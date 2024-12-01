// src/RouterSimulator.ts
import { EventEmitter } from "events";
import * as readline from "readline";
import { RouterController } from "./RouterController/RouterController";
import { CameraController } from "./camera-controller";
import { stateManager } from "./config/ConfigManager";

interface SimulatorDependencies {
  router: RouterController;
  camera: CameraController;
}

export class RouterSimulator extends EventEmitter {
  private rl: readline.Interface;
  private router: RouterController;
  private camera: CameraController;

  constructor(dependencies: SimulatorDependencies) {
    super();
    this.router = dependencies.router;
    this.camera = dependencies.camera;

    this.rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });
  }

  public async start(): Promise<void> {
    console.log(`
Router Simulator Commands:
------------------------
1 - Activate Entry Sensor (Sensor 1)
2 - Activate Exit Sensor (Sensor 2)
! - Deactivate Entry Sensor
@ - Deactivate Exit Sensor
c - Check Camera Connection
p - Take Test Photo
s - Show Current State
q - Quit
------------------------
    `);

    // Show initial state
    this.displayCurrentState();

    this.rl.on("line", async (input) => {
      try {
        await this.handleCommand(input.toLowerCase());
      } catch (error) {
        console.error("Error processing command:", error);
      }
    });
  }

  private displayCurrentState(): void {
    const state = stateManager.getState();
    console.log("\nCurrent System State:");
    console.log("-------------------");
    console.log(
      `Sensor 1: ${state.sensor1.active ? "🟢 Active" : "⭕ Inactive"}`
    );
    console.log(`Piston: ${state.piston.active ? "🟢 Active" : "⭕ Inactive"}`);
    console.log(`Riser: ${state.riser.active ? "🟢 Active" : "⭕ Inactive"}`);
    console.log(`Processing: ${state.isProcessing ? "🟢 Yes" : "⭕ No"}`);
    console.log(
      `Camera Connected: ${state.deviceConnected ? "🟢 Yes" : "⭕ No"}`
    );
    console.log("-------------------\n");
  }

  private async handleCommand(command: string): Promise<void> {
    try {
      switch (command) {
        case "1":
          stateManager.setSensor1Active(true);
          console.log("🟢 Entry sensor activation command sent");
          break;

        case "!":
          stateManager.setSensor1Active(false);
          console.log("⭕ Entry sensor deactivation command sent");
          break;

        case "c":
          const connected = await this.camera.checkDeviceConnection();
          stateManager.setDeviceConnected(connected);
          console.log(
            connected ? "📱 Camera connected" : "❌ Camera not connected"
          );
          break;

        case "p":
          try {
            stateManager.setCapturingImage(true);
            const filepath = await this.camera.takePhoto();
            console.log(`📸 Photo taken: ${filepath}`);
            stateManager.setLastPhotoPath(filepath);
            stateManager.setCapturingImage(false);
          } catch (error) {
            console.error("❌ Failed to take photo:", error);
            stateManager.setCapturingImage(false);
          }
          break;

        case "s":
          this.displayCurrentState();
          break;

        case "q":
          console.log("Cleaning up and exiting...");
          this.cleanup();
          process.exit(0);
          break;

        default:
          console.log("❌ Unknown command");
      }
    } catch (error) {
      console.error("Error executing command:", error);
      // Reset any pending states in case of error
      stateManager.setCapturingImage(false);
    }
  }

  public cleanup(): void {
    this.rl.close();
    this.removeAllListeners();
  }
}
