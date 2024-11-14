import EventEmitter from "events";
import {
  IGpio,
  IImageProcessor,
  ISensorMonitor,
  IStateManager,
  SystemState,
} from "./types";
import { CameraController } from "./camera-controller";
import { ConfigurationManager } from "./ConfigManager";
import { SensorMonitor } from "./SensorMonitor";
import { DEFAULT_EJECTION_CONFIG } from "./ejection-config";
import { EjectionControl } from "./ejection-control";
import { ImageProcessor } from "./ImageProcessor";

// RouterController.ts (simplified main class)
export class RouterController extends EventEmitter {
  public sensorMonitor: ISensorMonitor;
  public imageProcessor: IImageProcessor;
  private systemState: SystemState;

  private constructor(
    gpioFactory: (pin: number, direction: string, edge?: string) => IGpio,
    camera: CameraController,
    configManager: ConfigurationManager,
    sensor1Pin: number = 20,
    sensor2Pin: number = 21,
    solenoidPin: number = 14,
    ejectionPin: number = 15
  ) {
    super();

    this.systemState = {
      sensor1: false,
      sensor2: false,
      solenoid: false,
      ejection: false,
      isProcessing: false,
      isCapturingImage: false,
      lastPhotoPath: null,
      deviceConnected: false,
      ejectionSettings: DEFAULT_EJECTION_CONFIG,
    };

    const sensor1 = gpioFactory(sensor1Pin, "in", "both");
    const sensor2 = gpioFactory(sensor2Pin, "in", "both");
    const solenoid = gpioFactory(solenoidPin, "out");

    const ejectionControl = new EjectionControl(
      gpioFactory,
      ejectionPin,
      configManager
    );

    this.sensorMonitor = new SensorMonitor(sensor1, sensor2, solenoid, this);

    this.imageProcessor = new ImageProcessor(camera, ejectionControl, this);

    this.setupEventHandlers();
    this.sensorMonitor.startMonitoring();
  }

  getState(): SystemState {
    return { ...this.systemState };
  }

  // Static factory method for async initialization
  public static async create(
    gpioFactory: (pin: number, direction: string, edge?: string) => IGpio,
    camera: CameraController,
    configFileName?: string,
    sensor1Pin: number = 20,
    sensor2Pin: number = 21,
    solenoidPin: number = 14,
    ejectionPin: number = 15
  ): Promise<RouterController> {
    const configManager = await ConfigurationManager.create(configFileName);
    return new RouterController(
      gpioFactory,
      camera,
      configManager,
      sensor1Pin,
      sensor2Pin,
      solenoidPin,
      ejectionPin
    );
  }

  private setupEventHandlers(): void {
    this.sensorMonitor.on("sensor2Triggered", () => {
      if (!this.getState().isCapturingImage) {
        this.imageProcessor.processImage("").catch((error) => {
          this.emit("alert", {
            type: "error",
            message: "Failed to capture image",
            error,
          });
        });
      }
    });

    // Forward relevant events
    ["log", "alert", "photoTaken", "analysisComplete"].forEach((eventName) => {
      this.sensorMonitor.on(eventName, (...args) =>
        this.emit(eventName, ...args)
      );
      this.imageProcessor.on(eventName, (...args) =>
        this.emit(eventName, ...args)
      );
    });
  }

  updateState(updates: Partial<SystemState>): void {
    this.systemState = { ...this.systemState, ...updates };
    this.emit("stateUpdate", this.systemState);
  }

  public cleanup(): void {
    this.sensorMonitor.cleanup();
    this.imageProcessor.cleanup();
  }
}
