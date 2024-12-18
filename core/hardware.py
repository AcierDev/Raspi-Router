# core/hardware.py

import RPi.GPIO as GPIO
from config import SOLENOID_PIN, SENSOR_PIN, NEW_SENSOR_PIN

class GPIOController:
    def __init__(self):
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup pins
        self.setup_pins()
        
        # Initialize states
        self._solenoid_state = False

    def setup_pins(self):
        """Setup GPIO pins with proper modes"""
        # Setup input pins (sensors) with pull-up resistors
        # This matches the original logic where LOW means triggered
        GPIO.setup(SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(NEW_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Setup output pin (solenoid)
        GPIO.setup(SOLENOID_PIN, GPIO.OUT)
        GPIO.output(SOLENOID_PIN, GPIO.HIGH)  # Initialize to OFF (inverted logic)

    def read_sensor1(self):
        """Read state of sensor 1 - returns True when triggered"""
        return not GPIO.input(SENSOR_PIN)  # Invert to match original logic

    def read_sensor2(self):
        """Read state of sensor 2 - returns True when triggered"""
        return not GPIO.input(NEW_SENSOR_PIN)  # Invert to match original logic

    def set_solenoid(self, state):
        """Set solenoid state (True = ON, False = OFF)"""
        GPIO.output(SOLENOID_PIN, not state)  # Invert for hardware logic
        self._solenoid_state = state

    def get_solenoid_state(self):
        """Get current solenoid state"""
        return self._solenoid_state

    def cleanup(self):
        """Clean up GPIO resources"""
        self.set_solenoid(False)  # Ensure solenoid is off
        GPIO.cleanup()