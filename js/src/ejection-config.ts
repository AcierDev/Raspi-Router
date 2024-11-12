// Default ejection configuration
export const DEFAULT_EJECTION_CONFIG = {
  globalSettings: {
    ejectionDuration: 1000,
    requireMultipleDefects: false,
    minTotalArea: 100,
    maxDefectsBeforeEject: 5,
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
    regionOfInterest: { x: 0, y: 0, width: 100, height: 100 },
  },
};
