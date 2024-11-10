// src/server.ts
import express from "express";
import http from "http";
import path from "path";
import { WebSocket, WebSocketServer } from "ws";
import { CameraController } from "./camera-controller";
import { RouterController } from "./router-control";
import { IGpio } from "./gpio-factory";

import fs from "fs/promises";

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
    this.router = new RouterController(gpioFactory);

    this.setupWebSocket();
    this.setupRouterEvents();
    this.setupExpress(app);

    // Set up ping interval to keep connections alive
    this.pingInterval = setInterval(() => {
      this.wss.clients.forEach((client) => {
        if (client.readyState === WebSocket.OPEN) {
          client.ping();
          console.log("❤️ Ping sent to client");
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
        sensor1: this.router.getSensor1State(),
        sensor2: this.router.getSensor2State(),
        solenoid: this.router.getSolenoidState(),
        deviceConnected: false,
        lastPhotoPath: null,
      };

      console.log("📤 Sending initial state:", initialState);
      ws.send(JSON.stringify(initialState));

      // Handle incoming messages
      ws.on("message", (data) => {
        console.log("📥 Received message from client:", data.toString());
      });

      // Handle pong responses
      ws.on("pong", () => {
        console.log("💓 Received pong from client");
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

    // Health check endpoint
    app.get("/api/health", async (req, res) => {
      const deviceConnected = await this.camera.checkDeviceConnection();
      res.json({
        status: "healthy",
        deviceConnected,
        sensor1: this.router.getSensor1State(),
        sensor2: this.router.getSensor2State(),
        solenoid: this.router.getSolenoidState(),
      });
    });

    // Handle all other routes - Important for client-side routing
    app.get("*", (req, res) => {
      res.sendFile(path.join(process.cwd(), "public", "index.html"));
    });
  }

  private async setupRouterEvents(): Promise<void> {
    // State updates
    this.router.on("stateUpdate", (state) => {
      this.broadcastState(state);
    });

    // Image capture handling
    this.router.on("startImageCapture", async () => {
      try {
        const deviceConnected = await this.camera.checkDeviceConnection();
        if (deviceConnected) {
          const photoPath = await this.camera.takePhoto();

          // Create a binary message with a header to identify the message type
          const imageBuffer = await fs.readFile(photoPath);
          const metadata = {
            type: "image",
            filename: path.basename(photoPath),
            mimeType: "image/jpeg",
            timestamp: new Date().toISOString(),
            size: imageBuffer.length,
          };

          // Send metadata first
          this.broadcast("imageMetadata", metadata);

          // Send the binary image data to each client
          this.connectedClients.forEach((client) => {
            if (client.readyState === WebSocket.OPEN) {
              try {
                client.send(imageBuffer);
              } catch (error) {
                console.error("Error sending image data:", error);
              }
            }
          });

          this.router.imageCaptureComplete(true);
        } else {
          this.router.imageCaptureComplete(false);
          this.broadcast("alert", {
            type: "error",
            message: "Camera device not connected",
            timestamp: new Date().toISOString(),
          });
        }
      } catch (error) {
        this.router.imageCaptureComplete(false);
        this.broadcast("alert", {
          type: "error",
          message: "Failed to capture image",
          data: error,
          timestamp: new Date().toISOString(),
        });
      }
    });
  }

  private broadcast(type: string, data: any): void {
    const message = JSON.stringify({ type, data });
    console.log(`📢 Broadcasting ${type}:`, data);

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

  private broadcastState(state: any): void {
    const message = JSON.stringify(state);
    console.log(`📢 Broadcasting state update:`, state);

    let successCount = 0;
    let failCount = 0;

    this.connectedClients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        try {
          client.send(message);
          successCount++;
        } catch (error) {
          console.error("⚠️ Error broadcasting to client:", error);
          failCount++;
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
