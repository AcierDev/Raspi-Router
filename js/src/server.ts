// src/server.ts
import express from "express";
import http from "http";
import path from "path";
import { WebSocket, WebSocketServer } from "ws";
import { CameraController } from "./camera-controller";
import { IGpio } from "./gpio-factory";
import { LogEntry, RouterSettings, PresetSettings } from "./types";
import fs from "fs/promises";
import { RouterController } from "./RouterController/RouterController";
import { configManager, stateManager } from "./config/ConfigManager";

interface WebSocketMessage {
  type: string;
  data: any;
}

export class MonitoringServer {
  private wss: WebSocketServer;
  public router: RouterController;
  public camera: CameraController;
  private connectedClients: Set<WebSocket> = new Set();
  private pingInterval: NodeJS.Timeout | null = null;
  private connectedClientIds: Map<string, WebSocket> = new Map();

  constructor(
    app: express.Application,
    server: http.Server,
    gpioFactory: (pin: number, direction: string, edge?: string) => IGpio
  ) {
    console.log("🚀 Initializing Monitoring Server...");

    this.wss = new WebSocketServer({
      server,
      path: "/ws",
    });

    console.log("📡 WebSocket server created with path: /ws");

    this.camera = new CameraController();
    this.router = new RouterController(gpioFactory, this.camera);

    this.setupWebSocket();
    this.setupRouterEvents();
    this.setupStateManagerEvents();
    this.setupExpress(app);

    this.pingInterval = setInterval(() => {
      this.wss.clients.forEach((client) => {
        if (client.readyState === WebSocket.OPEN) {
          client.ping();
        }
      });
    }, 30000);
  }

  private async setupWebSocket() {
    this.wss.on(
      "connection",
      async (ws: WebSocket, req: http.IncomingMessage) => {
        const clientId = req.headers["sec-websocket-key"];

        // If this client already has a connection, close the old one
        const existingConnection = this.connectedClientIds.get(clientId);
        if (existingConnection) {
          console.log(`Closing existing connection for client ${clientId}`);
          existingConnection.close(1000, "New connection initiated");
          this.connectedClients.delete(existingConnection);
          this.connectedClientIds.delete(clientId);
        }

        // Store new connection
        this.connectedClientIds.set(clientId, ws);
        this.connectedClients.add(ws);

        // Send initial state and config
        const initialState = stateManager.getState();
        const initialConfig = configManager.getConfig();

        ws.send(
          JSON.stringify({
            type: "initialData",
            data: {
              state: initialState,
              config: initialConfig,
            },
          })
        );

        ws.on("message", (data) => {
          try {
            const message: WebSocketMessage = JSON.parse(data.toString());

            switch (message.type) {
              case "updateEjectionSettings":
                this.handleEjectionSettingsUpdate(message.data);
                break;
              case "applyEjectionPreset":
                this.handleEjectionPreset(message.data);
                break;
              case "getEjectionSettings":
                this.sendEjectionSettings(ws);
                break;
              default:
                console.log("📥 Unhandled message type:", message.type);
            }
          } catch (error) {
            console.error("Error processing WebSocket message:", error);
            ws.send(
              JSON.stringify({
                type: "error",
                data: "Invalid message format",
              })
            );
          }
        });

        ws.on("pong", () => {
          // Pong received, connection is alive
        });

        ws.on("close", () => {
          this.connectedClientIds.delete(clientId);
          this.connectedClients.delete(ws);
        });

        ws.on("error", (error) => {
          console.error("⚠️ WebSocket error:", error);
        });
      }
    );

    this.wss.on("error", (error) => {
      console.error("🚨 WebSocket server error:", error);
    });
  }

  private setupStateManagerEvents(): void {
    // Listen for state updates
    stateManager.on("stateUpdate", (state, source) => {
      this.broadcast("stateUpdate", state);
    });

    // Listen for config updates
    configManager.on("configUpdate", (config) => {
      this.broadcast("configUpdate", config);
    });
  }

  private setupExpress(app: express.Application): void {
    app.use(express.static(path.join(process.cwd(), "public")));
    app.use("/api/photos", express.static(path.join(process.cwd(), "photos")));
    app.get("*", (req, res) => {
      res.sendFile(path.join(process.cwd(), "public", "index.html"));
    });
  }

