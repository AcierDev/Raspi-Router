from PIL import Image
import os

def show_status(color):
    # Create a blank image with the specified color
    img = Image.new("RGB", (1920, 1080), color)
    img_path = "/tmp/status_screen.png"
    img.save(img_path)

    # Display the image using fbi
    os.system(f"sudo fbi -T 1 -noverbose -a {img_path}")

# Example usage
status = "ok"  # Change to "ok" or "alert" to test
show_status("green" if status == "ok" else "red")
