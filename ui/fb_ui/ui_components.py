# ui/fb_ui/ui_components.py

class UIComponentDrawer:
    def draw_all_components(self, ui, gpio_controller, network_status):
        # Draw title
        title = "Automated Inspection System"
        title_w = self._get_text_width(ui, title)
        ui.drawer.text(((ui.ui_width - title_w) // 2, 10), title, 
                    font=ui.font, fill=(255, 255, 255))
        
        # Draw state
        state_str = f"State: {ui.current_status['state'].replace('_', ' ').title()}"
        ui.drawer.text((10, 40), state_str, font=ui.font, fill=(255, 255, 255))
        
        # Draw sections
        metrics_y = self._draw_metrics_section(ui, 10, 70, ui.ui_width - 20)
        net_y = self._draw_section(ui, "Network Status", "", 10, metrics_y + 50, 
                                 ui.ui_width - 20, 180)
        self._draw_network_status(ui, network_status, 20, net_y)
        
        sensor_y = self._draw_section(ui, "Sensor Status", "", 10, net_y + 190, 
                                    ui.ui_width - 20, 140)
        self._draw_sensor_status(ui, gpio_controller, 20, sensor_y)
        
        if ui.current_status['alert']:
            alert_y = self._draw_section(ui, "Alert", "", 10, sensor_y + 110, 
                                       ui.ui_width - 20, 60, highlight=True)
            ui.drawer.text((20, alert_y), ui.current_status['alert'], 
                        font=ui.font, fill=(255, 0, 0))
        
        log_y = self._draw_section(ui, "System Log", "", 10, sensor_y + 180, 
                                 ui.ui_width - 20, 170)
        self._draw_log(ui, 20, log_y)
        
        self._draw_camera_view(ui, ui.ui_width + 10, 10,
                             ui.image_width - 20,
                             ui.fb['height'] - 20)

    def _draw_metrics_section(self, ui, x, y, width):
        """Draw comprehensive metrics section"""
        current_time = ui.metrics.metrics['start_time']
        uptime = current_time - ui.metrics.metrics['start_time']
        
        # Calculate statistics
        total_processed = ui.metrics.metrics['processed_count']
        total_defects = sum(ui.metrics.metrics['defect_counts'].values())
        avg_defects = total_defects / max(1, total_processed)
        
        # Calculate processing time statistics
        if ui.metrics.processing_stats['count'] > 0:
            avg_time = ui.metrics.processing_stats['total_time'] / ui.metrics.processing_stats['count']
            min_time = ui.metrics.processing_stats['min_time']
            max_time = ui.metrics.processing_stats['max_time']
            last_time = ui.metrics.metrics['last_process_time']
        else:
            avg_time = min_time = max_time = last_time = 0
        
        # Draw metrics section background
        metrics_y = self._draw_section(ui, "System Metrics", "", x, y, width, 320)
        
        # Draw basic metrics
        ui.drawer.text((x + 10, metrics_y), f"Uptime: {str(uptime).split('.')[0]}", 
                    font=ui.font, fill=(255, 255, 255))
        metrics_y += 20
        
        ui.drawer.text((x + 10, metrics_y), f"Total Processed: {total_processed}", 
                    font=ui.font, fill=(255, 255, 255))
        metrics_y += 20
        
        # Draw processing time metrics with colored values
        if last_time is not None:
            last_color = (255, 165, 0) if last_time > avg_time * 1.5 else (255, 255, 255)
            ui.drawer.text((x + 10, metrics_y), f"Last Process: {last_time:.2f}s", 
                       font=ui.font, fill=last_color)
        metrics_y += 20
        
        ui.drawer.text((x + 10, metrics_y), f"Avg Process: {avg_time:.2f}s", 
                    font=ui.font, fill=(255, 255, 255))
        metrics_y += 20
        
        ui.drawer.text((x + 10, metrics_y), f"Min Process: {min_time:.2f}s", 
                    font=ui.font, fill=(0, 255, 0))
        metrics_y += 20
        
        ui.drawer.text((x + 10, metrics_y), f"Max Process: {max_time:.2f}s", 
                    font=ui.font, fill=(255, 0, 0))
        metrics_y += 30
        
        # Draw defect metrics
        ui.drawer.text((x + 10, metrics_y), f"Total Defects: {total_defects}", 
                    font=ui.font, fill=(255, 255, 255))
        metrics_y += 20
        
        ui.drawer.text((x + 10, metrics_y), f"Avg Defects/Item: {avg_defects:.2f}", 
                    font=ui.font, fill=(255, 255, 255))
        metrics_y += 20
        
        # Draw error metrics
        error_rate = (ui.metrics.metrics['error_count'] / max(1, total_processed)) * 100
        ui.drawer.text((x + 10, metrics_y), f"Errors: {ui.metrics.metrics['error_count']} ({error_rate:.1f}%)", 
                    font=ui.font, fill=(255, 0, 0))
        metrics_y += 30
        
        # Draw defect type breakdown
        ui.drawer.text((x + 10, metrics_y), "Defect Types:", 
                    font=ui.font, fill=(255, 255, 255))
        metrics_y += 20
        
        for defect_type, count in sorted(ui.metrics.metrics['defect_counts'].items()):
            color = ui.defect_colors.get(defect_type.lower(), ui.defect_colors['default'])
            percentage = (count / max(1, total_defects)) * 100
            ui.drawer.text((x + 20, metrics_y), 
                       f"{defect_type}: {count} ({percentage:.1f}%)", 
                       font=ui.small_font, fill=color)
            metrics_y += 15
        
        return metrics_y + 10

    def _draw_section(self, ui, title, content, x, y, width, height, highlight=False):
        """Draw a section with title and content"""
        # Draw section box
        ui.drawer.rectangle([x, y, x + width, y + height], outline=(255, 255, 255))
        
        # Draw title background
        title_bg_color = (255, 0, 0) if highlight else (0, 0, 255)
        ui.drawer.rectangle([x + 1, y + 1, x + width - 1, y + 20], fill=title_bg_color)
        
        # Draw title text
        ui.drawer.text((x + 5, y + 2), title, font=ui.font, fill=(255, 255, 255))
        
        return y + 22

    def _draw_network_status(self, ui, network_status, x, y):
        """Draw network status with styling"""
        statuses = network_status.status
        y_offset = 0
        
        for service, info in statuses.items():
            # Main status with color coding
            color = (0, 255, 0) if info.get('status', 'Unknown') == 'Connected' else (255, 0, 0)
            text = f"{service.title()}: {info.get('status', 'Unknown')}"
            ui.drawer.text((x, y + y_offset), text, font=ui.font, fill=color)
            y_offset += 15
            
            if service in ['camera', 'ai_server']:
                if info.get('ip'):
                    ui.drawer.text((x + 20, y + y_offset),
                                f"IP: {info['ip']}", 
                                font=ui.font, 
                                fill=(255, 255, 255))
                    y_offset += 12

                if info.get('ping_time'):
                    ui.drawer.text((x + 20, y + y_offset),
                                f"Ping: {info['ping_time']}", 
                                font=ui.font, 
                                fill=(255, 255, 255))
                    y_offset += 12

                if info.get('last_success'):
                    last_success = network_status.format_last_success(info['last_success'])
                    ui.drawer.text((x + 20, y + y_offset),
                                f"Last: {last_success}", 
                                font=ui.font, 
                                fill=(255, 255, 255))
                    y_offset += 12
            
            y_offset += 5

    def _draw_sensor_status(self, ui, gpio_controller, x, y):
        """Draw sensor status including AI toggle switch"""
        sensor_states = [
            ("Sensor 1", gpio_controller.read_sensor1()),
            ("Sensor 2", gpio_controller.read_sensor2()),
            ("Solenoid", gpio_controller.get_solenoid_state()),
            ("Ejection", gpio_controller.get_ejection_state()),
            ("AI Disabled", gpio_controller.read_ai_toggle_switch()),
        ]
        
        for i, (name, state) in enumerate(sensor_states):
            color = (0, 255, 0) if state else (255, 0, 0)
            status_text = 'Active' if state else 'Inactive'
            text = f"{name}: {status_text}"
            
            # Draw status indicator circle
            circle_x = x + 5
            circle_y = y + (i * 20) + 7
            ui.drawer.ellipse([circle_x, circle_y, circle_x + 8, circle_y + 8], fill=color)
            
            # Draw text with padding for circle
            ui.drawer.text((x + 20, y + i * 20), text, font=ui.font, fill=(255, 255, 255))

    def _draw_log(self, ui, x, y):
        """Draw system log with styling"""
        visible_messages = ui.status_messages[-8:]
        
        for i, message in enumerate(visible_messages):
            color = (255, 0, 0) if 'ALERT:' in message else (
                    0, 255, 255) if 'NETWORK:' in message else (200, 200, 200)
            
            max_chars = 80
            display_message = message[:max_chars] + '...' if len(message) > max_chars else message
            
            ui.drawer.text((x, y + i * 15), display_message, font=ui.font, fill=color)

    def _get_text_width(self, ui, text):
        """Get text width using current font"""
        if hasattr(ui.drawer, 'textlength'):
            return ui.drawer.textlength(text, font=ui.font)
        else:
            bbox = ui.drawer.textbbox((0, 0), text, font=ui.font)
            return bbox[2] - bbox[0]

    def _draw_camera_view(self, ui, x, y, width, height):
        """Draw the camera image with detection overlays"""
        # Draw border
        ui.drawer.rectangle([x, y, x + width, y + height], outline=(255, 255, 255))
        
        if ui.current_image and hasattr(ui.current_image, 'mode'):
            try:
                # Only print debug once per image update
                if not hasattr(ui, '_last_image_debug'):
                    print(f"Drawing image: original size={ui.current_image.size}")
                    ui._last_image_debug = ui.current_image.size
                elif ui._last_image_debug != ui.current_image.size:
                    print(f"Drawing new image: original size={ui.current_image.size}")
                    ui._last_image_debug = ui.current_image.size
                
                # Create a copy for resizing
                img_copy = ui.current_image.copy()
                img_copy.thumbnail((width - 4, height - 4))
                
                # Calculate position to center the image
                img_x = x + 2 + (width - 4 - img_copy.width) // 2
                img_y = y + 2 + (height - 4 - img_copy.height) // 2
                
                # Paste the image
                ui.image.paste(img_copy, (img_x, img_y))
                
                # Draw detections if available
                if ui.current_predictions and 'predictions' in ui.current_predictions:
                    self._draw_detections(ui, ui.current_predictions['predictions'], 
                                        img_x, img_y, img_copy.width, img_copy.height)
                    
                # Draw timestamp
                if ui.image_timestamp:
                    timestamp_str = f"Captured: {ui.image_timestamp.strftime('%H:%M:%S')}"
                    ui.drawer.text(
                        (x + 5, y + 5),
                        timestamp_str,
                        font=ui.font,
                        fill=(255, 255, 0)
                    )
                    
            except Exception as e:
                print(f"Error drawing camera view: {e}")
                import traceback
                traceback.print_exc()
                self._draw_placeholder(ui, x, y, width, height)
        else:
            self._draw_placeholder(ui, x, y, width, height)

    def _draw_detections(self, ui, predictions, img_x, img_y, img_width, img_height):
        """Draw detection boxes and labels on the image"""
        print(f"Drawing {len(predictions)} detections")
        print(f"Image dimensions: {img_width}x{img_height} at ({img_x}, {img_y})")
        
        # Get actual image dimensions from metadata
        if ui.current_predictions and 'metadata' in ui.current_predictions:
            metadata = ui.current_predictions['metadata']
            source_width = metadata.get('image_size', {}).get('width', 1920)
            source_height = metadata.get('image_size', {}).get('height', 1080)
        else:
            source_width = 1920  # Default values if metadata not available
            source_height = 1080
        
        print(f"Source image dimensions: {source_width}x{source_height}")
        
        # Calculate scaling factors
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
                color = ui.defect_colors.get(class_name.lower(), ui.defect_colors['default'])
                
                # Draw box with minimum width of 2 pixels
                ui.drawer.rectangle([x1, y1, x2, y2], outline=color, width=2)
                
                # Prepare label text
                label = f"{class_name} {confidence:.1%}"
                
                # Draw label background
                text_bb = ui.drawer.textbbox((0, 0), label, font=ui.small_font)
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
                
                ui.drawer.rectangle(
                    [label_x, label_y, label_x + text_width + 2*margin, label_y + text_height + 2*margin],
                    fill=color
                )
                
                # Draw label text
                ui.drawer.text(
                    (label_x + margin, label_y + margin),
                    label,
                    font=ui.small_font,
                    fill=(0, 0, 0)
                )
                
            except Exception as e:
                print(f"Error drawing detection {i}: {e}")
                import traceback
                traceback.print_exc()
                continue

    def _draw_detection_summary(self, ui, x, y):
        """Draw detection summary at the bottom of the image"""
        summary = ui.current_predictions['summary']
        
        # Draw background
        padding = 5
        line_height = 15
        num_lines = len(summary['class_counts']) + 1
        
        ui.drawer.rectangle(
            [x - padding, y - padding,
             x + 200, y + (line_height * num_lines) + padding],
            fill=(0, 0, 0, 128)
        )
        
        # Draw total count
        ui.drawer.text(
            (x, y),
            f"Total defects: {summary['count']}",
            font=ui.small_font,
            fill=(255, 255, 255)
        )
        
        # Draw counts by type
        y_offset = line_height
        for class_name, count in summary['class_counts'].items():
            color = ui.defect_colors.get(class_name.lower(), ui.defect_colors['default'])
            ui.drawer.text(
                (x, y + y_offset),
                f"• {class_name}: {count}",
                font=ui.small_font,
                fill=color
            )
            y_offset += line_height

    def _draw_placeholder(self, ui, x, y, width, height):
        """Draw placeholder when no image is available"""
        text = "No Camera Image"
        text_bbox = ui.drawer.textbbox((0, 0), text, font=ui.font)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = x + (width - text_width) // 2
        text_y = y + height // 2 - 10
        ui.drawer.text((text_x, text_y), text, font=ui.font, fill=(128, 128, 128))