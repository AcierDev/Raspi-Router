import fs from "fs";
import { Gpio } from "onoff";

export interface IGpio {
  readSync(): number;
  writeSync(value: number): void;
  watch(callback: (err: Error | null, value: number) => void): void;
  unexport(): void;
  getPin(): number;
  getDirection(): string;
}

class RealGpio implements IGpio {
  private gpio: Gpio;
  private pin: number;
  private direction: string;

  constructor(pin: number, direction: string, edge?: string) {
    this.pin = pin;
    this.direction = direction;
    this.gpio = new Gpio(pin, direction, edge);
    console.log(
      `[GPIO ${pin}] Initialized in ${direction} mode${
        edge ? ` with edge=${edge}` : ""
      }`
    );
  }

  readSync(): number {
    const value = this.gpio.readSync();
    console.log(`[GPIO ${this.pin}] Read value=${value}`);
    return value;
  }

  writeSync(value: number): void {
    console.log(`[GPIO ${this.pin}] Writing value=${value}`);
    this.gpio.writeSync(value);
  }

  watch(callback: (err: Error | null, value: number) => void): void {
    console.log(`[GPIO ${this.pin}] Setting up watch`);
    this.gpio.watch((err, value) => {
      console.log(
        `[GPIO ${this.pin}] Watch triggered: value=${value}${
          err ? ", error=" + err : ""
        }`
      );
      callback(err, value);
    });
  }

  unexport(): void {
    console.log(`[GPIO ${this.pin}] Unexporting`);
    this.gpio.unexport();
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

    return new RealGpio(adjustedPin, direction, edge);
  };
};
