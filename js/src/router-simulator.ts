import { EventEmitter } from "events";
import * as readline from "readline";
import { RouterController } from "./router-control";
import { CameraController } from "./camera-controller";

interface SimulatorDependencies {
  router: RouterController;
  camera: CameraController;
}

export class RouterSimulator {
  private rl: readline.Interface;
  private router: RouterController;
  private camera: CameraController;

  constructor(dependencies: SimulatorDependencies) {
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
q - Quit
------------------------
`);

    this.rl.on("line", async (input) => {
      try {
        await this.handleCommand(input.toLowerCase());
      } catch (error) {
        console.error("Error processing command:", error);
      }
    });
  }

  private async handleCommand(command: string): Promise<void> {
    try {
      switch (command) {
        case "1":
          // Access sensor1 through the router's exposed methods
          this.router.updateSensor1State(1);
          console.log("🟢 Entry sensor activated");
          break;
        case "2":
          // Access sensor2 through the router's exposed methods
          this.router.updateSensor2State(1);
          console.log("🟢 Exit sensor activated");
          break;
        case "!":
          this.router.updateSensor1State(0);
          console.log("⭕ Entry sensor deactivated");
          break;
        case "@":
          this.router.updateSensor2State(0);
          console.log("⭕ Exit sensor deactivated");
          break;
        case "c":
          const connected = await this.camera.checkDeviceConnection();
          console.log(
            connected ? "📱 Camera connected" : "❌ Camera not connected"
          );
          break;
        case "p":
          try {
            this.router.updateSensor1State(0);
            this.router.updateSensor2State(0);
            setTimeout(() => {
              this.router.updateSensor1State(1);
              this.router.updateSensor2State(1);
            }, 1000);
          } catch (error) {
            console.error("❌ Failed to take photo:", error);
          }
          break;
        case "q":
          this.cleanup();
          process.exit(0);
          break;
        default:
          console.log("Unknown command");
      }
    } catch (error) {
      console.error("Error executing command:", error);
    }
  }

  public cleanup(): void {
    this.rl.close();
  }
}
