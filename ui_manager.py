import curses
from datetime import datetime
from config import MAX_LOG_MESSAGES, VISIBLE_LOG_MESSAGES

class UIManager:
    def __init__(self):
        self.status_messages = []
        self.current_status = {
            'state': 'normal',
            'alert': None,
            'last_inference': None,
            'last_confidence': None,
            'system_status': 'Running'
        }

    def update_status_message(self, message, is_alert=False, is_network=False):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = "ALERT: " if is_alert else "NETWORK: " if is_network else ""
        self.status_messages.append(f"[{timestamp}] {prefix}{message}")
        if len(self.status_messages) > MAX_LOG_MESSAGES:
            self.status_messages.pop(0)

    def get_status_color(self, status):
        if status == 'Connected':
            return curses.A_BOLD
        elif status == 'Disconnected':
            return curses.A_REVERSE
        return curses.A_DIM

    def draw_network_status(self, stdscr, start_y, network_status):
        # Section Title
        stdscr.addstr(start_y, 2, "=== Network Status ===", curses.A_BOLD)
        
        # Internet status (y+2)
        status_attr = self.get_status_color(network_status.status['internet']['status'])
        stdscr.addstr(start_y + 2, 4, "Internet:   ")
        stdscr.addstr(f"{network_status.status['internet']['status']:<11}", status_attr)
        stdscr.addstr(f" Last: {network_status.format_last_success(network_status.status['internet']['last_success'])}")
        
        # Camera status (y+4, y+5)
        stdscr.addstr(start_y + 4, 4, "Camera:")
        host_attr = self.get_status_color(network_status.status['camera']['host_status'])
        service_attr = self.get_status_color(network_status.status['camera']['service_status'])
        
        # Camera Host (y+5)
        stdscr.addstr(start_y + 5, 6, f"Host:    {network_status.status['camera']['host_status']:<11}", host_attr)
        if network_status.status['camera']['ping_time']:
            stdscr.addstr(f" [{network_status.status['camera']['ping_time']}]")
            
        # Camera Service (y+6)
        stdscr.addstr(start_y + 6, 6, f"Service: {network_status.status['camera']['service_status']:<11}", service_attr)
        if network_status.status['camera']['response_time']:
            stdscr.addstr(f" [{network_status.status['camera']['response_time']}]")
        
        # AI Server status (y+8, y+9, y+10)
        stdscr.addstr(start_y + 8, 4, "AI Server:")
        host_attr = self.get_status_color(network_status.status['ai_server']['host_status'])
        service_attr = self.get_status_color(network_status.status['ai_server']['service_status'])
        
        # AI Server Host (y+9)
        stdscr.addstr(start_y + 9, 6, f"Host:    {network_status.status['ai_server']['host_status']:<11}", host_attr)
        if network_status.status['ai_server']['ping_time']:
            stdscr.addstr(f" [{network_status.status['ai_server']['ping_time']}]")
            
        # AI Server Service (y+10)
        stdscr.addstr(start_y + 10, 6, f"Service: {network_status.status['ai_server']['service_status']:<11}", service_attr)
        if network_status.status['ai_server']['response_time']:
            stdscr.addstr(f" [{network_status.status['ai_server']['response_time']}]")

    def draw_sensor_status(self, stdscr, start_y, gpio_controller):
        # Section Title
        stdscr.addstr(start_y, 2, "=== Sensor Status ===", curses.A_BOLD)
        
        # Format sensor states with visual indicators
        sensor1_state = "Active" if gpio_controller.read_sensor1() else "Inactive"
        sensor2_state = "Active" if gpio_controller.read_sensor2() else "Inactive"
        solenoid_state = "Active (ON)" if gpio_controller.get_solenoid_state() else "Inactive (OFF)"
        
        # Add visual emphasis for active states
        stdscr.addstr(start_y + 2, 4, f"Sensor 1: ")
        stdscr.addstr(f"{sensor1_state}", curses.A_BOLD if gpio_controller.read_sensor1() else curses.A_NORMAL)
        
        stdscr.addstr(start_y + 3, 4, f"Sensor 2: ")
        stdscr.addstr(f"{sensor2_state}", curses.A_BOLD if gpio_controller.read_sensor2() else curses.A_NORMAL)
        
        stdscr.addstr(start_y + 4, 4, f"Solenoid: ")
        stdscr.addstr(f"{solenoid_state}", curses.A_BOLD if gpio_controller.get_solenoid_state() else curses.A_NORMAL)

    def draw_alert(self, stdscr, start_y):
        # Section Title
        stdscr.addstr(start_y, 2, "=== Alert ===", curses.A_BOLD | curses.A_REVERSE)
        stdscr.addstr(start_y + 2, 4, f"{self.current_status['alert']}", curses.A_REVERSE)
        if self.current_status['state'] == 'error_recovery':
            stdscr.addstr(start_y + 3, 4, "Waiting for: Sensor 1 (restart) or Sensor 2 (manual placement)")

    def draw_inference_status(self, stdscr, start_y):
        if self.current_status['last_inference'] or self.current_status['last_confidence']:
            # Section Title
            stdscr.addstr(start_y, 2, "=== Last Inference ===", curses.A_BOLD)
            if self.current_status['last_inference']:
                stdscr.addstr(start_y + 2, 4, f"Time: {self.current_status['last_inference']}")
            if self.current_status['last_confidence']:
                stdscr.addstr(start_y + 3, 4, f"Confidence: {self.current_status['last_confidence']:.2%}")

    def draw_log(self, stdscr, start_y, height, width):
        # Section Title
        stdscr.addstr(start_y, 2, "=== System Log ===", curses.A_BOLD)
        log_start = start_y + 2
        for i, message in enumerate(self.status_messages[-VISIBLE_LOG_MESSAGES:]):
            if log_start + i < height - 1:
                if "ALERT:" in message:
                    stdscr.addstr(log_start + i, 4, message[:width-6], curses.A_REVERSE)
                elif "NETWORK:" in message:
                    stdscr.addstr(log_start + i, 4, message[:width-6], curses.A_BOLD)
                else:
                    stdscr.addstr(log_start + i, 4, message[:width-6])

    def draw(self, stdscr, gpio_controller, network_status):
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        
        # Draw title and state (y: 0, 2)
        title = "Automated Inspection System"
        stdscr.addstr(0, (width - len(title)) // 2, title, curses.A_BOLD)
        state_str = f"State: {self.current_status['state'].replace('_', ' ').title()}"
        stdscr.addstr(2, 2, state_str, curses.A_BOLD)
        
        # Draw system status on the same line as state
        system_status = f"System: {self.current_status['system_status']}"
        stdscr.addstr(2, width - len(system_status) - 2, system_status)
        
        # Network status starts at y=4 (takes 12 lines: 1 title + 1 space + 10 content)
        self.draw_network_status(stdscr, 4, network_status)
        
        # Sensor status starts at y=17 (takes 6 lines: 1 title + 1 space + 4 content)
        self.draw_sensor_status(stdscr, 17, gpio_controller)
        
        # Alert or inference status starts at y=24
        current_y = 24
        if self.current_status['alert']:
            self.draw_alert(stdscr, current_y)
            current_y += 5  # Alert takes 5 lines
            self.draw_inference_status(stdscr, current_y)
            current_y += 5  # Inference status takes 5 lines
        else:
            self.draw_inference_status(stdscr, current_y)
            current_y += 5  # Inference status takes 5 lines
        
        # System log starts after alert/inference (remaining space)
        self.draw_log(stdscr, current_y, height - 1, width)
        
        # Footer
        footer = "Press 'q' to quit"
        stdscr.addstr(height-1, (width - len(footer)) // 2, footer)
        
        stdscr.refresh()