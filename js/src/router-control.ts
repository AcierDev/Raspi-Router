import { EventEmitter } from "events";
import { IGpio } from "./gpio-factory";

interface SystemState {
  sensor1: boolean;
  sensor2: boolean;
  solenoid: boolean;
  isProcessing: boolean;
  isCapturingImage: boolean;
}

export class RouterController extends EventEmitter {
  private sensor1: IGpio;
  private sensor2: IGpio;
  private solenoid: IGpio;
  private sensor1ActiveTime: number | null = null;
  private solenoidTimeout: NodeJS.Timeout | null = null;
  private monitorInterval: NodeJS.Timer;
  private isCapturingImage = false;
  private hasDisplayedWaitAlert = false;
  private validCycleInProgress: boolean = false;

  private systemState: SystemState = {
    sensor1: false,
    sensor2: false,
    solenoid: false,
    isProcessing: false,
    isCapturingImage: false,
  };

  private previousStates = {
    sensor1: 0,
    sensor2: 0,
    solenoid: 0,
  };

  constructor(
    gpioFactory: (pin: number, direction: string, edge?: string) => IGpio,
    private readonly sensor1Pin: number = 14,
    private readonly sensor2Pin: number = 15,
    private readonly solenoidPin: number = 18,
    private readonly sensor1ActivationTime: number = 300,
    private readonly solenoidDeactivationDelay: number = 500
  ) {
    super();
    this.initializePins(gpioFactory);
    this.emitSystemLog("Router Controller initialized", {
      sensor1Pin,
      sensor2Pin,
      solenoidPin,
      sensor1ActivationTime,
      solenoidDeactivationDelay,
    });
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

    if (previousState.isCapturingImage !== this.systemState.isCapturingImage) {
      this.hasDisplayedWaitAlert = false;
    }

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
    this.monitorInterval = setInterval(() => {
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
          this.isCapturingImage = true;
          this.updateSystemState({ isCapturingImage: true });
          this.emit("startImageCapture");
          this.emitSystemLog("Image capture initiated");
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

  private async handleImageCapture(): Promise<void> {
    if (this.isCapturingImage) return; // Prevent concurrent captures

    try {
      this.isCapturingImage = true;
      this.updateSystemState({ isCapturingImage: true });

      // Convert event emission to Promise
      const result = await new Promise((resolve, reject) => {
        this.emit("startImageCapture", (error?: Error, filepath?: string) => {
          if (error) reject(error);
          else resolve(filepath);
        });
      });

      this.imageCaptureComplete(true);
      this.emitSystemLog("Image capture completed successfully", { result });
    } catch (error) {
      this.emitAlert(
        "error",
        error instanceof Error ? error.message : "Camera error"
      );
      this.imageCaptureComplete(false);
      this.emitSystemLog("Image capture failed", { error });

      // Add delay before allowing next capture attempt
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
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
    clearInterval(this.monitorInterval);
    this.sensor1.unexport();
    this.sensor2.unexport();
    this.solenoid.unexport();
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
