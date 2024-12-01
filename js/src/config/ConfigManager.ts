// src/config/ConfigManager.ts
import { EventEmitter } from "events";
import fs from "fs/promises";
import path from "path";
import { ClassName, RouterSettings, PresetSettings } from "../types";
import { DEFAULT_EJECTION_CONFIG } from "./DEFAULT_CONFIG";
import { StateManager } from "../RouterController/SateManager";

export class ConfigurationManager extends EventEmitter {
  private config: RouterSettings = DEFAULT_EJECTION_CONFIG;
  private readonly configPath: string;

  constructor() {
    super();
    this.configPath = path.join(
      process.cwd(),
      "config",
      "ejection-config.json"
    );
  }

  public async initialize(): Promise<void> {
    try {
      // Try to load saved config
      try {
        const savedConfig = await this.loadConfig();
        this.config = savedConfig;
      } catch (error) {
        console.log("No saved config found, using defaults");
        this.config = DEFAULT_EJECTION_CONFIG;
      }

      // Ensure config directory exists
      await fs.mkdir(path.dirname(this.configPath), { recursive: true });

      // Save initial config
      await this.saveConfig();
    } catch (error) {
      console.error("Failed to initialize config manager:", error);
      throw error;
    }
  }

  private async loadConfig(): Promise<RouterSettings> {
    const data = await fs.readFile(this.configPath, "utf-8");
    return JSON.parse(data);
  }

  private async saveConfig(): Promise<void> {
    await fs.writeFile(
      this.configPath,
      JSON.stringify(this.config, null, 2),
      "utf-8"
    );
  }

  public getConfig(): RouterSettings {
    return { ...this.config };
  }

  public async updateConfig(updates: Partial<RouterSettings>): Promise<void> {
    this.config = { ...this.config, ...updates };
    await this.saveConfig();
    this.emit("configUpdate", this.config);
  }

  public async applyPreset(preset: PresetSettings): Promise<void> {
    const presetConfigs: Record<PresetSettings, Partial<RouterSettings>> = {
      High: {
        globalSettings: {
          requireMultipleDefects: false,
          minTotalArea: 100,
          maxDefectsBeforeEject: 1,
          ejectionDuration: 1000,
          riserDuration: 2000,
          pistonDuration: 5000,
        },
        perClassSettings: Object.fromEntries(
          Object.keys(this.config.perClassSettings).map((key) => [
            key,
            { enabled: true, minConfidence: 0.7, minArea: 50, maxCount: 1 },
          ])
        ) as Record<
          string,
          {
            enabled: boolean;
            minConfidence: number;
            minArea: number;
            maxCount: number;
          }
        >,
      },
      Medium: {
        globalSettings: {
          requireMultipleDefects: false,
          minTotalArea: 200,
          maxDefectsBeforeEject: 2,
          ejectionDuration: 1000,
          riserDuration: 2000,
          pistonDuration: 5000,
        },
        perClassSettings: Object.fromEntries(
          Object.keys(this.config.perClassSettings).map((key) => [
            key,
            { enabled: true, minConfidence: 0.8, minArea: 100, maxCount: 2 },
          ])
        ) as Record<
          ClassName,
          {
            enabled: boolean;
            minConfidence: number;
            minArea: number;
            maxCount: number;
          }
        >,
      },
      Low: {
        globalSettings: {
          requireMultipleDefects: true,
          minTotalArea: 300,
          maxDefectsBeforeEject: 3,
          ejectionDuration: 1000,
          riserDuration: 2000,
          pistonDuration: 5000,
        },
        perClassSettings: Object.fromEntries(
          Object.keys(this.config.perClassSettings).map((key) => [
            key,
            { enabled: true, minConfidence: 0.9, minArea: 150, maxCount: 3 },
          ])
        ) as Record<
          ClassName,
          {
            enabled: boolean;
            minConfidence: number;
            minArea: number;
            maxCount: number;
          }
        >,
      },
    };

    await this.updateConfig(presetConfigs[preset]);

    await this.saveConfig();
    this.emit("configUpdate", this.config);
  }
}

// Export singleton instances
export const stateManager = new StateManager();
export const configManager = new ConfigurationManager();
