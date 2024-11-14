// src/server.ts
import express from "express";
import http from "http";
import path from "path";
import { WebSocket, WebSocketServer } from "ws";
import { CameraController } from "./camera-controller";
import { RouterController } from "./router-control";
import { IGpio } from "./gpio-factory";
import { LogEntry, EjectionSettings, PresetSettings } from "./types";
import fs from "fs/promises";

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
    this.router = await RouterController.create(
      gpioFactory,
      this.camera,
      '"ejection-config.json"',
      20,
      21,
      14,
      15
    );

    this.setupWebSocket();
    this.setupRouterEvents();
    this.setupExpress(app);

    // Set up ping interval to keep connections alive
    this.pingInterval = setInterval(() => {
      this.wss.clients.forEach((client) => {
        if (client.readyState === WebSocket.OPEN) {
          client.ping();
          //console.log("❤️ Ping sent to client");
        }
      });
    }, 30000);
  }

  private setupWebSocket(): void {
    console.log("🔌 Setting up WebSocket handlers...");

    this.wss.on("listening", () => {
      console.log("👂 WebSocket server is listening for connections");
    });

    this.wss.on("connection", (ws: WebSocket, req: http.IncomingMessage) => {
      console.log(
        `✨ New WebSocket client connected from ${req.socket.remoteAddress}`
      );
      console.log(`📊 Total connected clients: ${this.wss.clients.size}`);

      this.connectedClients.add(ws);

      // Send initial state
      const initialState = {
        sensor1: this.router.sensorMonitor.getSensor1State(),
        sensor2: this.router.sensorMonitor.getSensor2State(),
        solenoid: this.router.sensorMonitor.getSolenoidState(),
        deviceConnected: false,
        lastPhotoPath: null,
        isCapturingImage: false,
        ejectionSettings: this.router.getEjectionSettings(),
      };

      //console.log("📤 Sending initial state:", initialState);
      ws.send(JSON.stringify(initialState));

      // Handle incoming messages
      ws.on("message", (data) => {
        try {
          const message: WebSocketMessage = JSON.parse(data.toString());
          //console.log("📥 Received message from client:", message);

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

      // Handle pong responses
      ws.on("pong", () => {
        //console.log("💓 Received pong from client");
      });

      ws.on("close", (code, reason) => {
        console.log(
          `🔌 Client disconnected. Code: ${code}, Reason: ${
            reason || "No reason provided"
          }`
        );
        console.log(
          `📊 Remaining connected clients: ${this.wss.clients.size - 1}`
        );
        this.connectedClients.delete(ws);
      });

      ws.on("error", (error) => {
        console.error("⚠️ WebSocket error:", error);
      });
    });

    this.wss.on("error", (error) => {
      console.error("🚨 WebSocket server error:", error);
    });
  }

  private setupExpress(app: express.Application): void {
    // Serve static files from the public directory
    app.use(express.static(path.join(process.cwd(), "public")));

    // Serve photos
    app.use("/api/photos", express.static(path.join(process.cwd(), "photos")));

    // Handle all other routes - Important for client-side routing
    app.get("*", (req, res) => {
      res.sendFile(path.join(process.cwd(), "public", "index.html"));
    });
  }

  private async handleEjectionSettingsUpdate(
    settings: Partial<EjectionSettings>
  ): Promise<void> {
    try {
      await this.router.updateEjectionSettings(settings);

      // Broadcast the new settings to all clients
      this.broadcast(
        "ejectionSettingsUpdated",
        this.router.getEjectionSettings()
      );

      // Log the update
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

      // Broadcast the new settings to all clients
      this.broadcast(
        "ejectionSettingsUpdated",
        this.router.getEjectionSettings()
      );

      // Log the preset application
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
    const settings = this.router.getEjectionSettings();
    ws.send(
      JSON.stringify({
        type: "ejectionSettings",
        data: settings,
      })
    );
  }

  private setupRouterEvents(): void {
    // Handle state updates
    this.router.on("stateUpdate", (state) => {
      this.broadcast("stateUpdate", state);
    });

    // Handle System logs
    this.router.on("systemLog", (log: LogEntry) => {
      this.broadcast("systemLog", log);
    });

    // Handle image capture events - now immediately sends the image
    this.router.on("imageCaptured", async (imageData) => {
      try {
        const imageBuffer = await fs.readFile(imageData.path);
        const metadata = {
          type: "image",
          filename: path.basename(imageData.path),
          mimeType: "image/jpeg",
          timestamp: imageData.timestamp,
          size: imageBuffer.length,
          analysis: null, // No analysis yet
          storedLocations: null,
        };

        // Send metadata first
        this.broadcast("imageMetadata", metadata);

        // Then send the image buffer
        this.connectedClients.forEach((client) => {
          if (client.readyState === WebSocket.OPEN) {
            client.send(imageBuffer);
          }
        });
      } catch (error) {
        console.error("Error sending image data:", error);
      }
    });

    // Handle analysis completion separately
    this.router.on("analysisComplete", (analysisData) => {
      try {
        // If we have analysis results, broadcast them with normalized format
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
            foo: "five",
          });
        }
      } catch (error) {
        console.error("Error sending analysis results:", error);
      }
    });

    // Handle alerts
    this.router.on("alert", (alert) => {
      this.broadcast("alert", alert);
    });
  }

  private broadcast(type: string, data: any): void {
    const message = JSON.stringify({ type, data });
    //console.log(`📢 Broadcasting ${type}:`, data);

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
