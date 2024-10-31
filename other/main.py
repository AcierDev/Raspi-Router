import RPi.GPIO as GPIO
import time
import requests
import cv2
import numpy as np

import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"


# Define pin numbers
solenoid_pin = 2  # Pin connected to the relay controlling the solenoid
sensor_pin = 16   # Pin connected to the sensor

# Set up GPIO mode
GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
GPIO.setup(solenoid_pin, GPIO.OUT)
GPIO.setup(sensor_pin, GPIO.IN)

# URL to request the image
image_url = "http://192.168.1.164:1821"
inference_url = "http://192.168.1.210:5000/detect-imperfection"

import time

def send_image_for_analysis(image_data):
    try:
        print(f"Sending image to {inference_url} for analysis")
        
        # Start time tracking
        start_time = time.time()
        
        files = {'image': ('image.jpg', image_data, 'image/jpeg')}
        response = requests.post(inference_url, files=files)
        
        # End time tracking
        end_time = time.time()
        analysis_duration = end_time - start_time
        print(f"Analysis took {analysis_duration:.2f} seconds.")

        if response.status_code == 200:
            print("Response received from analysis server.")
            result = response.json()
            
            # Extract the confidence from the predictions
            predictions = result.get('predictions', [])
            if predictions:
                # Draw bounding boxes on the image
                image_with_boxes = draw_bounding_boxes(image_data, predictions)
                
                # Show the image with bounding boxes
                display_image(image_with_boxes)
                
                # Determine if any predictions have confidence > 0.5
                highest_confidence = max(pred['confidence'] for pred in predictions)
                print(f"Highest confidence: {highest_confidence}")
                
                if highest_confidence > 0.5:
                    print("Imperfection")
                else:
                    print("No Imperfection")
            else:
                print("No predictions received from the analysis.")
        else:
            print(f"Failed to get a valid response, status code: {response.status_code}")
            print("Response content:", response.content)
    except requests.exceptions.RequestException as e:
        print("Error occurred while sending the image for analysis:", e)

def draw_bounding_boxes(image_data, predictions):
    """
    Draws bounding boxes on the image based on predictions.
    :param image_data: Binary image data.
    :param predictions: List of predictions with bounding box details.
    :return: Image with bounding boxes drawn on it.
    """
    # Convert the image data into a numpy array
    np_img = np.frombuffer(image_data, np.uint8)
    image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    
    # Iterate over predictions and draw bounding boxes
    for pred in predictions:
        x = int(pred['x'])
        y = int(pred['y'])
        width = int(pred['width'])
        height = int(pred['height'])
        confidence = pred['confidence']
        
        # Define top-left and bottom-right points
        start_point = (x - width // 2, y - height // 2)
        end_point = (x + width // 2, y + height // 2)
        
        # Draw rectangle on the image (red color, thickness=2)
        cv2.rectangle(image, start_point, end_point, (0, 0, 255), 2)
        
        # Add confidence label above the rectangle
        label = f"{pred['class_name']}: {confidence:.2f}"
        cv2.putText(image, label, (start_point[0], start_point[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    
    return image

import matplotlib.pyplot as plt


def display_image(image):
    """
    Displays the given image using matplotlib.
    :param image: The image with bounding boxes to display.
    """
    # Convert the image from BGR (OpenCV format) to RGB for matplotlib
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    plt.imshow(image_rgb)
    plt.axis('off')  # Hide axis labels
    plt.show()


def download_image():
    try:
        print("Sending GET request to", image_url)
        response = requests.get(image_url, stream=True)

        if response.status_code == 200:
            print("Response received, status code:", response.status_code)
            content_type = response.headers.get('Content-Type')
            
            if 'image' in content_type:
                print("Image received, sending for analysis.")
                # Send the image directly to the analysis server
                send_image_for_analysis(response.content)
            else:
                print("Received content is not an image. Content-Type:", content_type)
        else:
            print("Failed to get a valid response, status code:", response.status_code)

    except requests.exceptions.RequestException as e:
        print("Error occurred while downloading the image:", e)

try:
    while True:
        sensor_status = GPIO.input(sensor_pin)

        if sensor_status == GPIO.HIGH:
            print("Sensor activated, sending request for the image.")
            # Activate the solenoid
            time.sleep(0.2)  # 200 ms delay
            GPIO.output(solenoid_pin, GPIO.HIGH)
            
            # Download the image and send it for analysis
            download_image()

        if sensor_status == GPIO.LOW:
            # Deactivate the solenoid
            time.sleep(0.2)  # 200 ms delay
            GPIO.output(solenoid_pin, GPIO.LOW)

        time.sleep(0.5)  # Short delay to avoid overwhelming the loop with log messages

except KeyboardInterrupt:
    print("Keyboard interrupt detected. Cleaning up GPIO settings.")
    GPIO.cleanup()
    print("GPIO cleaned up. Exiting program.")
