import EventEmitter from "events";
import { DetectionResponse, IImageProcessor } from "./types";
import { EjectionControl } from "./ejection-control";
import { CameraController } from "./camera-controller";
import path from "path";
import fs from "fs";
import { RouterController } from "./router-control";

// ImageProcessor.ts
export class ImageProcessor extends EventEmitter implements IImageProcessor {
  private isCapturingImage = false;
  private readonly DETECTION_API =
    "http://192.168.1.210:5000/detect-imperfection";

  constructor(
    private camera: CameraController,
    private ejectionControl: EjectionControl,
    private controller: RouterController
  ) {
    super();
    this.setupCameraEvents();
  }

  private setupCameraEvents(): void {
    this.camera.on(
      "deviceStatus",
      (status: "connected" | "disconnected" | "error") => {
        this.controller.updateState({
          deviceConnected: status === "connected",
        });
        if (status !== "connected") {
          this.emit("alert", { type: "warning", message: `Camera ${status}` });
        }
      }
    );

    this.camera.on("photoTaken", (filepath: string) => {
      this.controller.updateState({ lastPhotoPath: filepath });
      this.emit("photoTaken", filepath);
    });

    this.camera.on("error", (error: Error) => {
      this.emit("alert", { type: "error", message: "Camera error", error });
    });
  }

  async processImage(filepath: string): Promise<void> {
    if (this.isCapturingImage) return;

    try {
      this.isCapturingImage = true;
      this.controller.updateState({ isCapturingImage: true });

      const filepath = await this.camera.takePhoto();

      this.emit("imageCaptured", {
        path: filepath,
        timestamp: new Date().toISOString(),
        analysis: null,
        storedLocations: null,
      });

      await this.analyzeImage(filepath);

      this.imageCaptureComplete(true);
      this.emit("log", "Image capture completed", { filepath });
    } catch (error) {
      this.emit("alert", {
        type: "error",
        message: error instanceof Error ? error.message : "Camera error",
      });
      this.imageCaptureComplete(false);
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }

  private async analyzeImage(filepath: string): Promise<void> {
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

      if (ejectionResult.shouldEject) {
        await this.ejectionControl.activate();
        this.emit("log", "Ejection triggered", ejectionResult);
      }

      this.emit("analysisComplete", {
        path: filepath,
        timestamp: new Date().toISOString(),
        analysis: results.data,
        processingTime: Date.now() - results.timestamp,
        storedLocations: results.data.file_info.stored_locations,
      });
    } catch (error) {
      this.emit("alert", {
        type: "error",
        message: "Failed to analyze image",
        error,
      });
    }
  }

  private imageCaptureComplete(success: boolean = true): void {
    this.isCapturingImage = false;
    this.controller.updateState({ isCapturingImage: false });

    if (!success) {
      this.emit("log", "Image capture failed - ending capture cycle");
      this.emit("alert", {
        type: "error",
        message: "Image capture failed - awaiting new sensor1 activation",
      });
    } else {
      this.emit("log", "Image capture completed successfully");
    }
  }

  cleanup(): void {
    // Any cleanup needed for the image processor
  }
}
