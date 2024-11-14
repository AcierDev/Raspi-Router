import { EventEmitter } from "events";
import { IGpio } from "./gpio-factory";
import { CameraController } from "./camera-controller";
import {
  DetectionResponse,
  EjectionSettings,
  PresetSettings,
  SystemState,
} from "./types";
import fs from "fs";
import path from "path";
import { EjectionControl } from "./ejection-control";
import { DEFAULT_EJECTION_CONFIG } from "./ejection-config";
import { ConfigurationManager } from "./ConfigManager";

export class RouterController extends EventEmitter {
  private sensor1: IGpio;
  private sensor2: IGpio;
  private solenoid: IGpio;
  private ejectionControl: EjectionControl;
  private configManager: ConfigurationManager = new ConfigurationManager();
  private sensor1ActiveTime: number | null = null;
  private solenoidTimeout: NodeJS.Timeout | null = null;
  private isCapturingImage = false;
  private validCycleInProgress: boolean = false;
  private readonly DETECTION_API =
    "http://192.168.1.210:5000/detect-imperfection";

  private systemState: SystemState = {
    sensor1: false,
    sensor2: false,
    solenoid: false,
    ejection: false, // Added to initial state
    isProcessing: false,
    isCapturingImage: false,
    lastPhotoPath: null,
    deviceConnected: false,
    ejectionSettings: DEFAULT_EJECTION_CONFIG,
  };

  private previousStates = {
    sensor1: 0,
    sensor2: 0,
    solenoid: 0,
  };

  constructor(
    gpioFactory: (pin: number, direction: string, edge?: string) => IGpio,
    private camera: CameraController,
    private readonly sensor1Pin: number = 20,
    private readonly sensor2Pin: number = 21,
    private readonly solenoidPin: number = 14,
    private readonly ejectionPin: number = 15,
    private readonly sensor1ActivationTime: number = 300,
    private readonly solenoidDeactivationDelay: number = 500,
    initialEjectionConfig = DEFAULT_EJECTION_CONFIG
  ) {
    super();
    this.initializePins(gpioFactory);
    this.initializeAsync(gpioFactory);
    this.setupCameraEvents();
    this.configManager;

    // Initialize ejection control
    this.ejectionControl = new EjectionControl(
      gpioFactory,
      this.ejectionPin,
      this.configManager
    );

    this.emitSystemLog("Router Controller initialized", {
      sensor1Pin,
      sensor2Pin,
      solenoidPin,
      ejectionPin,
      sensor1ActivationTime,
      solenoidDeactivationDelay,
      initialEjectionConfig,
    });
  }

  private async initializeAsync(
    gpioFactory: (pin: number, direction: string, edge?: string) => IGpio
  ): Promise<void> {
    try {
      await this.configManager.initialize();
      this.initializePins(gpioFactory);
      this.setupCameraEvents();

      // Initialize ejection control with configured manager
      this.ejectionControl = new EjectionControl(
        gpioFactory,
        this.ejectionPin,
        this.configManager
      );

      // Setup ejection control events
      this.setupEjectionControlEvents();

      this.emitSystemLog("Router Controller initialized successfully");
    } catch (error) {
      this.emitAlert("error", "Failed to initialize router controller", error);
      throw error;
    }
  }
  setupEjectionControlEvents() {
    // Setup ejection control events with state updates
    this.ejectionControl.on("ejectionStarted", () => {
      this.updateSystemState({ ejection: true });
      this.emitSystemLog("Ejection started");
    });

    this.ejectionControl.on("ejectionComplete", () => {
      this.updateSystemState({ ejection: false });
      this.emitSystemLog("Ejection completed");
    });

    this.ejectionControl.on("error", (error) => {
      this.updateSystemState({ ejection: false });
      this.emitAlert("error", "Ejection system error", error);
    });

    this.ejectionControl.on("configUpdated", (newConfig) => {
      this.emitSystemLog("Ejection configuration updated", newConfig);
    });
  }

