from PIL import Image
import io

# Test if PIL can handle a small in-memory image
try:
    # Create a small test image
    test_img = Image.new('RGB', (100, 100), color='red')
    # Save to bytes
    img_byte_arr = io.BytesIO()
    test_img.save(img_byte_arr, format='JPEG')
    # Try to read it back
    img_byte_arr.seek(0)
    test_read = Image.open(img_byte_arr)
    test_read.load()  # This forces the image to be read
    print("In-memory JPEG test: Success")
    
    # Print supported formats
    print("\nSupported formats:", Image.registered_extensions())
except Exception as e:
    print("Test failed:", str(e))
