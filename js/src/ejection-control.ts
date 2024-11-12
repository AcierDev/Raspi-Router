import { EventEmitter } from "events";
import { IGpio } from "./gpio-factory";
import {
  DetectionResponse,
  EjectionSettings,
  Prediction,
  ClassName,
  PresetSettings,
} from "./types";
import { ConfigurationManager } from "./ConfigManager";

export class EjectionControl extends EventEmitter {
  private ejectionSolenoid: IGpio;
  private ejectionTimeout: NodeJS.Timeout | null = null;
  private config: EjectionSettings;
  private configManager: ConfigurationManager;

  constructor(
    gpioFactory: (pin: number, direction: string) => IGpio,
    pin: number,
    configManager: ConfigurationManager
  ) {
    super();
    this.ejectionSolenoid = gpioFactory(pin, "out");
    this.configManager = configManager;
    this.config = this.configManager.getConfig();
    this.ejectionSolenoid.writeSync(0);
    console.log(`[EjectionControl] Initialized with pin ${pin}`);
    console.log(
      "[EjectionControl] Initial config loaded:",
      JSON.stringify(this.config, null, 2)
    );
  }

  private calculateArea(bbox: number[]): number {
    const area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]);
    console.log(
      `[Area Calculation] BBox: ${JSON.stringify(bbox)} → Area: ${area}`
    );
    return area;
  }

  private isInRegionOfInterest(bbox: number[]): boolean {
    if (!this.config.advancedSettings.regionOfInterest) {
      console.log("[ROI Check] No ROI configured, allowing all regions");
      return true;
    }

    const roi = this.config.advancedSettings.regionOfInterest;
    const [x1, y1, x2, y2] = bbox;
    const isInside = !(
      x1 > roi.x + roi.width ||
      x2 < roi.x ||
      y1 > roi.y + roi.height ||
      y2 < roi.y
    );

    console.log(`[ROI Check] BBox ${JSON.stringify(bbox)}`);
    console.log(`[ROI Check] ROI: ${JSON.stringify(roi)}`);
    console.log(`[ROI Check] Is inside ROI: ${isInside}`);
    return isInside;
  }

  private calculateOverlap(predictions: Prediction[]): number {
    if (
      !this.config.advancedSettings.considerOverlap ||
      predictions.length < 2
    ) {
      console.log(
        "[Overlap] Overlap check skipped - disabled or insufficient predictions"
      );
      return 0;
    }

    let totalOverlap = 0;
    console.log(
      `[Overlap] Calculating overlap for ${predictions.length} predictions`
    );

    for (let i = 0; i < predictions.length; i++) {
      for (let j = i + 1; j < predictions.length; j++) {
        const box1 = Object.values(predictions[i].bbox);
        const box2 = Object.values(predictions[j].bbox);

        const xOverlap = Math.max(
          0,
          Math.min(box1[2], box2[2]) - Math.max(box1[0], box2[0])
        );
        const yOverlap = Math.max(
          0,
          Math.min(box1[3], box2[3]) - Math.max(box1[1], box2[1])
        );
        const overlap = xOverlap * yOverlap;
        totalOverlap += overlap;

        console.log(`[Overlap] Between prediction ${i} and ${j}:`);
        console.log(`  Box1: ${JSON.stringify(box1)}`);
        console.log(`  Box2: ${JSON.stringify(box2)}`);
        console.log(`  Overlap area: ${overlap}`);
      }
    }

    console.log(`[Overlap] Total overlap area: ${totalOverlap}`);
    return totalOverlap;
  }

  private checkClassMaxCount(predictions: Prediction[]): {
    exceeded: boolean;
    className?: ClassName;
    count?: number;
  } {
    console.log("[Class Count] Checking maximum count per class");
    const countByClass: { [key in ClassName]?: number } = {};

    for (const pred of predictions) {
      const className = pred.class_name as ClassName;
      countByClass[className] = (countByClass[className] || 0) + 1;

      const classConfig = this.config.perClassSettings[className];
      console.log(
        `[Class Count] ${className}: ${countByClass[className]} (max: ${
          classConfig.maxCount || "unlimited"
        })`
      );

      if (
        classConfig.maxCount &&
        countByClass[className]! > classConfig.maxCount
      ) {
        console.log(`[Class Count] Maximum count exceeded for ${className}`);
        return {
          exceeded: true,
          className,
          count: countByClass[className],
        };
      }
    }

    console.log("[Class Count] No class count limits exceeded");
    return { exceeded: false };
  }

  private checkGlobalCriteria(validPredictions: Prediction[]): {
    shouldEject: boolean;
    reason?: string;
    details?: any;
  } {
    console.log("[Global Criteria] Checking global ejection criteria");

    // Check maximum defects limit
    if (this.config.globalSettings.maxDefectsBeforeEject) {
      console.log(
        `[Max Defects] Checking max defects: ${validPredictions.length} (max: ${this.config.globalSettings.maxDefectsBeforeEject})`
      );
      if (
        validPredictions.length >=
        this.config.globalSettings.maxDefectsBeforeEject
      ) {
        return {
          shouldEject: true,
          reason: "Maximum defect count exceeded",
          details: {
            defectCount: validPredictions.length,
            threshold: this.config.globalSettings.maxDefectsBeforeEject,
          },
        };
      }
    }

    // Check multiple defects requirement
    if (this.config.globalSettings.requireMultipleDefects) {
      console.log(
        `[Multiple Defects] Checking multiple defects requirement (found: ${validPredictions.length})`
      );
      if (validPredictions.length >= 2) {
        return {
          shouldEject: true,
          reason: "Multiple defects detected",
          details: { defectCount: validPredictions.length },
        };
      }
    }

    // Check total area
    if (this.config.globalSettings.minTotalArea) {
      const totalArea = validPredictions.reduce(
        (sum, pred) => sum + this.calculateArea(Object.values(pred.bbox)),
        0
      );
      console.log(
        `[Total Area] Checking total area: ${totalArea} (min: ${this.config.globalSettings.minTotalArea})`
      );

      if (totalArea >= this.config.globalSettings.minTotalArea) {
        return {
          shouldEject: true,
          reason: "Total area threshold exceeded",
          details: {
            totalArea,
            threshold: this.config.globalSettings.minTotalArea,
          },
        };
      }
    }

    // Consider overlap if enabled
    if (this.config.advancedSettings.considerOverlap) {
      const overlapArea = this.calculateOverlap(validPredictions);
      if (overlapArea > 0) {
        return {
          shouldEject: true,
          reason: "Overlapping defects detected",
          details: { overlapArea },
        };
      }
    }

    return { shouldEject: false };
  }

  private checkPerClassCriteria(predictions: Prediction[]): {
    shouldEject: boolean;
    reason?: string;
    details?: any;
  } {
    console.log("[Per-Class Criteria] Checking per-class ejection criteria");

    // Check if any individual prediction meets its class-specific criteria
    for (const pred of predictions) {
      const className = pred.class_name as ClassName;
      const classConfig = this.config.perClassSettings[className];
      const area = this.calculateArea(Object.values(pred.bbox));

      console.log(`[Per-Class] Evaluating ${className}:`);
      console.log(
        `  Confidence: ${pred.confidence} (min: ${classConfig.minConfidence})`
      );
      console.log(`  Area: ${area} (min: ${classConfig.minArea || "none"})`);

      if (
        pred.confidence >= classConfig.minConfidence &&
        (!classConfig.minArea || area >= classConfig.minArea)
      ) {
        return {
          shouldEject: true,
          reason: `Class-specific criteria met for ${className}`,
          details: {
            className,
            confidence: pred.confidence,
            area,
            threshold: {
              confidence: classConfig.minConfidence,
              area: classConfig.minArea,
            },
          },
        };
      }
    }

    // Check class count limits
    const maxCountCheck = this.checkClassMaxCount(predictions);
    if (maxCountCheck.exceeded) {
      return {
        shouldEject: true,
        reason: `Maximum count exceeded for class ${maxCountCheck.className}`,
        details: {
          className: maxCountCheck.className,
          count: maxCountCheck.count,
          threshold:
            this.config.perClassSettings[maxCountCheck.className!].maxCount,
        },
      };
    }

    return { shouldEject: false };
  }

  public shouldEject(response: DetectionResponse): {
    shouldEject: boolean;
    reason: string;
    details: any;
  } {
    console.log("\n[Ejection Decision] Starting ejection decision process");
    console.log(
      `[Ejection Decision] Received ${response.data.predictions.length} predictions`
    );

    const { predictions } = response.data;
    if (predictions.length === 0) {
      return {
        shouldEject: false,
        reason: "No defects detected",
        details: null,
      };
    }

    // Filter predictions based on enabled classes and ROI
    console.log(
      "[Ejection Decision] Filtering predictions based on basic criteria"
    );
    const validPredictions = predictions.filter((pred) => {
      const className = pred.class_name as ClassName;
      const classConfig = this.config.perClassSettings[className];

      if (!classConfig || !classConfig.enabled) {
        console.log(
          `[Filter] ${className}: Rejected - Class disabled or not configured`
        );
        return false;
      }

      const meetsROI = this.isInRegionOfInterest(Object.values(pred.bbox));
      console.log(
        `[Filter] ${className} ROI check: ${meetsROI ? "PASS" : "FAIL"}`
      );

      return meetsROI;
    });

    if (validPredictions.length === 0) {
      return {
        shouldEject: false,
        reason: "No defects in valid regions",
        details: {
          totalPredictions: predictions.length,
          allRejected: true,
        },
      };
    }

    // Check both global and per-class criteria
    const globalCheck = this.checkGlobalCriteria(validPredictions);
    const perClassCheck = this.checkPerClassCriteria(validPredictions);

    // Eject if either global or per-class checks pass
    if (globalCheck.shouldEject || perClassCheck.shouldEject) {
      const primaryReason = globalCheck.shouldEject
        ? globalCheck
        : perClassCheck;
      return {
        shouldEject: true,
        reason: primaryReason.reason!,
        details: {
          ...primaryReason.details,
          globalCriteriaMet: globalCheck.shouldEject,
          perClassCriteriaMet: perClassCheck.shouldEject,
          validDefects: validPredictions.map((p) => ({
            class: p.class_name,
            confidence: p.confidence,
            area: this.calculateArea(Object.values(p.bbox)),
          })),
        },
      };
    }

    return {
      shouldEject: false,
      reason: "No ejection criteria met",
      details: {
        validPredictions: validPredictions.length,
        globalCriteriaMet: false,
        perClassCriteriaMet: false,
      },
    };
  }

  // Rest of the class methods remain unchanged
  public async activate(): Promise<void> {
    console.log("[Activation] Starting ejection cycle");
    try {
      this.ejectionSolenoid.writeSync(1);
      console.log("[Activation] Solenoid activated");
      this.emit("ejectionStarted");

      if (this.ejectionTimeout) {
        clearTimeout(this.ejectionTimeout);
        console.log("[Activation] Cleared existing timeout");
      }

      await new Promise<void>((resolve) => {
        console.log(
          `[Activation] Setting ejection duration: ${this.config.globalSettings.ejectionDuration}ms`
        );
        this.ejectionTimeout = setTimeout(() => {
          this.deactivate();
          resolve();
        }, this.config.globalSettings.ejectionDuration);
      });
    } catch (error) {
      console.error("[Activation] Error during activation:", error);
      this.emit("error", error);
      this.deactivate();
    }
  }

  private deactivate(): void {
    console.log("[Deactivation] Starting deactivation");
    try {
      this.ejectionSolenoid.writeSync(0);
      console.log("[Deactivation] Solenoid deactivated");
      this.emit("ejectionComplete");
    } catch (error) {
      console.error("[Deactivation] Error during deactivation:", error);
      this.emit("error", error);
    }
  }

  public async applyPreset(preset: PresetSettings): Promise<void> {
    console.log("[Config] Applying preset:", preset);
    try {
      await this.configManager.applyPreset(preset);
      this.config = this.configManager.getConfig();
      console.log("[Config] Preset applied successfully");
      this.emit("configUpdated", this.config);
    } catch (error) {
      console.error("[Config] Error applying preset:", error);
      this.emit("error", new Error(`Failed to apply preset: ${error}`));
      throw error;
    }
  }

  public async updateConfig(
    newConfig: Partial<EjectionSettings>
  ): Promise<void> {
    console.log(
      "[Config] Updating configuration:",
      JSON.stringify(newConfig, null, 2)
    );
    try {
      await this.configManager.updateConfig(newConfig);
      this.config = this.configManager.getConfig();
      console.log("[Config] Configuration updated successfully");
      this.emit("configUpdated", this.config);
    } catch (error) {
      console.error("[Config] Error updating configuration:", error);
      this.emit("error", new Error(`Failed to update config: ${error}`));
      throw error;
    }
  }

  public getConfig(): EjectionSettings {
    return { ...this.config };
  }

  public cleanup(): void {
    console.log("[Cleanup] Starting cleanup");
    if (this.ejectionTimeout) {
      clearTimeout(this.ejectionTimeout);
      console.log("[Cleanup] Cleared ejection timeout");
    }
    this.ejectionSolenoid.unexport();
    console.log("[Cleanup] Solenoid unexported");
  }
}
