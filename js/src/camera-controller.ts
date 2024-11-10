import EventEmitter from "events";
import { exec } from "child_process";
import { promisify } from "util";
import fs from "fs/promises";
import path from "path";
import { RouterController } from "./router-control";

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
  private lastConnectionCheck: number = 0;
  private reconnectAttempts: number = 0;
  private deviceStatus: "connected" | "disconnected" | "error" = "disconnected";

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
      await this.startDeviceMonitoring();
    } catch (error) {
      this.emit("error", new Error("Failed to initialize camera controller"));
    }
  }

  private async startDeviceMonitoring(): Promise<void> {
    setInterval(async () => {
      try {
        const isConnected = await this.checkDeviceConnection();
        const newStatus = isConnected ? "connected" : "disconnected";

        if (newStatus !== this.deviceStatus) {
          this.deviceStatus = newStatus;
          this.emit("deviceStatus", this.deviceStatus);
        }
      } catch (error) {
        this.deviceStatus = "error";
        this.emit("deviceStatus", "error");
      }
    }, this.config.connectionCheckInterval);
  }

  private async waitForDevice(timeout: number = 10000): Promise<boolean> {
    const startTime = Date.now();
    while (Date.now() - startTime < timeout) {
      if (await this.checkDeviceConnection()) {
        return true;
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    return false;
  }

  async checkDeviceConnection(): Promise<boolean> {
    try {
      const { stdout } = await execAsync("adb devices");
      const isConnected = stdout.includes("device");

      if (isConnected) {
        this.reconnectAttempts = 0;
      }

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
    try {
      // Get storage volumes to find SD card UUID
      const { stdout: storage } = await execAsync(
        'adb shell "sm list-volumes"'
      );
      console.log("Storage volumes:", storage);

      // Parse the UUID from the public volume
      const publicVolume = storage
        .split("\n")
        .find((line) => line.includes("public:"));

      if (!publicVolume) {
        throw new Error("Could not find public storage volume");
      }

      const match = publicVolume.match(/mounted\s+([A-F0-9-]+)/i);
      if (!match) {
        throw new Error("Could not parse storage UUID");
      }

      const uuid = match[1];
      const cameraPath = `/storage/${uuid}/DCIM/Camera`;

      console.log(`Using camera path: ${cameraPath}`);

      // Verify the path exists
      const { stdout: pathCheck } = await execAsync(
        `adb shell "ls -la ${cameraPath}"`
      );
      if (!pathCheck) {
        throw new Error(`Camera path ${cameraPath} not accessible`);
      }

      return cameraPath;
    } catch (error) {
      console.error("Error finding photo path:", error);
      throw error;
    }
  }

  private async executeCameraCommand(filepath: string): Promise<void> {
    try {
      const cameraPath = await this.findPhotoPath();
      console.log("Using camera path:", cameraPath);

      // Get initial file list
      const { stdout: initialFiles } = await execAsync(
        `adb shell "ls -la ${cameraPath}"`
      );
      console.log("Initial files in camera directory:", initialFiles);

      // Start camera app
      console.log("Starting camera app...");
      await Promise.race([
        execAsync(
          "adb shell am start -a android.media.action.STILL_IMAGE_CAPTURE"
        ),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error("Camera start timeout")), 5000)
        ),
      ]);

      // Wait for camera to stabilize
      await new Promise((resolve) => setTimeout(resolve, 2000));

      // Take photo
      console.log("Taking photo...");
      await Promise.race([
        execAsync("adb shell input keyevent KEYCODE_CAMERA"),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error("Shutter timeout")), 3000)
        ),
      ]);

      // Wait for photo to be saved
      console.log("Waiting for photo to be saved...");
      await new Promise((resolve) => setTimeout(resolve, 4000));

      // Get list of files sorted by modification time
      const { stdout: newMostRecent } = await execAsync(
        `adb shell "ls -t ${cameraPath} | head -n 1"`
      );
      const latestPhoto = newMostRecent.trim();

      if (!latestPhoto) {
        throw new Error("No photos found after capture");
      }

      console.log("Most recent photo:", latestPhoto);

      // Pull the file
      const fullPath = `${cameraPath}/${latestPhoto}`;
      console.log(`Pulling file from: ${fullPath}`);
      await execAsync(`adb pull "${fullPath}" "${filepath}"`);

      // Verify the transfer
      await this.verifyPhotoCapture(filepath);
    } catch (error) {
      console.error("Error in executeCameraCommand:", error);
      throw error;
    }
  }

  async takePhoto(): Promise<string> {
    if (this.isCapturing) {
      throw new Error("Camera is busy capturing an image");
    }

    if (!(await this.waitForDevice())) {
      throw new Error("Camera device not connected or not responding");
    }

    this.isCapturing = true;
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const filename = `photo_${timestamp}.jpg`;
    const filepath = path.join(this.config.photosDir, filename);

    try {
      console.log("Starting photo capture process...");

      // Kill any existing camera processes
      await execAsync("adb shell am force-stop com.android.camera");
      await execAsync("adb shell am force-stop com.android.camera2");

      // Ensure camera path exists
      const cameraPath = await this.findPhotoPath();
      await execAsync(`adb shell "mkdir -p ${cameraPath}"`);

      // Take the photo
      await this.executeCameraCommand(filepath);

      this.isCapturing = false;
      this.emit("photoTaken", filepath);
      return filepath;
    } catch (error) {
      this.isCapturing = false;
      throw this.enhanceError(error);
    }
  }

  private async verifyPhotoCapture(filepath: string): Promise<void> {
    try {
      const stats = await fs.stat(filepath);
      if (stats.size < 1000) {
        // Photo should be at least 1KB
        throw new Error("Captured photo appears to be corrupt or incomplete");
      }

      // Try to verify it's a valid JPEG
      const buffer = await fs.readFile(filepath, { flag: "r" });
      if (buffer[0] !== 0xff || buffer[1] !== 0xd8) {
        // JPEG magic numbers
        throw new Error("File is not a valid JPEG image");
      }
    } catch (error) {
      if (error instanceof Error) {
        throw new Error(`Failed to verify photo capture: ${error.message}`);
      }
      throw new Error("Failed to verify photo capture");
    }
  }
}