  // Update the configuration methods to be async
  public async updateEjectionSettings(
    settings: Partial<EjectionSettings>
  ): Promise<void> {
    try {
      await this.ejectionControl.updateConfig(settings);

      this.updateSystemState({
        ejectionSettings: this.ejectionControl.getConfig(),
      });

      this.emitSystemLog("Ejection settings updated successfully", {
        previousSettings: this.systemState.ejectionSettings,
        newSettings: settings,
      });
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";
      this.emitAlert(
        "error",
        "Failed to update ejection settings",
        errorMessage
      );
      this.emitSystemLog("Ejection settings update failed", {
        error: errorMessage,
      });
      throw error;
    }
  }

  public async applyEjectionPreset(preset: PresetSettings): Promise<void> {
    try {
      await this.ejectionControl.applyPreset(preset);

      this.updateSystemState({
        ejectionSettings: this.ejectionControl.getConfig(),
      });

      this.emitSystemLog("Ejection preset applied successfully", {
        preset,
        resultingSettings: this.ejectionControl.getConfig(),
      });
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";
      this.emitAlert("error", "Failed to apply ejection preset", errorMessage);
      this.emitSystemLog("Ejection preset application failed", {
        preset,
        error: errorMessage,
      });
      throw error;
    }
  }

  // Method to update ejection configuration
  public updateEjectionConfig(
    newConfig: Partial<typeof DEFAULT_EJECTION_CONFIG>
  ): void {
    this.ejectionControl.updateConfig(newConfig);
  }

  // Method to get current ejection configuration
  public getEjectionSettings(): typeof DEFAULT_EJECTION_CONFIG {
    return this.ejectionControl.getConfig();
  }

  private setupCameraEvents(): void {
    // Monitor camera device connection status
    this.camera.on(
      "deviceStatus",
      (status: "connected" | "disconnected" | "error") => {
        this.updateSystemState({ deviceConnected: status === "connected" });
        if (status !== "connected") {
          this.emitAlert("warning", `Camera ${status}`);
        }
      }
    );

    // Handle photo capture events
    this.camera.on("photoTaken", (filepath: string) => {
      this.updateSystemState({ lastPhotoPath: filepath });
      this.emit("photoTaken", filepath);
    });

    this.camera.on("error", (error: Error) => {
      this.emitAlert("error", "Camera error", error);
    });
  }

