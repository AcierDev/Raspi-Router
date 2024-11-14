import EventEmitter from "events";
import { IGpio, ISensorMonitor } from "./types";
import { RouterController } from "./router-control";

// SensorMonitor.ts
export class SensorMonitor extends EventEmitter implements ISensorMonitor {
  private sensor1ActiveTime: number | null = null;
  private solenoidTimeout: NodeJS.Timeout | null = null;
  private validCycleInProgress: boolean = false;

  constructor(
    private sensor1: IGpio,
    private sensor2: IGpio,
    private solenoid: IGpio,
    private controller: RouterController,
    private readonly sensor1ActivationTime: number = 300,
    private readonly solenoidDeactivationDelay: number = 500
  ) {
    super();
    this.setupSensorWatchers();
  }

  private setupSensorWatchers(): void {
    this.sensor1.watch((err, value) => {
      if (err) {
        this.emit("error", { sensor: "sensor1", error: err });
        return;
      }
      const isActive = value === 1;
      this.controller.updateState({ sensor1: isActive });
      this.emit("log", `Sensor 1 ${isActive ? "activated" : "deactivated"}`);
    });

    this.sensor2.watch((err, value) => {
      if (err) {
        this.emit("error", { sensor: "sensor2", error: err });
        return;
      }
      const isActive = value === 1;
      this.controller.updateState({ sensor2: isActive });
      this.emit("log", `Sensor 2 ${isActive ? "activated" : "deactivated"}`);
    });
  }

  startMonitoring(): void {
    setInterval(() => {
      try {
        const currentTime = Date.now();
        const sensor1Active = this.sensor1.readSync() === 1;
        const sensor2Active = this.sensor2.readSync() === 1;

        if (sensor1Active) {
          if (!this.sensor1ActiveTime) {
            this.emit("log", "Sensor 1 activation started");
            this.sensor1ActiveTime = currentTime;
            this.validCycleInProgress = true;
            this.controller.updateState({ isProcessing: true });
          }

          if (
            currentTime - this.sensor1ActiveTime >=
            this.sensor1ActivationTime
          ) {
            this.activateSolenoid();
          }
        } else {
          if (this.sensor1ActiveTime) {
            this.emit("log", "Sensor 1 deactivation process started");
            this.handleSensor1Deactivation();
          }
          this.sensor1ActiveTime = null;
        }

        if (sensor2Active && this.validCycleInProgress) {
          this.emit("sensor2Triggered");
        }
      } catch (error) {
        this.emit("error", { type: "monitoring", error });
      }
    }, 50);
  }

  private activateSolenoid(): void {
    try {
      if (!this.controller.getState().solenoid) {
        this.solenoid.writeSync(1);
        this.controller.updateState({ solenoid: true });
        this.emit("log", "Solenoid activated");
      }
    } catch (error) {
      this.emit("error", { type: "solenoid", error });
    }
  }

  private handleSensor1Deactivation(): void {
    if (this.solenoidTimeout) {
      clearTimeout(this.solenoidTimeout);
    }

    this.solenoidTimeout = setTimeout(() => {
      try {
        if (this.controller.getState().solenoid) {
          this.solenoid.writeSync(0);
          this.controller.updateState({
            solenoid: false,
            isProcessing: false,
          });
          this.emit("log", "Solenoid deactivated");
        }
        this.validCycleInProgress = false;
      } catch (error) {
        this.emit("error", { type: "solenoid", error });
      }
    }, this.solenoidDeactivationDelay);
  }

  cleanup(): void {
    if (this.solenoidTimeout) {
      clearTimeout(this.solenoidTimeout);
    }
    this.sensor1.unexport();
    this.sensor2.unexport();
    this.solenoid.unexport();
  }

  getSensor1State(): number {
    return this.sensor1.readSync();
  }

  getSensor2State(): number {
    return this.sensor2.readSync();
  }

  getSolenoidState(): number {
    return this.solenoid.readSync();
  }

  updateSensor1State(value: number): void {
    this.sensor1.writeSync(value);
  }

  updateSensor2State(value: number): void {
    this.sensor2.writeSync(value);
  }
}
