import EventEmitter from "events";
import { exec } from "child_process";
import { promisify } from "util";
import fs from "fs/promises";
import path from "path";

const execAsync = promisify(exec);

interface CameraControllerConfig {
  photosDir: string;
  connectionCheckInterval: number;
  maxRetries: number;
  retryDelay: number;
}

export class CameraController extends EventEmitter {
  private readonly config: CameraControllerConfig;
  private isCapturing: boolean = false;
  private lastPhotoList: string[] = [];
  private cameraPath: string | null = null;
  private lastPhotoCheck: number = 0;
  private photoCheckInterval: number = 100;
  private lastKnownPhoto: string | null = null;
  private deviceStatus: "connected" | "disconnected" | "error" = "disconnected";
  private monitoringInterval;

  constructor(config: Partial<CameraControllerConfig> = {}) {
    super();
    this.config = {
      photosDir: "./photos",
      connectionCheckInterval: 5000,
      maxRetries: 3,
      retryDelay: 2000,
      ...config,
    };
    this.initialize();
  }

  private async initialize(): Promise<void> {
    try {
      await fs.mkdir(this.config.photosDir, { recursive: true });
      // Perform initial device check immediately
      const initialStatus = await this.checkDeviceConnection();
      this.deviceStatus = initialStatus ? "connected" : "disconnected";
      this.emit("deviceStatus", this.deviceStatus);

      // Then start the monitoring interval
      await this.startDeviceMonitoring();
    } catch (error) {
      this.deviceStatus = "error";
      this.emit("deviceStatus", "error");
      this.emit("error", new Error("Failed to initialize camera controller"));
    }
  }

  private async startDeviceMonitoring(): Promise<void> {
    // First clear any existing intervals to prevent duplicates
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
    }