  private async analyzeImage(filepath: string): Promise<DetectionResponse> {
    try {
      const formData = new FormData();
      const imageBuffer = await fs.promises.readFile(filepath);
      formData.append(
        "image",
        new Blob([imageBuffer]),
        path.basename(filepath)
      );

      const response = await fetch(this.DETECTION_API, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Detection API returned ${response.status}`);
      }

      const results: DetectionResponse = await response.json();

      // Use EjectionControl to determine if ejection is needed
      const ejectionResult = this.ejectionControl.shouldEject(results);

      this.updateSystemState({
        lastEjectionResult: {
          didEject: ejectionResult.shouldEject,
          reason: ejectionResult.reason,
          details: ejectionResult.details,
        },
      });

      this.emitSystemLog("Image analysis completed", {
        predictionsCount: results.data.predictions.length,
        defectTypes: results.data.predictions.map((p) => p.class_name),
        timestamp: results.timestamp,
        ejectionResult,
      });

      // Activate ejection if needed
      if (ejectionResult.shouldEject) {
        await this.ejectionControl.activate();
        this.emitSystemLog("Ejection triggered", ejectionResult);
      }

      return results;
    } catch (error) {
      this.emitAlert("error", "Failed to analyze image", error);
      throw error;
    }
  }

  private async analyzeImageAsync(filepath: string): Promise<void> {
    try {
      const startTime = Date.now();
      // Perform analysis
      const analysisResults = await this.analyzeImage(filepath);

      // Emit analysis results separately
      this.emit("analysisComplete", {
        path: filepath,
        timestamp: new Date().toISOString(),
        analysis: {
          ...analysisResults?.data,
        },
        processingTime: Date.now() - startTime,
        storedLocations: analysisResults?.data.file_info.stored_locations,
      });

      this.emitSystemLog("Image analysis completed", {
        filepath,
        hasAnalysis: true,
        storedLocations: analysisResults?.data.file_info.stored_locations,
      });

      // Handle ejection based on analysis results
      const ejectionResult = this.ejectionControl.shouldEject(analysisResults);
      if (ejectionResult.shouldEject) {
        await this.ejectionControl.activate();
        this.emitSystemLog("Ejection triggered", ejectionResult);
      }
    } catch (error) {
      this.emitAlert("warning", "Image analysis failed", error);
      this.emitSystemLog("Image analysis failed", { error, filepath });
    }
  }

  private async handleImageCapture(): Promise<void> {
    if (this.isCapturingImage) return;

    try {
      // const deviceConnected = await this.camera.quickDeviceCheck();
      // if (!deviceConnected) {
      //   throw new Error("Camera device not connected");
      // }

      this.isCapturingImage = true;
      this.updateSystemState({ isCapturingImage: true });

      // Capture the photo
      const filepath = await this.camera.takePhoto();

      // Immediately emit the captured image without analysis
      this.emit("imageCaptured", {
        path: filepath,
        timestamp: new Date().toISOString(),
        analysis: null,
        storedLocations: null,
      });

      // Start analysis asynchronously
      this.analyzeImageAsync(filepath);

      this.imageCaptureComplete(true);
      this.emitSystemLog("Image capture completed", { filepath });
    } catch (error) {
      this.emitAlert(
        "error",
        error instanceof Error ? error.message : "Camera error"
      );
      this.imageCaptureComplete(false);
      this.emitSystemLog("Image capture failed", { error });
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }

  private emitSystemLog(message: string, data?: any) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      message,
      data,
    };
    this.emit("systemLog", logEntry);
  }

  private emitAlert(
    type: "warning" | "error" | "info",
    message: string,
    data?: any
  ) {
    const alert = {
      type,
      timestamp: new Date().toISOString(),
      message,
      data,
    };
    this.emit("alert", alert);
  }

  private updateSystemState(updates: Partial<SystemState>) {
    const previousState = { ...this.systemState };
    this.systemState = { ...this.systemState, ...updates };

    this.emit("stateUpdate", this.systemState);
  }

  private initializePins(
    gpioFactory: (pin: number, direction: string, edge?: string) => IGpio
  ): void {
    try {
      this.sensor1 = gpioFactory(this.sensor1Pin, "in", "both");
      this.sensor2 = gpioFactory(this.sensor2Pin, "in", "both");
      this.solenoid = gpioFactory(this.solenoidPin, "out");

      this.solenoid.writeSync(0);
      this.monitorSensors();

      this.updateSystemState({
        sensor1: this.sensor1.readSync() === 1,
        sensor2: this.sensor2.readSync() === 1,
        solenoid: false,
      });

      // setInterval(() => {
      //   console.log("Sensor 1: ", this.sensor1.readSync());
      //   console.log("Sensor 2: ", this.sensor2.readSync());
      // });

      this.emitSystemLog("Initial system state set", this.systemState);

      this.sensor1.watch((err, value) => {
        if (err) {
          this.emitAlert("error", "Sensor 1 error", err);
          return;
        }
        const isActive = value === 1;
        this.updateSystemState({ sensor1: isActive });
        this.emitSystemLog(
          `Sensor 1 ${isActive ? "activated" : "deactivated"}`
        );
      });

      this.sensor2.watch((err, value) => {
        if (err) {
          this.emitAlert("error", "Sensor 2 error", err);
          return;
        }
        const isActive = value === 1;
        this.updateSystemState({ sensor2: isActive });
        this.emitSystemLog(
          `Sensor 2 ${isActive ? "activated" : "deactivated"}`
        );
      });
    } catch (error) {
      this.emitAlert("error", "Failed to initialize pins", error);
      throw error;
    }
  }

  private monitorSensors(): void {
    setInterval(() => {
      try {
        const currentTime = Date.now();
        const sensor1Active = this.sensor1.readSync() === 1;
        const sensor2Active = this.sensor2.readSync() === 1;

        // Handle Sensor 1 activation - starts a new valid cycle
        if (sensor1Active) {
          if (!this.sensor1ActiveTime) {
            this.emitSystemLog("Sensor 1 activation started");
            this.sensor1ActiveTime = currentTime;
            this.validCycleInProgress = true;
            this.updateSystemState({ isProcessing: true });
          }

          if (
            currentTime - this.sensor1ActiveTime >=
            this.sensor1ActivationTime
          ) {
            this.activateSolenoid();
          }
        } else {
          if (this.sensor1ActiveTime) {
            this.emitSystemLog("Sensor 1 deactivation process started");
            this.handleSensor1Deactivation();
          }
          this.sensor1ActiveTime = null;
        }

        // Only handle Sensor 2 if we're in a valid cycle (sensor1 was activated first)
        if (
          sensor2Active &&
          !this.isCapturingImage &&
          this.validCycleInProgress
        ) {
          this.handleImageCapture().catch((error) => {
            this.emitAlert("error", "Failed to capture image", error);
          });
        }
      } catch (error) {
        this.emitAlert("error", "Sensor monitoring error", error);
      }
    }, 50);
  }

  private activateSolenoid(): void {
    try {
      if (!this.systemState.solenoid) {
        this.solenoid.writeSync(1);
        this.updateSystemState({ solenoid: true });
        this.emitSystemLog("Solenoid activated");
      }
    } catch (error) {
      this.emitAlert("error", "Failed to activate solenoid", error);
    }
  }

  private handleSensor1Deactivation(): void {
    if (this.solenoidTimeout) {
      clearTimeout(this.solenoidTimeout);
    }

    this.solenoidTimeout = setTimeout(() => {
      try {
        if (this.systemState.solenoid) {
          this.solenoid.writeSync(0);
          this.updateSystemState({
            solenoid: false,
            isProcessing: false,
          });
          this.emitSystemLog("Solenoid deactivated");
        }
        // Reset the valid cycle flag when solenoid deactivates
        this.validCycleInProgress = false;
      } catch (error) {
        this.emitAlert("error", "Failed to deactivate solenoid", error);
      }
    }, this.solenoidDeactivationDelay);
  }

  public imageCaptureComplete(success: boolean = true): void {
    this.isCapturingImage = false;
    this.updateSystemState({ isCapturingImage: false });

    if (!success) {
      this.emitSystemLog("Image capture failed - ending capture cycle");
      this.emitAlert(
        "error",
        "Image capture failed - awaiting new sensor1 activation"
      );
      // Reset cycle on failure
      this.validCycleInProgress = false;
    } else {
      this.emitSystemLog("Image capture completed successfully");
      // Reset cycle after successful capture
      this.validCycleInProgress = false;
    }
  }

  public cleanup(): void {
    this.emitSystemLog("Starting cleanup");
    if (this.solenoidTimeout) {
      clearTimeout(this.solenoidTimeout);
    }
    this.sensor1.unexport();
    this.sensor2.unexport();
    this.solenoid.unexport();
    this.ejectionControl.cleanup();
    this.emitSystemLog("Cleanup completed");
  }

  public getSystemState(): SystemState {
    return { ...this.systemState };
  }

  public getSensor1State(): number {
    return this.sensor1.readSync();
  }

  public getSensor2State(): number {
    return this.sensor2.readSync();
  }

  public getSolenoidState(): number {
    return this.solenoid.readSync();
  }

  public updateSensor1State(value: number): void {
    if (value !== this.previousStates.sensor1) {
      console.log(
        `🔄 Manually updating Sensor 1: ${this.previousStates.sensor1} -> ${value}`
      );
      this.sensor1.writeSync(value);
      this.previousStates.sensor1 = value;
    }
  }

  public updateSensor2State(value: number): void {
    if (value !== this.previousStates.sensor2) {
      console.log(
        `🔄 Manually updating Sensor 2: ${this.previousStates.sensor2} -> ${value}`
      );
      this.sensor2.writeSync(value);
      this.previousStates.sensor2 = value;
    }
  }
}
