# ui/fb_ui.py

import os
import io
import mmap
import sys
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
from .base_ui import BaseUI

class FramebufferUI(BaseUI):
    def __init__(self):
        super().__init__()
        self.fb = self._init_framebuffer()
        self.current_predictions = None
        self.last_draw_time = None
        self.REDRAW_INTERVAL = 1.0
        
        # Enhanced metrics tracking
        self.metrics = {
            'start_time': datetime.now(),
            'processed_count': 0,
            'defect_counts': {},
            'processing_times': [],  # List of processing times in seconds
            'current_processing_start': None,  # Track current processing start time
            'error_count': 0,
            'last_process_time': None,
            'detection_history': [],
            'hourly_counts': {},
            'daily_counts': {},
        }
        
        # Add processing time statistics
        self.processing_stats = {
            'min_time': float('inf'),
            'max_time': 0,
            'total_time': 0,
            'count': 0
        }
        
        self.MAX_HISTORY = 100
        
        # Rest of initialization code remains the same...
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
            self.small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 10)
        except:
            try:
                self.font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 14)
                self.small_font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 10)
            except:
                self.font = ImageFont.load_default()
                self.small_font = ImageFont.load_default()

        self.image = Image.new('RGB', (self.fb['width'], self.fb['height']), (0, 0, 0))
        self.drawer = ImageDraw.Draw(self.image)
        
        self.ui_width = self.fb['width'] // 2
        self.image_width = self.fb['width'] - self.ui_width
        self.image_display_size = (936, 936)

    def start_processing(self):
        """Mark the start of processing for timing purposes"""
        self.metrics['current_processing_start'] = time.time()

    def update_metrics(self, results=None, error=None, processing_time=None):
        """Update system metrics based on processing results"""
        current_time = datetime.now()
        hour_key = current_time.strftime('%Y-%m-%d %H:00')
        day_key = current_time.strftime('%Y-%m-%d')
        
        # Calculate processing time if not provided
        if processing_time is None and self.metrics['current_processing_start'] is not None:
            processing_time = time.time() - self.metrics['current_processing_start']
        
        if processing_time is not None:
            # Update processing time statistics
            self.metrics['processing_times'].append(processing_time)
            self.metrics['last_process_time'] = processing_time
            
            # Update processing stats
            self.processing_stats['min_time'] = min(self.processing_stats['min_time'], processing_time)
            self.processing_stats['max_time'] = max(self.processing_stats['max_time'], processing_time)
            self.processing_stats['total_time'] += processing_time
            self.processing_stats['count'] += 1
            
            # Trim history if needed
            if len(self.metrics['processing_times']) > self.MAX_HISTORY:
                self.metrics['processing_times'].pop(0)
        
        if results:
            # Update processed count
            self.metrics['processed_count'] += 1
            
            # Update defect counts
            if 'predictions' in results:
                for pred in results['predictions']:
                    defect_type = pred['class_name']
                    self.metrics['defect_counts'][defect_type] = \
                        self.metrics['defect_counts'].get(defect_type, 0) + 1
            
            # Update detection history
            self.metrics['detection_history'].append({
                'timestamp': current_time,
                'count': len(results.get('predictions', [])),
                'types': [p['class_name'] for p in results.get('predictions', [])],
                'processing_time': processing_time
            })
            if len(self.metrics['detection_history']) > self.MAX_HISTORY:
                self.metrics['detection_history'].pop(0)
            
            # Update hourly and daily statistics
            self._update_time_based_stats(hour_key, day_key, results, processing_time)
            
        if error:
            self.metrics['error_count'] += 1
        
        # Reset processing start time
        self.metrics['current_processing_start'] = None

    def _update_time_based_stats(self, hour_key, day_key, results, processing_time):
        """Update hourly and daily statistics"""
        # Initialize hour stats if needed
        if hour_key not in self.metrics['hourly_counts']:
            self.metrics['hourly_counts'][hour_key] = {
                'total': 0,
                'defects': 0,
                'processing_times': [],
                'by_type': {}
            }
        
        # Initialize day stats if needed
        if day_key not in self.metrics['daily_counts']:
            self.metrics['daily_counts'][day_key] = {
                'total': 0,
                'defects': 0,
                'processing_times': [],
                'by_type': {}
            }
        
        # Update hourly stats
        hour_stats = self.metrics['hourly_counts'][hour_key]
        hour_stats['total'] += 1
        hour_stats['defects'] += len(results.get('predictions', []))
        if processing_time:
            hour_stats['processing_times'].append(processing_time)
        
        # Update daily stats
        day_stats = self.metrics['daily_counts'][day_key]
        day_stats['total'] += 1
        day_stats['defects'] += len(results.get('predictions', []))
        if processing_time:
            day_stats['processing_times'].append(processing_time)

    def _draw_metrics_section(self, x, y, width):
        """Draw comprehensive metrics section"""
        current_time = datetime.now()
        uptime = current_time - self.metrics['start_time']
        
        # Calculate statistics
        total_processed = self.metrics['processed_count']
        total_defects = sum(self.metrics['defect_counts'].values())
        avg_defects = total_defects / max(1, total_processed)
        
        # Calculate processing time statistics
        if self.processing_stats['count'] > 0:
            avg_time = self.processing_stats['total_time'] / self.processing_stats['count']
            min_time = self.processing_stats['min_time']
            max_time = self.processing_stats['max_time']
            last_time = self.metrics['last_process_time']
        else:
            avg_time = min_time = max_time = last_time = 0
        
        # Draw metrics section background
        metrics_y = self._draw_section("System Metrics", "", x, y, width, 320)
        
        # Draw basic metrics
        self.drawer.text((x + 10, metrics_y), f"Uptime: {str(uptime).split('.')[0]}", 
                        font=self.font, fill=(255, 255, 255))
        metrics_y += 20
        
        self.drawer.text((x + 10, metrics_y), f"Total Processed: {total_processed}", 
                        font=self.font, fill=(255, 255, 255))
        metrics_y += 20
        
        # Draw processing time metrics with colored values
        if last_time is not None:
            last_color = (255, 165, 0) if last_time > avg_time * 1.5 else (255, 255, 255)
            self.drawer.text((x + 10, metrics_y), f"Last Process: {last_time:.2f}s", 
                           font=self.font, fill=last_color)
        metrics_y += 20
        
        self.drawer.text((x + 10, metrics_y), f"Avg Process: {avg_time:.2f}s", 
                        font=self.font, fill=(255, 255, 255))
        metrics_y += 20
        
        self.drawer.text((x + 10, metrics_y), f"Min Process: {min_time:.2f}s", 
                        font=self.font, fill=(0, 255, 0))
        metrics_y += 20
        
        self.drawer.text((x + 10, metrics_y), f"Max Process: {max_time:.2f}s", 
                        font=self.font, fill=(255, 0, 0))
        metrics_y += 30
        
        # Draw defect metrics
        self.drawer.text((x + 10, metrics_y), f"Total Defects: {total_defects}", 
                        font=self.font, fill=(255, 255, 255))
        metrics_y += 20
        
        self.drawer.text((x + 10, metrics_y), f"Avg Defects/Item: {avg_defects:.2f}", 
                        font=self.font, fill=(255, 255, 255))
        metrics_y += 20
        
        # Draw error metrics
        error_rate = (self.metrics['error_count'] / max(1, total_processed)) * 100
        self.drawer.text((x + 10, metrics_y), f"Errors: {self.metrics['error_count']} ({error_rate:.1f}%)", 
                        font=self.font, fill=(255, 0, 0))
        metrics_y += 30
        
        # Draw defect type breakdown
        self.drawer.text((x + 10, metrics_y), "Defect Types:", 
                        font=self.font, fill=(255, 255, 255))
        metrics_y += 20
        
        for defect_type, count in sorted(self.metrics['defect_counts'].items()):
            color = self.defect_colors.get(defect_type.lower(), self.defect_colors['default'])
            percentage = (count / max(1, total_defects)) * 100
            self.drawer.text((x + 20, metrics_y), 
                           f"{defect_type}: {count} ({percentage:.1f}%)", 
                           font=self.small_font, fill=color)
            metrics_y += 15
        
        return metrics_y + 10

    def _init_framebuffer(self):
        """Initialize framebuffer device for Raspberry Pi"""
        try:
            # Open the framebuffer device
            fb_dev = os.open('/dev/fb0', os.O_RDWR)
            
            # Get framebuffer info using fbset
            fb_info_str = os.popen('fbset -i').read()
            
            # Parse resolution and line length
            width = height = 800  # Default values
            line_length = None
            
            for line in fb_info_str.split('\n'):
                if 'geometry' in line:
                    parts = line.split()
                    width = int(parts[1])
                    height = int(parts[2])
                elif 'LineLength' in line:
                    parts = line.split()
                    line_length = int(parts[2])
            
            # Calculate size based on line length if available
            if line_length:
                size = line_length * height
            else:
                size = width * height * 2  # 16 bits = 2 bytes per pixel
            
            # Memory map the framebuffer
            fb = mmap.mmap(fb_dev, size, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
            
            fb_info = {
                'dev': fb_dev,
                'fb': fb,
                'width': width,
                'height': height,
                'size': size,
                'line_length': line_length or (width * 2)
            }
            
            print(f"Framebuffer initialized: {width}x{height}, 16-bit color")
            return fb_info
            
        except Exception as e:
            print(f"Failed to initialize framebuffer: {e}")
            print("Debugging information:")
            try:
                print(f"Framebuffer device exists: {os.path.exists('/dev/fb0')}")
                print(f"Current user: {os.getlogin()}")
                print(f"Groups: {os.popen('groups').read().strip()}")
                print(f"Framebuffer permissions: {os.popen('ls -l /dev/fb0').read().strip()}")
                print("fbset output:")
                print(os.popen('fbset -i').read().strip())
            except:
                pass
            sys.exit(1)

    def _draw_camera_view(self, x, y, width, height):
        """Draw the camera image with detection overlays"""
        # Draw border
        self.drawer.rectangle([x, y, x + width, y + height], outline=(255, 255, 255))
        
        if self.current_image and hasattr(self.current_image, 'mode'):
            try:
                # Only print debug once per image update, not every refresh
                if not hasattr(self, '_last_image_debug'):
                    print(f"Drawing image: original size={self.current_image.size}")
                    self._last_image_debug = self.current_image.size
                elif self._last_image_debug != self.current_image.size:
                    print(f"Drawing new image: original size={self.current_image.size}")
                    self._last_image_debug = self.current_image.size
                
                # Create a copy for resizing
                img_copy = self.current_image.copy()
                img_copy.thumbnail((width - 4, height - 4))
                
                # Calculate position to center the image
                img_x = x + 2 + (width - 4 - img_copy.width) // 2
                img_y = y + 2 + (height - 4 - img_copy.height) // 2
                
                # Paste the image
                self.image.paste(img_copy, (img_x, img_y))
                
                # Draw detections if available
                if self.current_predictions and 'predictions' in self.current_predictions:
                    # Get source and display dimensions for scaling
                    source_width = self.current_image.width
                    source_height = self.current_image.height
                    display_width = img_copy.width
                    display_height = img_copy.height
                    
                    # Calculate scaling factors
                    scale_x = display_width / source_width
                    scale_y = display_height / source_height
                    
                    for pred in self.current_predictions['predictions']:
                        try:
                            # Get original coordinates
                            orig_coords = pred['metadata']['original_coords']
                            x_center = orig_coords['x']
                            y_center = orig_coords['y']
                            box_width = orig_coords['width']
                            box_height = orig_coords['height']
                            
                            # Calculate display coordinates
                            x1 = img_x + (x_center - box_width/2) * scale_x
                            y1 = img_y + (y_center - box_height/2) * scale_y
                            x2 = x1 + box_width * scale_x
                            y2 = y1 + box_height * scale_y
                            
                            # Get color based on defect type
                            class_name = pred['class_name'].lower()
                            color = self.defect_colors.get(class_name, self.defect_colors['default'])
                            
                            # Draw bounding box
                            self.drawer.rectangle([x1, y1, x2, y2], outline=color, width=2)
                            
                            # Draw label
                            label = f"{pred['class_name']} {pred['confidence']:.1%}"
                            text_bb = self.drawer.textbbox((0, 0), label, font=self.small_font)
                            text_width = text_bb[2] - text_bb[0]
                            text_height = text_bb[3] - text_bb[1]
                            
                            # Position label above box if possible
                            label_x = x1
                            label_y = y1 - text_height - 4
                            if label_y < img_y:  # If label would go above image, put it inside box
                                label_y = y1 + 2
                            
                            # Draw label background
                            self.drawer.rectangle(
                                [label_x, label_y, label_x + text_width + 4, label_y + text_height + 2],
                                fill=color
                            )
                            
                            # Draw label text
                            self.drawer.text(
                                (label_x + 2, label_y + 1),
                                label,
                                font=self.small_font,
                                fill=(0, 0, 0)
                            )
                            
                        except Exception as e:
                            print(f"Error drawing detection: {e}")
                            continue
                    
                # Draw timestamp
                if self.image_timestamp:
                    timestamp_str = f"Captured: {self.image_timestamp.strftime('%H:%M:%S')}"
                    self.drawer.text(
                        (x + 5, y + 5),
                        timestamp_str,
                        font=self.font,
                        fill=(255, 255, 0)
                    )
                    
            except Exception as e:
                print(f"Error drawing camera view: {e}")
                import traceback
                traceback.print_exc()
                self._draw_placeholder(x, y, width, height)
        else:
            self._draw_placeholder(x, y, width, height)

    def _draw_detections(self, predictions, img_x, img_y, img_width, img_height):
        """Draw detection boxes and labels on the image"""
        print(f"Drawing {len(predictions)} detections")
        print(f"Image dimensions: {img_width}x{img_height} at ({img_x}, {img_y})")
        
        # Get actual image dimensions from metadata
        if self.current_predictions and 'metadata' in self.current_predictions:
            metadata = self.current_predictions['metadata']
            source_width = metadata.get('image_size', {}).get('width', 1920)
            source_height = metadata.get('image_size', {}).get('height', 1080)
        else:
            source_width = 1920  # Default values if metadata not available
            source_height = 1080
        
        print(f"Source image dimensions: {source_width}x{source_height}")
        
        # Calculate scaling factors to map from source to display
        scale_x = img_width / source_width
        scale_y = img_height / source_height
        
        print(f"Scale factors: x={scale_x:.3f}, y={scale_y:.3f}")
        
        for i, pred in enumerate(predictions):
            try:
                # Get detection info
                bbox = pred.get('bbox', [])
                if not bbox or len(bbox) != 4:
                    print(f"Invalid bbox for prediction {i}: {bbox}")
                    continue
                    
                confidence = pred.get('confidence', 0)
                class_name = pred.get('class_name', 'unknown')
                
                # Get the original coordinates from metadata if available
                metadata = pred.get('metadata', {})
                orig_coords = metadata.get('original_coords', {})
                
                if orig_coords:
                    # Use original pixel coordinates and scale them
                    x = orig_coords.get('x', 0)
                    y = orig_coords.get('y', 0)
                    width = orig_coords.get('width', 0)
                    height = orig_coords.get('height', 0)
                    
                    # Scale to display coordinates
                    x1 = img_x + int(x * scale_x)
                    y1 = img_y + int(y * scale_y)
                    x2 = img_x + int((x + width) * scale_x)
                    y2 = img_y + int((y + height) * scale_y)
                else:
                    # Use normalized coordinates [0,1]
                    x1 = img_x + int(bbox[0] * img_width)
                    y1 = img_y + int(bbox[1] * img_height)
                    x2 = img_x + int(bbox[2] * img_width)
                    y2 = img_y + int(bbox[3] * img_height)
                
                # Ensure coordinates are within bounds
                x1 = max(img_x, min(img_x + img_width - 1, x1))
                y1 = max(img_y, min(img_y + img_height - 1, y1))
                x2 = max(img_x, min(img_x + img_width - 1, x2))
                y2 = max(img_y, min(img_y + img_height - 1, y2))
                
                # Ensure box has minimum size
                if x2 - x1 < 2: x2 = x1 + 2
                if y2 - y1 < 2: y2 = y1 + 2
                
                print(f"Drawing detection {i}: {class_name} at ({x1},{y1},{x2},{y2}) conf={confidence:.2f}")
                
                # Get color for this defect type
                color = self.defect_colors.get(class_name.lower(), self.defect_colors['default'])
                
                # Draw box with minimum width of 2 pixels
                self.drawer.rectangle([x1, y1, x2, y2], outline=color, width=2)
                
                # Prepare label text
                label = f"{class_name} {confidence:.1%}"
                
                # Draw label background
                text_bb = self.drawer.textbbox((0, 0), label, font=self.small_font)
                text_width = text_bb[2] - text_bb[0]
                text_height = text_bb[3] - text_bb[1]
                margin = 2
                
                # Position label above box if possible, inside if not
                label_x = x1
                label_y = y1 - text_height - 2*margin
                if label_y < img_y:
                    label_y = y1 + margin
                
                # Ensure label stays within image bounds
                if label_x + text_width + 2*margin > img_x + img_width:
                    label_x = img_x + img_width - text_width - 2*margin
                
                self.drawer.rectangle(
                    [label_x, label_y, label_x + text_width + 2*margin, label_y + text_height + 2*margin],
                    fill=color
                )
                
                # Draw label text
                self.drawer.text(
                    (label_x + margin, label_y + margin),
                    label,
                    font=self.small_font,
                    fill=(0, 0, 0)
                )
                
            except Exception as e:
                print(f"Error drawing detection {i}: {e}")
                import traceback
                traceback.print_exc()
                continue

    def _draw_detection_summary(self, x, y):
        """Draw detection summary at the bottom of the image"""
        summary = self.current_predictions['summary']
        
        # Draw background
        padding = 5
        line_height = 15
        num_lines = len(summary['class_counts']) + 1
        
        self.drawer.rectangle(
            [x - padding, y - padding,
             x + 200, y + (line_height * num_lines) + padding],
            fill=(0, 0, 0, 128)
        )
        
        # Draw total count
        self.drawer.text(
            (x, y),
            f"Total defects: {summary['count']}",
            font=self.small_font,
            fill=(255, 255, 255)
        )
        
        # Draw counts by type
        y_offset = line_height
        for class_name, count in summary['class_counts'].items():
            color = self.defect_colors.get(class_name.lower(), self.defect_colors['default'])
            self.drawer.text(
                (x, y + y_offset),
                f"• {class_name}: {count}",
                font=self.small_font,
                fill=color
            )
            y_offset += line_height

    def update_predictions(self, predictions):
        """Update the current predictions"""
        try:
            print("Updating predictions:", predictions is not None)
            self.current_predictions = predictions
            if predictions:
                print(f"Number of predictions: {len(predictions.get('predictions', []))}")
                print(f"First prediction: {predictions['predictions'][0] if predictions['predictions'] else 'None'}")
            self.update_status_message("Updated detection display")
        except Exception as e:
            print(f"Error in update_predictions: {e}")
            import traceback
            traceback.print_exc()

    def _draw_placeholder(self, x, y, width, height):
        """Draw placeholder when no image is available"""
        text = "No Camera Image"
        text_bbox = self.drawer.textbbox((0, 0), text, font=self.font)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = x + (width - text_width) // 2
        text_y = y + height // 2 - 10
        self.drawer.text((text_x, text_y), text, font=self.font, fill=(128, 128, 128))

    def update_image(self, image_data):
        """Update the current camera image"""
        if image_data:
            try:
                # Debug print original data
                print(f"Received image data of length: {len(image_data)}")
                
                # Create a fresh BytesIO object
                image_buffer = io.BytesIO(image_data)
                
                # Load the image and create a fully loaded copy
                temp_image = Image.open(image_buffer)
                
                # Debug print image details
                print(f"Loaded image: size={temp_image.size}, mode={temp_image.mode}")
                
                # Convert to RGB if needed
                if temp_image.mode != 'RGB':
                    temp_image = temp_image.convert('RGB')
                    print("Converted image to RGB mode")
                
                # Create a fully loaded copy
                self.current_image = temp_image.copy()
                self.image_timestamp = datetime.now()
                
                print(f"Stored image: size={self.current_image.size}, mode={self.current_image.mode}")
                self.update_status_message("Camera image updated")
                
            except Exception as e:
                print(f"Error loading image: {e}")
                import traceback
                traceback.print_exc()
                self.current_image = None
                self.image_timestamp = None
        else:
            self.current_image = None
            self.image_timestamp = None
            self.update_status_message("Camera image cleared")

    def update_display(self, gpio_controller, network_status):
        """Update the framebuffer display with enhanced metrics"""
        current_time = time.time()
        
        if self.last_draw_time and (current_time - self.last_draw_time) < self.REDRAW_INTERVAL:
            return
            
        try:
            # Clear the image
            self.drawer.rectangle([0, 0, self.fb['width'], self.fb['height']], fill=(0, 0, 0))
            
            # Draw title
            title = "Automated Inspection System"
            title_w = self._get_text_width(title)
            self.drawer.text(((self.ui_width - title_w) // 2, 10), title, 
                        font=self.font, fill=(255, 255, 255))
            
            # Draw state
            state_str = f"State: {self.current_status['state'].replace('_', ' ').title()}"
            self.drawer.text((10, 40), state_str, font=self.font, fill=(255, 255, 255))
            
            # Draw metrics section first
            metrics_y = self._draw_metrics_section(10, 70, self.ui_width - 20)
            
            # Draw network status
            net_y = self._draw_section("Network Status", "", 10, metrics_y + 10, 
                                     self.ui_width - 20, 180)
            self._draw_network_status(network_status, 20, net_y)
            
            # Draw sensor status
            sensor_y = self._draw_section("Sensor Status", "", 10, net_y + 190, 
                                        self.ui_width - 20, 100)
            self._draw_sensor_status(gpio_controller, 20, sensor_y)
            
            # Draw alert if present
            if self.current_status['alert']:
                alert_y = self._draw_section("Alert", "", 10, sensor_y + 110, 
                                           self.ui_width - 20, 60, highlight=True)
                self.drawer.text((20, alert_y), self.current_status['alert'], 
                            font=self.font, fill=(255, 0, 0))
            
            # Draw system log
            log_y = self._draw_section("System Log", "", 10, sensor_y + 180, 
                                     self.ui_width - 20, 170)
            self._draw_log(20, log_y)
            
            # Draw camera view
            self._draw_camera_view(self.ui_width + 10, 10,
                                 self.image_width - 20,
                                 self.fb['height'] - 20)
            
            # Update framebuffer
            self._update_framebuffer()
            self.last_draw_time = current_time
            
        except Exception as e:
            print(f"Error updating display: {e}")
            import traceback
            traceback.print_exc()

    def _draw_section(self, title, content, x, y, width, height, highlight=False):
        """Draw a section with title and content using original style"""
        # Draw section box
        self.drawer.rectangle([x, y, x + width, y + height], outline=(255, 255, 255))
        
        # Draw title background
        title_bg_color = (255, 0, 0) if highlight else (0, 0, 255)
        self.drawer.rectangle([x + 1, y + 1, x + width - 1, y + 20], fill=title_bg_color)
        
        # Draw title text
        self.drawer.text((x + 5, y + 2), title, font=self.font, fill=(255, 255, 255))
        
        return y + 22

    def _draw_network_status(self, network_status, x, y):
        """Draw network status with original styling"""
        statuses = network_status.status
        y_offset = 0
        
        for service, info in statuses.items():
            # Main status with color coding
            color = (0, 255, 0) if info.get('status', 'Unknown') == 'Connected' else (255, 0, 0)
            text = f"{service.title()}: {info.get('status', 'Unknown')}"
            self.drawer.text((x, y + y_offset), text, font=self.font, fill=color)
            y_offset += 15
            
            if service in ['camera', 'ai_server']:
                if info.get('ip'):
                    self.drawer.text((x + 20, y + y_offset),
                                f"IP: {info['ip']}", 
                                font=self.font, 
                                fill=(255, 255, 255))
                    y_offset += 12

                if info.get('ping_time'):
                    self.drawer.text((x + 20, y + y_offset),
                                f"Ping: {info['ping_time']}", 
                                font=self.font, 
                                fill=(255, 255, 255))
                    y_offset += 12

                if info.get('last_success'):
                    last_success = network_status.format_last_success(info['last_success'])
                    self.drawer.text((x + 20, y + y_offset),
                                f"Last: {last_success}", 
                                font=self.font, 
                                fill=(255, 255, 255))
                    y_offset += 12
            
            y_offset += 5

    def _draw_sensor_status(self, gpio_controller, x, y):
        """Draw sensor status including AI toggle switch"""
        sensor_states = [
            ("Sensor 1", gpio_controller.read_sensor1()),
            ("Sensor 2", gpio_controller.read_sensor2()),
            ("Solenoid", gpio_controller.get_solenoid_state()),
            ("Ejection", gpio_controller.get_ejection_state()),
            ("AI Disabled", gpio_controller.read_ai_toggle_switch()),  # Inverted because True means AI is disabled
        ]
        
        for i, (name, state) in enumerate(sensor_states):
            color = (0, 255, 0) if state else (255, 0, 0)
            status_text = 'Active' if state else 'Inactive'
            text = f"{name}: {status_text}"
            
            # Draw status indicator circle
            circle_x = x + 5
            circle_y = y + (i * 20) + 7
            self.drawer.ellipse([circle_x, circle_y, circle_x + 8, circle_y + 8], fill=color)
            
            # Draw text with padding for circle
            self.drawer.text((x + 20, y + i * 20), text, font=self.font, fill=(255, 255, 255))

    def _draw_log(self, x, y):
        """Draw system log with original styling"""
        visible_messages = self.status_messages[-8:]
        
        for i, message in enumerate(visible_messages):
            color = (255, 0, 0) if 'ALERT:' in message else (
                    0, 255, 255) if 'NETWORK:' in message else (200, 200, 200)
            
            max_chars = 80
            display_message = message[:max_chars] + '...' if len(message) > max_chars else message
            
            self.drawer.text((x, y + i * 15), display_message, font=self.font, fill=color)

    def _get_text_width(self, text):
        """Get text width using current font"""
        if hasattr(self.drawer, 'textlength'):
            return self.drawer.textlength(text, font=self.font)
        else:
            bbox = self.drawer.textbbox((0, 0), text, font=self.font)
            return bbox[2] - bbox[0]

    def _rgb_to_rgb565(self, r, g, b):
        """Convert RGB888 to RGB565"""
        r = (r >> 3) & 0x1F
        g = (g >> 2) & 0x3F
        b = (b >> 3) & 0x1F
        return (r << 11) | (g << 5) | b

    def _update_framebuffer(self):
        """Convert PIL image to framebuffer format and update display"""
        # Convert PIL image to numpy array
        image_array = np.array(self.image)
        height, width, _ = image_array.shape
        
        # Create numpy arrays for RGB components
        r = image_array[:, :, 0].astype(np.uint16)
        g = image_array[:, :, 1].astype(np.uint16)
        b = image_array[:, :, 2].astype(np.uint16)
        
        # Convert to RGB565 format
        rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        
        # Convert to bytes in correct order
        fb_bytes = np.zeros((height, width, 2), dtype=np.uint8)
        fb_bytes[:, :, 0] = rgb565 & 0xFF  # Low byte
        fb_bytes[:, :, 1] = (rgb565 >> 8) & 0xFF  # High byte
        
        # Write to framebuffer
        self.fb['fb'].seek(0)
        self.fb['fb'].write(fb_bytes.tobytes())