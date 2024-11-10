// src/index.ts
import express from "express";
import http from "http";
import { MonitoringServer } from "./server";
import { createGpioFactory } from "./gpio-factory";
import { RouterSimulator } from "./router-simulator";

async function startApplication(isSimulation: boolean = false) {
  try {
    // Create express app and server
    const app = express();
    const server = http.createServer(app);

    // Initialize GPIO factory
    const gpioFactory = createGpioFactory();

    // Create monitoring server
    const monitoring = new MonitoringServer(app, server, gpioFactory);

    // Start web server
    server.listen(3000, () => {
      console.log("Web dashboard available at http://localhost:3000");
    });

    let simulator: RouterSimulator | null = null;

    // If in simulation mode, start the simulator
    if (isSimulation) {
      simulator = new RouterSimulator({
        router: monitoring.router,
        camera: monitoring.camera,
      });
      await simulator.start();
    }

    // Handle shutdown gracefully
    const cleanup = () => {
      console.log("Shutting down...");
      monitoring.cleanup();
      if (simulator) {
        simulator.cleanup();
      }
      server.close(() => process.exit(0));
    };

    process.on("SIGINT", cleanup);
    process.on("SIGTERM", cleanup);
  } catch (error) {
    console.error("Failed to start application:", error);
    process.exit(1);
  }
}

// Start the application based on environment
const isSimulation = process.env.NODE_ENV === "simulation";
startApplication(isSimulation).catch((error) => {
  console.error("Failed to start application:", error);
  process.exit(1);
});
