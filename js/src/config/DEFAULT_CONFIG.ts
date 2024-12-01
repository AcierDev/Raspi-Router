import { RouterSettings } from "../types";

// Default ejection configuration
export const DEFAULT_EJECTION_CONFIG: RouterSettings = {
  globalSettings: {
    ejectionDuration: 1000,
    requireMultipleDefects: false,
    minTotalArea: 100,
    maxDefectsBeforeEject: 5,
    riserDuration: 3000,
    pistonDuration: 5000,
  },
  perClassSettings: {
    corner: { enabled: true, minConfidence: 0.5, minArea: 100, maxCount: 3 },
    crack: { enabled: true, minConfidence: 0.5, minArea: 100, maxCount: 3 },
    damage: { enabled: true, minConfidence: 0.5, minArea: 100, maxCount: 3 },
    edge: { enabled: true, minConfidence: 0.5, minArea: 100, maxCount: 3 },
    knot: { enabled: true, minConfidence: 0.5, minArea: 100, maxCount: 3 },
    router: { enabled: true, minConfidence: 0.5, minArea: 100, maxCount: 3 },
    side: { enabled: true, minConfidence: 0.5, minArea: 100, maxCount: 3 },
    tearout: { enabled: true, minConfidence: 0.5, minArea: 100, maxCount: 3 },
  },
  advancedSettings: {
    considerOverlap: false,
    regionOfInterest: {
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      type: "roi",
      id: "roi",
    },
    exclusionZones: [],
  },
};

export const SENSOR1_PIN = 20;
export const PISTON_PIN = 14;
export const RISER_PIN = 15;
export const EJECTOR_PIN = 18;