    this.monitoringInterval = setInterval(async () => {
      try {
        const isConnected = await this.checkDeviceConnection();
        const newStatus = isConnected ? "connected" : "disconnected";

        // Only emit if status actually changed
        if (newStatus !== this.deviceStatus) {
          this.deviceStatus = newStatus;
          this.emit("deviceStatus", this.deviceStatus);
        }
      } catch (error) {
        if (this.deviceStatus !== "error") {
          this.deviceStatus = "error";
          this.emit("deviceStatus", "error");
        }
      }
    }, this.config.connectionCheckInterval);
  }

  async checkDeviceConnection(): Promise<boolean> {
    try {
      const { stdout } = await execAsync("adb devices");

      // Split output into lines and remove the first line (which is just "List of devices attached")
      const lines = stdout.trim().split("\n").slice(1);

      // Check if there are any devices and if they are in "device" state
      // A properly connected device will show as "<serial>\tdevice"
      const connectedDevices = lines.filter((line) => {
        const [_, state] = line.trim().split("\t");
        return state === "device"; // Only count devices in full "device" state
      });

      const isConnected = connectedDevices.length > 0;
      // console.log("IS CAMERA CONNECTED: ", isConnected);
      // console.log("Connected devices:", connectedDevices);

      return isConnected;
    } catch (error) {
      this.emit("error", new Error("Failed to check device connection"));
      return false;
    }
  }

  private async retryOperation<T>(
    operation: () => Promise<T>,
    retryCount: number = 0
  ): Promise<T> {
    try {
      return await operation();
    } catch (error) {
      if (retryCount >= this.config.maxRetries) {
        throw error;
      }

      await new Promise((resolve) =>
        setTimeout(resolve, this.config.retryDelay)
      );
      return this.retryOperation(operation, retryCount + 1);
    }
  }

  public async handleCaptureRequest(
    callback: (error?: Error, result?: string) => void
  ): Promise<void> {
    try {
      const filepath = await this.retryOperation(() => this.takePhoto());
      callback(undefined, filepath);
    } catch (error) {
      const enhancedError = this.enhanceError(error);
      this.emit("error", enhancedError);
      callback(enhancedError);
    }
  }

  private enhanceError(error: unknown): Error {
    if (error instanceof Error) {
      return error;
    }

    if (typeof error === "string") {
      return new Error(error);
    }

    return new Error("Unknown camera error occurred");
  }

  private async findPhotoPath(): Promise<string> {
    // Cache the camera path for the entire session
    if (this.cameraPath) {
      return this.cameraPath;
    }

    console.log("📁 Finding camera directory (one-time operation)...");

    try {
      // Store the UUID for the session
      const { stdout: storage } = await execAsync(
        'adb shell "sm list-volumes"'
      );
      const match = storage.match(/public.*?mounted\s+([A-F0-9-]+)/i);

      if (!match) {
        throw new Error("Could not find storage UUID");
      }

      this.cameraPath = `/storage/${match[1]}/DCIM/Camera`;
      await execAsync(`adb shell "ls -d ${this.cameraPath}"`);

      return this.cameraPath;
    } catch (error) {
      console.error("❌ Storage volume method failed:", error);
      throw error;
    }
  }

  private async getCurrentPhotos(): Promise<string[]> {
    const now = Date.now();
    if (now - this.lastPhotoCheck < this.photoCheckInterval) {
      return this.lastPhotoList;
    }

    this.lastPhotoCheck = now;

    try {
      // Use a more efficient command that only gets jpg files
      const { stdout } = await execAsync(
        `adb shell "cd ${await this.findPhotoPath()} && ls -t *.jpg 2>/dev/null | head -n 1"`
      );

      const latestPhoto = stdout.trim();
      if (latestPhoto) {
        const fullPath = `${this.cameraPath}/${latestPhoto}`;
        this.lastPhotoList = [fullPath];
        return [fullPath];
      }

      return this.lastPhotoList;
    } catch (error) {
      return this.lastPhotoList;
    }
  }

  private async waitForNewPhoto(): Promise<string | null> {
    const startTime = Date.now();
    const timeout = 3000; // Reduced from 5000ms

    const initialPhoto = (await this.getCurrentPhotos())[0];
    let checkCount = 0;

    while (Date.now() - startTime < timeout) {
      checkCount++;
      const currentPhoto = (await this.getCurrentPhotos())[0];

      if (
        currentPhoto &&
        currentPhoto !== initialPhoto &&
        currentPhoto !== this.lastKnownPhoto
      ) {
        console.log(
          `✅ New photo detected after ${checkCount} checks:`,
          currentPhoto
        );
        this.lastKnownPhoto = currentPhoto;
        return currentPhoto;
      }

      await new Promise((resolve) =>
        setTimeout(resolve, this.photoCheckInterval)
      );
    }

    return null;
  }

  async takePhoto(): Promise<string> {
    if (this.isCapturing) {
      throw new Error("Camera is busy capturing an image");
    }

    console.log("📸 Starting photo capture process...");

    this.isCapturing = true;
    const timestamp = Date.now();
    const filename = `photo_${timestamp}.jpg`;
    const filepath = path.join(this.config.photosDir, filename);

    try {
      // Get initial state
      const initialPhoto = (await this.getCurrentPhotos())[0];
      this.lastPhotoList = initialPhoto ? [initialPhoto] : [];

      // Trigger capture
      await execAsync("adb shell input keyevent KEYCODE_CAMERA");

      // Wait for new photo
      const newPhoto = await this.waitForNewPhoto();
      if (!newPhoto) {
        throw new Error("No new photo detected after capture");
      }

      // Pull the file
      await execAsync(`adb pull "${newPhoto}" "${filepath}"`);

      // Quick validation
      const stats = await fs.stat(filepath);
      if (stats.size < 1000) {
        throw new Error("Captured photo appears to be corrupt");
      }

      this.isCapturing = false;
      this.emit("photoTaken", filepath);

      return filepath;
    } catch (error) {
      this.isCapturing = false;
      throw error instanceof Error ? error : new Error("Unknown camera error");
    }
  }
}
