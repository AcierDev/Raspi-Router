// src/gpio-factory.ts
export interface IGpio {
  readSync(): number;
  writeSync(value: number): void;
  watch(callback: (err: Error | null, value: number) => void): void;
  unexport(): void;
}

class MockGpio implements IGpio {
  private value: number = 0;
  private callbacks: ((err: Error | null, value: number) => void)[] = [];

  constructor(
    private pin: number,
    private direction: string,
    private edge?: string
  ) {}

  readSync(): number {
    return this.value;
  }

  writeSync(value: number): void {
    this.value = value;
    this.callbacks.forEach((cb) => cb(null, value));
  }

  watch(callback: (err: Error | null, value: number) => void): void {
    this.callbacks.push(callback);
  }

  unexport(): void {
    this.callbacks = [];
  }
}

export const createGpioFactory = () => {
  return (pin: number, direction: string, edge?: string): IGpio => {
    return new MockGpio(pin, direction, edge);
  };
};
