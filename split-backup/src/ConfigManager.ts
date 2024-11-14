import fs from "fs/promises";
import path from "path";
import { ClassName, EjectionSettings, PresetSettings } from "./types";
import { DEFAULT_EJECTION_CONFIG } from "./ejection-config";

export class ConfigurationManager {
  private configPath: string;
  private config: EjectionSettings;

  constructor(configFileName: string = "ejection-config.json") {
    this.configPath = path.join(process.cwd(), "config", configFileName);
    this.config = DEFAULT_EJECTION_CONFIG;
  }

  public static async create(
    configFileName: string = "ejection-config.json"
  ): Promise<ConfigurationManager> {
    const manager = new ConfigurationManager(configFileName);
    await manager.initialize();
    return manager;
  }

  public async initialize(): Promise<void> {
    try {
      // Ensure config directory exists
      const configDir = path.dirname(this.configPath);
      await fs.mkdir(configDir, { recursive: true });

      // Try to load existing config
      try {
        const fileContent = await fs.readFile(this.configPath, "utf-8");
        this.config = JSON.parse(fileContent);
        console.log("📖 Loaded existing configuration");
      } catch (error) {
        // If file doesn't exist or is invalid, save default config
        await this.saveConfig(DEFAULT_EJECTION_CONFIG);
        console.log("📝 Created new configuration file with defaults");
      }
    } catch (error) {
      console.error("Error initializing configuration:", error);
      throw new Error("Failed to initialize configuration");
    }
  }

  public async saveConfig(newConfig: EjectionSettings): Promise<void> {
    try {
      this.config = newConfig;
      await fs.writeFile(
        this.configPath,
        JSON.stringify(newConfig, null, 2),
        "utf-8"
      );
      console.log("💾 Configuration saved successfully");
    } catch (error) {
      console.error("Error saving configuration:", error);
      throw new Error("Failed to save configuration");
    }
  }

  public async updateConfig(
    partialConfig: Partial<EjectionSettings>
  ): Promise<void> {
    const updatedConfig = {
      ...this.config,
      ...partialConfig,
      globalSettings: {
        ...this.config.globalSettings,
        ...(partialConfig.globalSettings || {}),
      },
      perClassSettings: {
        ...this.config.perClassSettings,
        ...(partialConfig.perClassSettings || {}),
      },
      advancedSettings: {
        ...this.config.advancedSettings,
        ...(partialConfig.advancedSettings || {}),
      },
    };

    await this.saveConfig(updatedConfig);
  }

  public async applyPreset(preset: PresetSettings): Promise<void> {
    const presetConfigs: Record<PresetSettings, Partial<EjectionSettings>> = {
      High: {
        globalSettings: {
          requireMultipleDefects: false,
          minTotalArea: 100,
          maxDefectsBeforeEject: 1,
          ejectionDuration: 1000,
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
  }

  public getConfig(): EjectionSettings {
    return { ...this.config };
  }

  public async backup(): Promise<void> {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const backupPath = path.join(
      process.cwd(),
      "config",
      "backups",
      `ejection-config-${timestamp}.json`
    );

    try {
      await fs.mkdir(path.dirname(backupPath), { recursive: true });
      await fs.copyFile(this.configPath, backupPath);
      console.log(`📦 Configuration backed up to ${backupPath}`);
    } catch (error) {
      console.error("Error backing up configuration:", error);
      throw new Error("Failed to backup configuration");
    }
  }
}
