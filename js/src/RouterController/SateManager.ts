// src/StateManager.ts
import { EventEmitter } from "events";
import fs from "fs/promises";
import path from "path";
import { SystemState } from "../types";

export class StateManager extends EventEmitter {
  private state: SystemState = {
    sensor1: {
      active: false,
    },
    piston: {
      active: false,
    },
    ejector: {
      active: false,
    },
    riser: {
      active: false,
    },
    isProcessing: false,
    isCapturingImage: false,
    lastPhotoPath: null,
    deviceConnected: false,
  };

  private readonly statePath: string;

  constructor() {
    super();
    this.statePath = path.join(process.cwd(), "config", "system-state.json");
  }

  public async initialize(): Promise<void> {
    try {
      // Try to load saved state
      try {
        const savedState = await this.loadState();
        this.state = {
          ...savedState,
          // Reset volatile states on startup
          isProcessing: false,
          isCapturingImage: false,
          sensor1: { ...savedState.sensor1, active: false },
          piston: { ...savedState.piston, active: false },
          riser: { ...savedState.riser, active: false },
          ejector: { ...savedState.ejector, active: false },
        };
      } catch (error) {
        console.log("No saved state found, using defaults");
      }

      // Ensure state directory exists
      await fs.mkdir(path.dirname(this.statePath), { recursive: true });

      // Save initial state
      await this.saveState();
    } catch (error) {
      console.error("Failed to initialize state manager:", error);
      throw error;
    }
  }

  private async loadState(): Promise<SystemState> {
    const data = await fs.readFile(this.statePath, "utf-8");
    return JSON.parse(data);
  }

  private async saveState(): Promise<void> {
    await fs.writeFile(
      this.statePath,
      JSON.stringify(this.state, null, 2),
      "utf-8"
    );
  }

  public getState(): SystemState {
    return { ...this.state };
  }

  public async updateState(
    updates: Partial<SystemState>,
    source?: string
  ): Promise<void> {
    const previousState = { ...this.state };
    this.state = { ...this.state, ...updates };

    // Handle specific state changes
    if (
      updates.sensor1?.active !== undefined &&
      updates.sensor1.active !== previousState.sensor1?.active
    ) {
      this.emit("sensor1StateChange", updates.sensor1.active);
    }

    if (
      updates.isProcessing !== undefined &&
      updates.isProcessing !== previousState.isProcessing
    ) {
      this.emit("processingStateChange", updates.isProcessing);
    }

    // Save state for persistent values
    if (this.shouldPersistState(updates)) {
      await this.saveState();
    }

    // Emit general state update event
    this.emit("stateUpdate", this.state, source);
  }

  private shouldPersistState(updates: Partial<SystemState>): boolean {
    // Define which state properties should be persisted
    const persistentKeys = ["lastPhotoPath", "deviceConnected"];
    return Object.keys(updates).some((key) => persistentKeys.includes(key));
  }

  // Helper methods for specific state updates
  public async setSensor1Active(active: boolean): Promise<void> {
    await this.updateState(
      {
        sensor1: { ...this.state.sensor1, active },
      },
      "sensor1"
    );
  }

  public async setPistonActive(active: boolean): Promise<void> {
    await this.updateState(
      {
        piston: { ...this.state.piston, active },
      },
      "piston"
    );
  }

  public async setRiserActive(active: boolean): Promise<void> {
    await this.updateState(
      {
        riser: { ...this.state.riser, active },
      },
      "riser"
    );
  }

  public async setEjectorActive(active: boolean): Promise<void> {
    await this.updateState(
      {
        ejector: { ...this.state.ejector, active },
      },
      "ejector"
    );
  }

  public async setProcessing(isProcessing: boolean): Promise<void> {
    await this.updateState({ isProcessing }, "processing");
  }

  public async setCapturingImage(isCapturing: boolean): Promise<void> {
    await this.updateState({ isCapturingImage: isCapturing }, "camera");
  }

  public async setDeviceConnected(connected: boolean): Promise<void> {
    await this.updateState({ deviceConnected: connected }, "camera");
  }

  public async setLastPhotoPath(path: string | null): Promise<void> {
    await this.updateState({ lastPhotoPath: path }, "camera");
  }
}
