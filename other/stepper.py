from RpiMotorLib import RpiMotorLib
import time

# Define GPIO pins
direction_pin = 5  # Direction GPIO Pin
step_pin = 6      # Step GPIO Pin
mode_pins = ()    # Mode pins (empty for this example)

# Declare an named instance of class pass GPIO pins numbers
stepper = RpiMotorLib.A4988Nema(direction_pin, step_pin, mode_pins, "A4988")

# Motor steps per revolution (depends on your motor)
steps_per_revolution = 400

try:
    print("Moving forward 200 steps...")
    # Spin motor 200 steps
    stepper.motor_go(True,               # True for clockwise, False for counter-clockwise
                     "Full",             # Step type (Full, Half, 1/4, 1/8, 1/16, 1/32)
                     200,                # Number of steps
                     0.005,              # Step delay [sec]
                     False,              # True for verbose output, False for quiet
                     0.05)               # Initial delay [sec]
    print("Movement complete.")

except KeyboardInterrupt:
    print("Program interrupted.")

finally:
    print("Cleaning up...")
    # The RpiMotorLib doesn't need cleanup like raw GPIO