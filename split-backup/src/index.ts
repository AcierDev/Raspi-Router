// src/index.ts
import express from "express";
import http from "http";
import { MonitoringServer } from "./server";
import { createGpioFactory } from "./gpio-factory";
import { RouterSimulator } from "./router-simulator";
import { CameraController } from "./camera-controller";
import { RouterController } from "./router-control";

async function startApplication(isSimulation: boolean) {
  try {
    // Create express app and server
    const app = express();
    const server = http.createServer(app);

    const gpioFactory = createGpioFactory(); // Your GPIO factory implementation
    const camera = new CameraController(); // Your camera controller implementation

    // Create monitoring server
    const monitoring = new MonitoringServer(app, server, await gpioFactory);

    let simulator: RouterSimulator | null = null;

    // If in simulation mode, start the simulator
    if (isSimulation) {
      simulator = new RouterSimulator({
        router: monitoring.router,
        camera: monitoring.camera,
      });
      await simulator.start();
    }

    // Start web server
    server.listen(3000, () => {
      console.log("Web dashboard available at http://localhost:3000");
    });

    const routerController = await RouterController.create(
      await gpioFactory,
      camera
    );

    // Rest of your application startup code
    console.log("Application started successfully");

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

    return routerController;
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
