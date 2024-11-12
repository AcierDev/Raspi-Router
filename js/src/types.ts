export interface IGpio {
  readSync(): number;
  writeSync(value: number): void;
  watch(callback: (err: Error | null, value: number) => void): void;
  unexport(): void;
}

export interface LogEntry {
  id?: string;
  timestamp: string;
  level: "info" | "warning" | "error";
  message: string;
  source?: string;
}

// Updated interfaces to match the actual API response
export interface FileInfo {
  original_filename: string;
  stored_locations: {
    count_based: string;
    defect_types: string[];
  };
}

export interface BoundingBox {
  0: number; // x1
  1: number; // y1
  2: number; // x2
  3: number; // y2
}

export interface Prediction {
  bbox: BoundingBox;
  class_name: ClassName;
  confidence: number;
  detection_id: string;
}

export interface DetectionResponse {
  data: {
    file_info: FileInfo;
    predictions: Prediction[];
  };
  success: boolean;
  timestamp: string;
  processingTime: number;
}

// Configuration interfaces designed for easy GUI control
export interface DefectClassConfig {
  enabled: boolean;
  minConfidence: number;
  minArea?: number;
  maxArea?: number;
}

export interface SystemState {
  sensor1: boolean;
  sensor2: boolean;
  solenoid: boolean;
  ejection: boolean;
  isProcessing: boolean;
  lastPhotoPath: string | null;
  deviceConnected: boolean;
  isCapturingImage: boolean;
  lastEjectionResult?: {
    didEject: boolean;
    reason: string;
    details: any;
  };
  ejectionSettings: EjectionSettings;
}

export type ClassName =
  | "corner"
  | "crack"
  | "damage"
  | "edge"
  | "knot"
  | "router"
  | "side"
  | "tearout";

export interface RegionOfInterest {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface EjectionSettings {
  globalSettings: GlobalSettings;
  perClassSettings: PerClassSettings;
  advancedSettings: AdvancedSettings;
}

export interface GlobalSettings {
  ejectionDuration: number;
  requireMultipleDefects: boolean;
  minTotalArea: number;
  maxDefectsBeforeEject: number;
}

export type PerClassSettings = {
  [className in ClassName]: {
    enabled: boolean;
    minConfidence: number;
    minArea: number;
    maxCount: number;
  };
};

export type AdvancedSettings = {
  considerOverlap: boolean;
  regionOfInterest: RegionOfInterest;
};

export type PresetSettings = "High" | "Medium" | "Low";
