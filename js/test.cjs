#!/usr/bin/env node

const { Gpio } = require("onoff");

// Parse command line arguments
const args = process.argv.slice(2);

// Help text
const showHelp = () => {
  console.log(`
GPIO Pin Toggle Script for Raspberry Pi
Usage: node gpio-toggle.js <pin> [state]

Arguments:
  pin   : GPIO pin number (will automatically add 512 for WiringPi mapping)
  state : Optional - Set to specific state (1 for ON, 0 for OFF)
          If omitted, will toggle current state

Examples:
  Toggle pin 15:    node gpio-toggle.js 15
  Turn pin 15 ON:   node gpio-toggle.js 15 1
  Turn pin 15 OFF:  node gpio-toggle.js 15 0
    `);
  process.exit(0);
};

// Show help if requested or no arguments provided
if (args.length === 0 || args[0] === "-h" || args[0] === "--help") {
  showHelp();
}

// Validate pin number and add 512 for WiringPi mapping
const rawPinNumber = parseInt(args[0]);
if (isNaN(rawPinNumber) || rawPinNumber < 0 || rawPinNumber > 27) {
  console.error("Error: Invalid GPIO pin number. Must be between 0 and 27.");
  process.exit(1);
}
const pinNumber = rawPinNumber + 512;

// Validate state if provided
let targetState = null;
if (args[1] !== undefined) {
  targetState = parseInt(args[1]);
  if (![0, 1].includes(targetState)) {
    console.error("Error: State must be 0 (OFF) or 1 (ON)");
    process.exit(1);
  }
}

// Main function to handle pin operations
async function togglePin(pin, rawPin, state = null) {
  let gpio = null;

  try {
    // Initialize GPIO pin with explicit direction and initial state
    console.log(`Initializing GPIO ${rawPin} (mapped to ${pin})...`);
    gpio = new Gpio(pin, "out", "none", { activeLow: false });

    // Add a small delay after initialization
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Read current state if we're doing a toggle
    if (state === null) {
      console.log("Reading current state...");
      const currentState = gpio.readSync();
      state = currentState === 0 ? 1 : 0;
    }

    console.log(
      `Attempting to set pin ${rawPin} (mapped to ${pin}) to state ${state}...`
    );

    // Write the new state
    await gpio.writeSync(state);
    console.log(
      `Successfully set pin ${rawPin} to ${state === 1 ? "ON" : "OFF"}`
    );
  } catch (error) {
    console.error("Detailed error information:");
    console.error(`- Error name: ${error.name}`);
    console.error(`- Error message: ${error.message}`);
    console.error(`- Error code: ${error.code}`);
    console.error(`- Attempted operation on pin: ${rawPin} (mapped to ${pin})`);
    console.error(`- Attempted state: ${state}`);

    if (error.code === "EINVAL") {
      console.error("\nPossible solutions:");
      console.error(
        `1. Verify that GPIO ${rawPin} (mapped to ${pin}) is not in use by another process`
      );
      console.error("2. Check if the pin is properly exported in sysfs");
      console.error(
        `3. Try running: sudo gpio unexport ${pin} before retrying`
      );
      console.error(
        "4. Ensure you have the latest version of WiringPi installed"
      );
    }

    process.exit(1);
  } finally {
    // Cleanup with delay
    if (gpio) {
      try {
        await new Promise((resolve) => setTimeout(resolve, 100));
        gpio.unexport();
        console.log(`Cleaned up GPIO ${rawPin} (mapped to ${pin})`);
      } catch (cleanupError) {
        console.error(`Warning: Cleanup failed - ${cleanupError.message}`);
      }
    }
  }
}

// Execute the toggle
console.log(
  `Starting GPIO operation for pin ${rawPinNumber} (mapped to ${pinNumber})${
    targetState !== null ? ` with target state ${targetState}` : ""
  }`
);
togglePin(pinNumber, rawPinNumber, targetState).catch((error) => {
  console.error(`Fatal error: ${error.message}`);
  process.exit(1);
});