  private async handleEjectionSettingsUpdate(
    settings: Partial<RouterSettings>
  ): Promise<void> {
    try {
      await this.router.updateEjectionSettings(settings);

      const logEntry: LogEntry = {
        timestamp: new Date().toISOString(),
        level: "info",
        message: "Ejection settings updated",
      };
      this.broadcast("systemLog", logEntry);
    } catch (error) {
      console.error("Error updating ejection settings:", error);
      const logEntry: LogEntry = {
        timestamp: new Date().toISOString(),
        level: "error",
        message: "Failed to update ejection settings",
      };
      this.broadcast("systemLog", logEntry);
    }
  }

  private async handleEjectionPreset(preset: PresetSettings): Promise<void> {
    try {
      await this.router.applyEjectionPreset(preset);

      const logEntry: LogEntry = {
        timestamp: new Date().toISOString(),
        level: "info",
        message: `Applied ${preset} ejection preset`,
      };
      this.broadcast("systemLog", logEntry);
    } catch (error) {
      console.error("Error applying ejection preset:", error);
      const logEntry: LogEntry = {
        timestamp: new Date().toISOString(),
        level: "error",
        message: "Failed to apply ejection preset",
      };
      this.broadcast("systemLog", logEntry);
    }
  }

  private sendEjectionSettings(ws: WebSocket): void {
    const settings = configManager.getConfig();
    ws.send(
      JSON.stringify({
        type: "ejectionSettings",
        data: settings,
      })
    );
  }

  private setupRouterEvents(): void {
    // Forward system logs
    this.router.on("systemLog", (log: LogEntry) => {
      this.broadcast("systemLog", log);
    });

    // Handle image capture events
    this.router.on("imageCaptured", async (imageData) => {
      try {
        const imageBuffer = await fs.readFile(imageData.path);
        const metadata = {
          type: "image",
          filename: path.basename(imageData.path),
          mimeType: "image/jpeg",
          timestamp: imageData.timestamp,
          size: imageBuffer.length,
          analysis: null,
          storedLocations: null,
        };

        this.broadcast("imageMetadata", metadata);

        this.connectedClients.forEach((client) => {
          if (client.readyState === WebSocket.OPEN) {
            client.send(imageBuffer);
          }
        });
      } catch (error) {
        console.error("Error sending image data:", error);
      }
    });

    // Handle analysis completion
    this.router.on("analysisComplete", (analysisData) => {
      try {
        if (analysisData.analysis?.predictions) {
          const normalizedPredictions = analysisData.analysis.predictions.map(
            (pred) => ({
              class_name: pred.class_name,
              confidence: pred.confidence,
              detection_id: pred.detection_id,
              bbox: {
                x1: pred.bbox[0],
                y1: pred.bbox[1],
                x2: pred.bbox[2],
                y2: pred.bbox[3],
              },
            })
          );

          this.broadcast("analysisResults", {
            filename: path.basename(analysisData.path),
            timestamp: analysisData.timestamp,
            predictions: normalizedPredictions,
            storedLocations: analysisData.storedLocations,
            processingTime: analysisData.processingTime,
          });
        }
      } catch (error) {
        console.error("Error sending analysis results:", error);
      }
    });

    // Forward alerts
    this.router.on("alert", (alert) => {
      this.broadcast("alert", alert);
    });
  }

  private broadcast(type: string, data: any): void {
    const message = JSON.stringify({ type, data });

    this.connectedClients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        try {
          client.send(message);
        } catch (error) {
          console.error(`⚠️ Error broadcasting ${type} to client:`, error);
        }
      }
    });
  }

  public cleanup(): void {
    console.log("🧹 Starting server cleanup...");

    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      console.log("⏱️ Cleared ping interval");
    }

    this.router.cleanup();
    console.log("🔌 Router cleaned up");

    let closedCount = 0;
    this.connectedClients.forEach((client) => {
      client.close();
      closedCount++;
    });
    console.log(`🚪 Closed ${closedCount} WebSocket connections`);

    console.log("✨ Cleanup complete");
  }
}
