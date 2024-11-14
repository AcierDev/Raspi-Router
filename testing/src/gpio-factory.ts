import fs from "fs";

export interface IGpio {
  readSync(): number;
  writeSync(value: number): void;
  watch(callback: (err: Error | null, value: number) => void): void;
  unexport(): void;
  getPin(): number; // Add method to get pin number for logging
  getDirection(): string; // Add method to get direction for logging
}

class MockGpio implements IGpio {
  private value: number = 0;
  private callbacks: ((err: Error | null, value: number) => void)[] = [];
  private lastReadTime: number = Date.now();
  private lastWriteTime: number = Date.now();
  private readCount: number = 0;
  private writeCount: number = 0;

  constructor(
    private pin: number,
    private direction: string,
    private edge?: string
  ) {
    console.log(
      `[GPIO ${pin}] Initialized in ${direction} mode${
        edge ? ` with edge=${edge}` : ""
      }`
    );
  }

  readSync(): number {
    const now = Date.now();
    const timeSinceLastRead = now - this.lastReadTime;
    this.readCount++;

    // Log every 1000th read or if more than 1 second has passed
    if (this.readCount % 1000 === 0 || timeSinceLastRead > 1000) {
      console.log(
        `[GPIO ${this.pin}] Read value=${this.value} (count=${this.readCount}, interval=${timeSinceLastRead}ms)`
      );
      this.readCount = 0; // Reset counter after logging
    }

    this.lastReadTime = now;
    return this.value;
  }

  writeSync(value: number): void {
    const now = Date.now();
    const timeSinceLastWrite = now - this.lastWriteTime;
    this.writeCount++;

    // Always log writes since they're typically less frequent
    console.log(
      `[GPIO ${this.pin}] Write value=${value} (previous=${this.value}, interval=${timeSinceLastWrite}ms)`
    );

    if (this.value !== value) {
      console.log(`[GPIO ${this.pin}] State change: ${this.value} -> ${value}`);
      this.value = value;
      this.callbacks.forEach((cb) => {
        try {
          cb(null, value);
        } catch (err) {
          console.error(`[GPIO ${this.pin}] Callback error:`, err);
        }
      });
    }

    this.lastWriteTime = now;
  }

  watch(callback: (err: Error | null, value: number) => void): void {
    console.log(
      `[GPIO ${this.pin}] Adding watch callback (total callbacks: ${
        this.callbacks.length + 1
      })`
    );
    this.callbacks.push(callback);
  }

  unexport(): void {
    console.log(
      `[GPIO ${this.pin}] Unexporting (clearing ${this.callbacks.length} callbacks)`
    );
    this.callbacks = [];
  }

  getPin(): number {
    return this.pin;
  }

  getDirection(): string {
    return this.direction;
  }
}

async function getGpioOffset(): Promise<number> {
  try {
    // Read the base value from gpiochip512
    const base = parseInt(
      fs.readFileSync("/sys/class/gpio/gpiochip512/base").toString()
    );
    console.log(`[GPIO] Chip base offset detected: ${base}`);
    return base;
  } catch (err) {
    console.log("[GPIO] Using default offset of 512 (RPi 5)", err);
    return 512; // Default fallback for RPi 5
  }
}

export const createGpioFactory = async () => {
  console.log("[GPIO] Initializing GPIO factory...");
  const baseOffset = await getGpioOffset();
  console.log(`[GPIO] Using base offset: ${baseOffset}`);

  return (pin: number, direction: string, edge?: string): IGpio => {
    const adjustedPin = baseOffset + pin;
    console.log(`[GPIO] Creating new GPIO instance:
    Original Pin: ${pin}
    Adjusted Pin: ${adjustedPin}
    Direction: ${direction}
    Edge: ${edge || "none"}
    Timestamp: ${new Date().toISOString()}
    `);
    return new MockGpio(adjustedPin, direction, edge);
  };
};

// For real hardware implementation
export const createRealGpioFactory = async () => {
  console.log("[GPIO] Initializing real GPIO factory...");
  const baseOffset = await getGpioOffset();
  console.log(`[GPIO] Using base offset: ${baseOffset}`);

  return (pin: number, direction: string, edge?: string): IGpio => {
    const { Gpio } = require("onoff");
    const adjustedPin = baseOffset + pin;
    console.log(`[GPIO] Creating new real GPIO instance:
    Original Pin: ${pin}
    Adjusted Pin: ${adjustedPin}
    Direction: ${direction}
    Edge: ${edge || "none"}
    Timestamp: ${new Date().toISOString()}
    `);

    // Wrap the real GPIO in a logging proxy
    const realGpio = new Gpio(adjustedPin, direction, edge);
    return {
      readSync: () => {
        const value = realGpio.readSync();
        console.log(`[GPIO ${adjustedPin}] Read value=${value}`);
        return value;
      },
      writeSync: (value: number) => {
        console.log(`[GPIO ${adjustedPin}] Writing value=${value}`);
        realGpio.writeSync(value);
      },
      watch: (callback: (err: Error | null, value: number) => void) => {
        console.log(`[GPIO ${adjustedPin}] Setting up watch`);
        realGpio.watch((err, value) => {
          console.log(
            `[GPIO ${adjustedPin}] Watch triggered: value=${value}${
              err ? ", error=" + err : ""
            }`
          );
          callback(err, value);
        });
      },
      unexport: () => {
        console.log(`[GPIO ${adjustedPin}] Unexporting`);
        realGpio.unexport();
      },
      getPin: () => adjustedPin,
      getDirection: () => direction,
    };
  };
};
