import RPi.GPIO as GPIO
from config import SOLENOID_PIN, SENSOR_PIN, NEW_SENSOR_PIN

class GPIOController:
    def __init__(self):
        self.setup()

    def setup(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SOLENOID_PIN, GPIO.OUT)
        GPIO.setup(SENSOR_PIN, GPIO.IN)
        GPIO.setup(NEW_SENSOR_PIN, GPIO.IN)
        GPIO.output(SOLENOID_PIN, GPIO.HIGH)  # Initialize solenoid to OFF (inverted logic)

    def cleanup(self):
        GPIO.output(SOLENOID_PIN, GPIO.HIGH)  # Ensure solenoid is OFF
        GPIO.cleanup()

    def read_sensor1(self):
        return not GPIO.input(SENSOR_PIN)

    def read_sensor2(self):
        return not GPIO.input(NEW_SENSOR_PIN)

    def get_solenoid_state(self):
        return not GPIO.input(SOLENOID_PIN)

    def set_solenoid(self, state):
        # Remember: inverted logic (LOW = ON, HIGH = OFF)
        GPIO.output(SOLENOID_PIN, not state)