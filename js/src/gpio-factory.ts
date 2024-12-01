import fs from "fs";
import { BinaryValue, Direction, Edge, Gpio } from "onoff";

export interface IGpio {
  readSync(): number;
  writeSync(value: number): void;
  watch(callback: (err: Error | null, value: number) => void): void;
  unexport(): void;
  getPin(): number;
  getDirection(): string;
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
      this.readCount = 0;
    }

    this.lastReadTime = now;
    return this.value == 1 ? 0 : 1;
  }

  writeSync(value: number): void {
    const now = Date.now();
    const timeSinceLastWrite = now - this.lastWriteTime;
    this.writeCount++;

    if (this.value !== value) {
      // console.log(
      //   `[GPIO ${this.pin}] State change detected:
      //   Previous State: ${this.value}
      //   New State: ${value}
      //   Time Since Last Write: ${timeSinceLastWrite}ms
      //   Timestamp: ${new Date().toISOString()}`
      // );

      this.value = value;
      this.callbacks.forEach((cb) => {
        try {
          cb(null, value == 1 ? 0 : 1);
        } catch (err) {
          console.error(`[GPIO ${this.pin}] Callback error:`, err);
        }
      });
    } else {
      console.log(
        `[GPIO ${this.pin}] Write value=${value} (no state change, interval=${timeSinceLastWrite}ms)`
      );
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
    const base = parseInt(
      fs.readFileSync("/sys/class/gpio/gpiochip512/base").toString()
    );
    console.log(`[GPIO] Chip base offset detected: ${base}`);
    return base;
  } catch (err) {
    console.log("[GPIO] Using default offset of 512 (RPi 5)", err);
    return 512;
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

  return (
    pin: number,
    direction: Direction,
    edge?: Edge,
    name?: string
  ): IGpio => {
    const adjustedPin = baseOffset + pin;
    console.log(`[GPIO] Creating new real GPIO instance:
    Name: ${name}
    Original Pin: ${pin}
    Adjusted Pin: ${adjustedPin}
    Direction: ${direction}
    Edge: ${edge || "none"}
    Timestamp: ${new Date().toISOString()}
    `);

    const realGpio = new Gpio(adjustedPin, direction, edge);
    let lastValue: number | null = null;

    return {
      readSync: () => {
        const value = realGpio.readSync() == 1 ? 0 : 1;
        return value;
      },
      writeSync: (value: number) => {
        const invertedValue = value == 1 ? 0 : 1;
        if (lastValue !== value) {
          console.log(
            `[GPIO ${pin} - ${name}] State change detected:
            Previous State: ${lastValue !== null ? lastValue : "initial"}
            New State: ${invertedValue}
            Timestamp: ${new Date().toISOString()}`
          );
          lastValue = invertedValue;
        }
        // console.log(`SETTING PIN: ${pin} to ${invertedValue}`);
        realGpio.writeSync(invertedValue as BinaryValue);
      },
      watch: (callback: (err: Error | null, value: number) => void) => {
        console.log(`[GPIO ${adjustedPin}] Setting up watch`);
        realGpio.watch((err, gpioValue) => {
          const value = gpioValue == 1 ? 0 : 1;
          if (lastValue !== value) {
            console.log(
              `[GPIO ${pin} - ${name}] State change detected (watch):
              Previous State: ${lastValue !== null ? lastValue : "initial"}
              New State: ${value}
              Timestamp: ${new Date().toISOString()}`
            );
            lastValue = value;
          }
          callback(err, value);
        });
      },
      unexport: () => {
        console.log(`[GPIO ${pin}] Unexporting`);
        realGpio.unexport();
      },
      getPin: () => adjustedPin,
      getDirection: () => direction,
    };
  };
};
