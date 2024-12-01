// src/SensorController.ts
import { EventEmitter } from "events";
import { IGpio, SystemState } from "../types";
import { PISTON_PIN, RISER_PIN, SENSOR1_PIN } from "../config/DEFAULT_CONFIG";
import { ConfigurationManager, stateManager } from "../config/ConfigManager";
import lodash from "lodash";
import { CameraController } from "../camera-controller";

export class SensorController extends EventEmitter {
  private sensor1: IGpio;
  private piston: IGpio;
  private riser: IGpio;
  private sensor1ActiveTime: number | null = null;
  private pistonActivationTime: number | null = null;
  private pistonRetractTime: number | null = null;
  private riserActivationTime: number | null = null;
  private validCycleInProgress: boolean = false;
  private configManager: ConfigurationManager | null = null;
  private lastSensorValue: number = -1;
  private cameraController: CameraController;

  constructor(
    gpioFactory: (pin: number, direction: string, edge?: string) => IGpio,
    private readonly sensor1ActivationTime: number = 300,
    configManager: ConfigurationManager,
    cameraController: CameraController
  ) {
    super();
    this.cameraController = cameraController;
    this.initializePins(gpioFactory);
    this.monitorSensors();
    this.configManager = configManager;
  }

  private initializePins(
    gpioFactory: (
      pin: number,
      direction: string,
      edge?: string,
      name?: string
    ) => IGpio
  ): void {
    try {
      const state = stateManager.getState();
      console.log(state);

      // Initialize GPIO pins
      this.sensor1 = gpioFactory(SENSOR1_PIN, "in", "both", "sensor1");
      this.piston = gpioFactory(PISTON_PIN, "out", null, "piston");
      this.riser = gpioFactory(RISER_PIN, "out", null, "riser");

      // Set initial states for actuators
      this.piston.writeSync(0);
      this.riser.writeSync(0);

      // Update initial states
      stateManager.setSensor1Active(this.sensor1.readSync() === 1);
      stateManager.setPistonActive(false);
      stateManager.setRiserActive(false);

      this.emitSystemLog("Initial system state set");
      this.setupSensorWatchers();
    } catch (error) {
      this.emitAlert("error", "Failed to initialize pins", error);
      throw error;
    }
  }

  private setupSensorWatchers(): void {
    // Create a debounced function for handling sensor changes
    const handleSensorChange = lodash.debounce(
      (value: number) => {
        if (value !== this.lastSensorValue) {
          const previousValue = this.lastSensorValue;
          this.lastSensorValue = value;
          const isActive = value === 1;

          this.emitSystemLog("Debounced sensor value changed", {
            previousValue,
            newValue: value,
            isActive,
            timestamp: new Date().toISOString(),
          });

          // console.log(
          //   `Sensor 1 value changed to: ${value} at ${new Date().toISOString()}`
          // );
          stateManager.setSensor1Active(isActive);
        }
      },
      50,
      {
        // Wait for 50ms of stability before triggering
        leading: false, // Don't trigger on the leading edge
        trailing: true, // Trigger on the trailing edge
        maxWait: 100, // Maximum time to wait before forcing an update
      }
    );

    // Watch for sensor changes
    this.sensor1.watch((err, value) => {
      if (err) {
        this.emitAlert("error", "Sensor 1 error", err);
        return;
      }

      // Pass the value to our debounced handler
      handleSensorChange(value);
    });
  }

  private monitorSensors(): void {
    setInterval(() => {
      try {
        const currentTime = Date.now();
        const state = stateManager.getState();
        const sensor1Active = state.sensor1.active;

        // Handle initial sensor1 activation
        if (sensor1Active && !this.sensor1ActiveTime) {
          this.emitSystemLog("Sensor 1 activation started");
          this.sensor1ActiveTime = currentTime;
          this.validCycleInProgress = true;
          stateManager.setProcessing(true);
        }

        // Start piston activation after delay
        if (
          this.validCycleInProgress &&
          this.sensor1ActiveTime &&
          currentTime - this.sensor1ActiveTime >= this.sensor1ActivationTime &&
          !state.piston.active
        ) {
          this.activatePiston();
        }

        // Monitor for piston completion based on time
        if (
          state.piston.active &&
          !sensor1Active &&
          this.pistonActivationTime &&
          currentTime - this.pistonActivationTime >=
            this.configManager?.getConfig()?.globalSettings.pistonDuration
        ) {
          this.handlePistonComplete();
        }

        // Monitor for riser completion based on time
        if (
          state.riser.active &&
          this.riserActivationTime &&
          currentTime - this.riserActivationTime >=
            this.configManager?.getConfig()?.globalSettings.riserDuration
        ) {
          this.handleRiserComplete();
        }

        // Reset cycle if sensor1 deactivates without starting sequence
        if (
          !sensor1Active &&
          this.sensor1ActiveTime &&
          !state.piston.active &&
          !state.riser.active
        ) {
          this.resetCycle();
        }
      } catch (error) {
        this.emitAlert("error", "Sensor monitoring error", error);
      }
    }, 50);
  }

