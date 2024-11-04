import RPi.GPIO as GPIO
import time

# Define pin numbers
solenoidPin = 27  # GPIO pin connected to the relay controlling the solenoid
sensorPin = 14   # GPIO pin connected to the sensor

# Set up the GPIO pins
GPIO.setmode(GPIO.BCM)  # Use BCM GPIO numbering
GPIO.setup(solenoidPin, GPIO.OUT)  # Set solenoid pin as an output
GPIO.setup(sensorPin, GPIO.IN)     # Set sensor pin as an input

try:
    while True:
        if GPIO.input(sensorPin) == GPIO.HIGH:
            # Activate the solenoid
            time.sleep(0.2)  # Delay 200ms
            GPIO.output(solenoidPin, GPIO.HIGH)

        # Check if the sensor is deactivated
        if GPIO.input(sensorPin) == GPIO.LOW:
            # Deactivate the solenoid
            time.sleep(0.2)  # Delay 200ms
            GPIO.output(solenoidPin, GPIO.LOW)

finally:
    GPIO.cleanup()  # Clean up GPIO on exit
