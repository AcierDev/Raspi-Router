# ui/curses_ui.py

import curses
from datetime import datetime
from .base_ui import BaseUI

class CursesUI(BaseUI):
    def __init__(self):
        super().__init__()
        self.height = 0
        self.width = 0

    def draw(self, stdscr, gpio_controller, network_status):
        """Draw the curses-based UI"""
        self.height, self.width = stdscr.getmaxyx()
        stdscr.clear()

        # Draw title
        title = "Automated Inspection System"
        stdscr.addstr(0, (self.width - len(title)) // 2, title, curses.A_BOLD)

        # Draw state
        state_str = f"State: {self.current_status['state'].replace('_', ' ').title()}"
        stdscr.addstr(2, 2, state_str)

        # Draw network status
        self._draw_network_section(stdscr, network_status, 4)

        # Draw sensor status
        self._draw_sensor_section(stdscr, gpio_controller, 12)

        # Draw alert if present
        if self.current_status['alert']:
            self._draw_alert_section(stdscr, 16)

        # Draw log messages
        self._draw_log_section(stdscr, 18)

        # Draw current time
        self._draw_time(stdscr)

    def _draw_network_section(self, stdscr, network_status, start_y):
        """Draw network status information"""
        stdscr.addstr(start_y, 2, "Network Status:", curses.A_UNDERLINE)
        y = start_y + 1

        for service in ['internet', 'camera', 'ai_server']:
            status_text = self.get_network_status_text(network_status, service)
            for i, line in enumerate(status_text.split('\n')):
                color = (curses.A_BOLD if 'Connected' in line else curses.A_NORMAL)
                stdscr.addstr(y + i, 4, line, color)
            y += status_text.count('\n') + 2

    def _draw_sensor_section(self, stdscr, gpio_controller, start_y):
        """Draw sensor status information"""
        stdscr.addstr(start_y, 2, "Sensor Status:", curses.A_UNDERLINE)
        
        for i, (name, state) in enumerate(self.get_sensor_status_text(gpio_controller)):
            status = 'Active' if state else 'Inactive'
            line = f"{name}: {status}"
            stdscr.addstr(start_y + i + 1, 4, line, 
                         curses.A_BOLD if state else curses.A_NORMAL)

    def _draw_alert_section(self, stdscr, start_y):
        """Draw alert message if present"""
        stdscr.addstr(start_y, 2, "Alert:", curses.A_UNDERLINE | curses.A_BOLD)
        stdscr.addstr(start_y + 1, 4, self.current_status['alert'], 
                     curses.A_BOLD)

    def _draw_log_section(self, stdscr, start_y):
        """Draw system log messages"""
        stdscr.addstr(start_y, 2, "System Log:", curses.A_UNDERLINE)
        
        for i, message in enumerate(self.get_visible_messages()):
            if start_y + i + 1 < self.height - 1:  # Ensure we don't write past screen
                message = self.format_status_message(message, self.width - 6)
                attr = (curses.A_BOLD if "ALERT:" in message else 
                       curses.A_DIM if "NETWORK:" in message else 
                       curses.A_NORMAL)
                stdscr.addstr(start_y + i + 1, 4, message, attr)

    def _draw_time(self, stdscr):
        """Draw current time in top right corner"""
        time_str = datetime.now().strftime("%H:%M:%S")
        try:
            stdscr.addstr(0, self.width - len(time_str) - 2, time_str)
        except curses.error:
            pass  # Ignore if screen too small