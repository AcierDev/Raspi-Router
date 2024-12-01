// src/RouterController/RouterController.ts
import { EventEmitter } from "events";
import fs from "fs";
import path from "path";
import {
  DetectionResponse,
  RouterSettings,
  PresetSettings,
  IGpio,
  LogEntry,
} from "../types";
import { EjectionControl } from "../ejection-control";
import { CameraController } from "../camera-controller";
import { SensorController } from "./SensorController";
import { EJECTOR_PIN } from "../config/DEFAULT_CONFIG";
import { configManager, stateManager } from "../config/ConfigManager";

export class RouterController extends EventEmitter {
  private ejectionControl: EjectionControl;
  private isCapturingImage = false;
  public sensorController: SensorController;
  private readonly DETECTION_API =
    "http://192.168.1.210:5000/detect-imperfection";

  constructor(
    gpioFactory: (pin: number, direction: string, edge?: string) => IGpio,
    private camera: CameraController,
    private readonly sensor1ActivationTime: number = 300,
    private readonly pistonDeactivationDelay: number = 500
  ) {
    super();
    this.initializeAsync(gpioFactory);
  }

  private async initializeAsync(
    gpioFactory: (pin: number, direction: string, edge?: string) => IGpio
  ): Promise<void> {
    try {
      // Initialize config manager
      await configManager.initialize();

      // Initialize sensor controller
      this.sensorController = new SensorController(
        gpioFactory,
        this.sensor1ActivationTime,
        configManager,
        this.camera
      );
      this.setupSensorControllerEvents();

      // Initialize camera
      this.setupCameraEvents();

      // Initialize ejection control
      this.ejectionControl = new EjectionControl(
        gpioFactory,
        EJECTOR_PIN,
        configManager
      );
      this.setupEjectionControlEvents();

      this.emitSystemLog("Router Controller initialized successfully");
    } catch (error) {
      this.emitAlert("error", "Failed to initialize router controller", error);
      throw error;
    }
  }

  private setupSensorControllerEvents(): void {
    // Forward system logs
    this.sensorController.on("systemLog", (log) => {
      this.emit("systemLog", log);
    });

    // Forward alerts
    this.sensorController.on("alert", (alert) => {
      this.emit("alert", alert);
    });

    // Handle ready for capture event
    this.sensorController.on("readyForCapture", () => {
      this.handleImageCapture();
    });
  }

  private setupEjectionControlEvents() {
    this.ejectionControl.on("ejectionStarted", () => {
      stateManager.setEjectorActive(true);
      this.emitSystemLog("Ejection started");
    });

    this.ejectionControl.on("ejectionComplete", () => {
      stateManager.setEjectorActive(false);
      this.emitSystemLog("Ejection completed");
    });

    this.ejectionControl.on("error", (error) => {
      stateManager.setEjectorActive(false);
      this.emitAlert("error", "Ejection system error", error);
    });

    this.ejectionControl.on("configUpdated", (newConfig) => {
      configManager.updateConfig(newConfig);
      this.emitSystemLog("Ejection configuration updated", newConfig);
    });
  }

  private setupCameraEvents(): void {
    this.camera.on(
      "deviceStatus",
      (status: "connected" | "disconnected" | "error") => {
        console.log("camera event status:", status);
        stateManager.setDeviceConnected(status === "connected");
        if (status !== "connected") {
          this.emitAlert("warning", `Camera ${status}`);
        }
      }
    );

    this.camera.on("photoTaken", (filepath: string) => {
      stateManager.setLastPhotoPath(filepath);
      this.emit("photoTaken", filepath);
    });

    this.camera.on("error", (error: Error) => {
      this.emitAlert("error", "Camera error", error);
    });
  }

  public async updateEjectionSettings(
    settings: Partial<RouterSettings>
  ): Promise<void> {
    try {
      await this.ejectionControl.updateConfig(settings);
      this.emitSystemLog("Ejection settings updated successfully");
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
      await configManager.applyPreset(preset);

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
      const ejectionResult = this.ejectionControl.shouldEject(results);

      // Update the last ejection result in state
      await stateManager.updateState({
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

  private async handleImageCapture(): Promise<void> {
    if (this.isCapturingImage) return;

    try {
      this.isCapturingImage = true;
      await stateManager.setCapturingImage(true);

      const filepath = await this.camera.takePhoto();
      await stateManager.setLastPhotoPath(filepath);

      this.emit("imageCaptured", {
        path: filepath,
        timestamp: new Date().toISOString(),
        analysis: null,
        storedLocations: null,
      });

      await this.analyzeImageAndProcess(filepath);

      this.sensorController.handleCaptureComplete(true);
      this.imageCaptureComplete(true);
      this.emitSystemLog("Image capture and analysis completed", { filepath });
    } catch (error) {
      this.emitAlert(
        "error",
        error instanceof Error ? error.message : "Camera error"
      );
      this.sensorController.handleCaptureComplete(false);
      this.imageCaptureComplete(false);
      this.emitSystemLog("Image capture or analysis failed", { error });
    }
  }

  private async analyzeImageAndProcess(filepath: string): Promise<void> {
    try {
      const startTime = Date.now();
      const analysisResults = await this.analyzeImage(filepath);

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

      const ejectionResult = this.ejectionControl.shouldEject(analysisResults);
      if (ejectionResult.shouldEject) {
        await this.ejectionControl.activate();
        this.emitSystemLog("Ejection triggered", ejectionResult);
      }
    } catch (error) {
      this.emitAlert("warning", "Image analysis failed", error);
      this.emitSystemLog("Image analysis failed", { error, filepath });
      throw error;
    }
  }

  public imageCaptureComplete(success: boolean = true): void {
    this.isCapturingImage = false;
    stateManager.setCapturingImage(false);

    if (!success) {
      this.emitSystemLog("Image capture failed - ending capture cycle");
      this.emitAlert(
        "error",
        "Image capture failed - awaiting new sensor1 activation"
      );
      this.sensorController.invalidateCycle();
    } else {
      this.emitSystemLog("Image capture completed successfully");
      this.sensorController.invalidateCycle();
    }
  }

  // Helper methods for emitting logs and alerts
  private emitSystemLog(message: string, data?: any) {
    const logEntry: LogEntry = {
      timestamp: new Date().toISOString(),
      level: "info",
      message,
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

  public getEjectionSettings(): RouterSettings {
    return configManager.getConfig();
  }

  public cleanup(): void {
    this.emitSystemLog("Starting cleanup");
    this.sensorController.cleanup();
    this.ejectionControl.cleanup();
    this.emitSystemLog("Cleanup completed");
  }
}