  private activatePiston(): void {
    try {
      this.piston.writeSync(1);
      this.pistonActivationTime = Date.now();
      stateManager.setPistonActive(true);
      this.emitSystemLog("Piston activated");
    } catch (error) {
      this.emitAlert("error", "Failed to activate piston", error);
    }
  }

  public handleCaptureComplete(success: boolean): void {
    if (success) {
      this.emitSystemLog("Image capture and analysis completed successfully");
    } else {
      this.emitSystemLog("Image capture or analysis failed");
    }
    this.deactivateRiserAndReset();
  }

  private async handlePistonComplete(): Promise<void> {
    try {
      // Deactivate piston
      this.piston.writeSync(0);
      this.pistonActivationTime = null;
      this.pistonRetractTime = Date.now();
      stateManager.setPistonActive(false);
      this.emitSystemLog("Piston retraction started");

      // Wait for piston retraction before proceeding
      await this.waitForPistonRetraction();
    } catch (error) {
      this.emitAlert("error", "Failed to handle piston completion", error);
      this.invalidateCycle();
    }
  }

  private handleRiserComplete(): void {
    try {
      this.emit("readyForCapture");
    } catch (error) {
      this.emitAlert("error", "Failed to handle riser completion", error);
      this.deactivateRiserAndReset();
    }
  }

  private deactivateRiserAndReset(): void {
    try {
      this.riser.writeSync(0);
      this.riserActivationTime = null;
      stateManager.setRiserActive(false);
      this.emitSystemLog("Riser deactivated");

      setTimeout(() => {
        this.resetCycle();
      }, 1000);
    } catch (error) {
      this.emitAlert("error", "Failed to deactivate riser", error);
      this.resetCycle();
    }
  }

  private async waitForPistonRetraction(): Promise<void> {
    // Wait for piston retraction (e.g., 500ms or configured time)
    const retractionDelay = 500;

    await new Promise((resolve) => setTimeout(resolve, retractionDelay));

    // Check camera connection before activating riser
    try {
      const isCameraConnected =
        await this.cameraController.checkDeviceConnection();

      console.log(isCameraConnected);

      if (!isCameraConnected) {
        this.emitAlert("error", "Camera not connected, aborting cycle");
        this.invalidateCycle();
        return;
      }

      // Only proceed with riser activation if camera is connected
      this.activateRiser();
    } catch (error) {
      this.emitAlert("error", "Failed to check camera connection", error);
      this.invalidateCycle();
    }
  }

  private activateRiser(): void {
    try {
      this.riser.writeSync(1);
      this.riserActivationTime = Date.now();
      this.pistonRetractTime = null;
      stateManager.setRiserActive(true);
      this.emitSystemLog(
        "Riser activated after successful piston retraction and camera check"
      );
    } catch (error) {
      this.emitAlert("error", "Failed to activate riser", error);
      this.invalidateCycle();
    }
  }

  private resetCycle(): void {
    this.sensor1ActiveTime = null;
    this.pistonActivationTime = null;
    this.riserActivationTime = null;
    this.validCycleInProgress = false;
    stateManager.setProcessing(false);
    console.log("reset cycle");
    stateManager.setSensor1Active(false);
    this.emitSystemLog("Cycle reset");
  }

  public invalidateCycle(): void {
    try {
      this.piston.writeSync(0);
      this.riser.writeSync(0);
      stateManager.setPistonActive(false);
      stateManager.setRiserActive(false);
      this.resetCycle();
      this.emitSystemLog("Cycle invalidated");
    } catch (error) {
      this.emitAlert("error", "Failed to invalidate cycle", error);
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

  public cleanup(): void {
    this.emitSystemLog("Starting system cleanup");
    this.sensor1.unexport();
    this.piston.unexport();
    this.riser.unexport();
    this.emitSystemLog("System cleanup completed");
  }
}
