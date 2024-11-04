# src/system/inspection.py
import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

from src.ui.fb_manager import FBUIManager

from .state import SystemState
from ..config import IMAGE_URL, INFERENCE_URL, SENSOR2_WAIT_TIME

logger = logging.getLogger(__name__)

class InspectionSystem:
    """Main inspection system controller"""

    def __init__(self, components: Dict[str, Any], state: SystemState):
        """
        Initialize the inspection system.
        
        Args:
            components: Dictionary of system components
            state: System state object
        """
        self.components = components
        self.state = state
        self._processing_lock = asyncio.Lock()

    async def process_cycle(self) -> None:
        """Process a single system cycle"""
        gpio = self.components['gpio']
        ui = self.components['ui']

        if self.state.error_state:
            await self._handle_error_recovery()
            return

        # Normal state processing
        if not self.state.piece_in_progress:
            if gpio.read_sensor1():
                self.state.piece_in_progress = True
                ui.update_status_message("Piece detected - activating solenoid")
                self.state.waiting_for_sensor2 = False

        if self.state.piece_in_progress:
            await self._handle_piece_processing()

        # Update UI
        await self._update_ui()

    async def _handle_piece_processing(self) -> None:
        """Handle piece processing state machine"""
        gpio = self.components['gpio']
        ui = self.components['ui']
        current_time = asyncio.get_event_loop().time()

        if gpio.read_sensor1():
            gpio.set_solenoid(True)
        else:
            gpio.set_solenoid(False)

            if not self.state.waiting_for_sensor2:
                self.state.waiting_for_sensor2 = True
                self.state.sensor2_check_time = current_time
                ui.update_status_message(
                    "Sensor 1 released - waiting for piece to reach slot..."
                )

            if self.state.waiting_for_sensor2 and \
               (current_time - self.state.sensor2_check_time > SENSOR2_WAIT_TIME):
                
                if not gpio.read_sensor2():
                    ui.update_status_message("No piece fell in slot!", is_alert=True)
                    self.state.error_state = True
                else:
                    await self._process_piece()

                self.state.piece_in_progress = False
                self.state.waiting_for_sensor2 = False

    async def _process_piece(self) -> None:
        """Process a single piece with image capture and analysis"""
        async with self._processing_lock:
            if self.state.processing_active:
                return

            self.state.processing_active = True
            ui = self.components['ui']
            processor = self.components['processor']

            try:
                ui.update_status_message("=== Starting piece processing ===")
                ui.clear_image()

                # Image capture
                image_data = await asyncio.wait_for(
                    processor.get_image(IMAGE_URL),
                    timeout=30
                )

                if not image_data:
                    raise RuntimeError("Failed to capture image")

                ui.set_current_image(image_data)
                ui.update_status_message("Image captured successfully")

                # Image analysis
                analysis_result = await asyncio.wait_for(
                    processor.send_for_analysis(INFERENCE_URL, image_data),
                    timeout=30
                )

                if analysis_result:
                    ui.current_status.last_inference = datetime.now().strftime("%H:%M:%S")
                    ui.current_status.last_confidence = analysis_result.confidence
                    ui.update_status_message(
                        f"Analysis complete - confidence: {analysis_result.confidence:.1%}"
                    )
                else:
                    ui.update_status_message("Analysis complete - no confident predictions")

            except asyncio.TimeoutError:
                ui.update_status_message("Operation timed out", is_alert=True)
            except Exception as e:
                ui.update_status_message(f"Processing error: {str(e)}", is_alert=True)
                logger.error(f"Piece processing error: {e}")
            finally:
                ui.update_status_message("=== Piece processing complete ===")
                self.state.processing_active = False

    async def _handle_error_recovery(self) -> None:
        """Handle system error recovery"""
        gpio = self.components['gpio']
        ui = self.components['ui']

        if gpio.read_sensor1():
            ui.update_status_message("Restarting cycle from sensor 1")
            self.state.error_state = False
            self.state.piece_in_progress = True
            self.state.waiting_for_sensor2 = False
        elif gpio.read_sensor2():
            ui.update_status_message("Manual piece placement detected")
            await self._process_piece()
            self.state.error_state = False

    async def _update_ui(self) -> None:
        """Update the UI display"""
        ui = self.components['ui']
        gpio = self.components['gpio']
        network = self.components['network']

        if isinstance(ui, FBUIManager):
            ui.update_display(gpio, network)
        else:
            ui.draw(gpio, network)