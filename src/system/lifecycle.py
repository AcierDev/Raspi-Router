# src/system/lifecycle.py
import asyncio
import logging
import signal
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import AsyncExitStack

from ..imaging import ImageProcessor
from ..network import NetworkMonitor
from ..ui import FBUIManager, CursesUIManager
from .state import SystemState
from ..config import (
    IMAGE_URL,
    INFERENCE_URL,
    NETWORK_CHECK_INTERVAL,
    SENSOR2_WAIT_TIME
)

logger = logging.getLogger(__name__)

class SystemLifecycle:
    """Handles system lifecycle management including initialization and shutdown"""

    @staticmethod
    async def initialize_components(use_framebuffer: bool, state: SystemState) -> tuple[Dict[str, Any], AsyncExitStack]:
        """
        Initialize all system components.
        
        Args:
            use_framebuffer: Whether to use framebuffer UI
            state: System state object
            
        Returns:
            Tuple of (components dict, AsyncExitStack)
        """
        components = {}
        exit_stack = AsyncExitStack()

        try:
            # Initialize GPIO
            from ..hardware import GPIOController
            components['gpio'] = GPIOController()
            
            # Initialize UI
            if use_framebuffer:
                components['ui'] = FBUIManager()
            else:
                components['ui'] = CursesUIManager()

            # Initialize network monitor
            network_monitor = await exit_stack.enter_async_context(
                NetworkMonitor(lambda status: SystemLifecycle._handle_network_status(status, components['ui']))
            )
            components['network'] = network_monitor

            # Initialize image processor
            image_processor = await exit_stack.enter_async_context(
                ImageProcessor(components['ui'].update_status_message)
            )
            components['processor'] = image_processor

            logger.info("System initialization complete")
            return components, exit_stack

        except Exception as e:
            logger.error(f"Initialization error: {e}")
            await exit_stack.aclose()
            raise

    @staticmethod
    async def setup_signal_handlers(state: SystemState) -> None:
        """Set up system signal handlers"""
        def signal_handler(sig):
            logger.info(f"Received signal {sig}")
            state.shutdown_requested = True
            
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_event_loop().add_signal_handler(
                sig,
                lambda s=sig: signal_handler(s)
            )

    @staticmethod
    async def _handle_network_status(status: Dict[str, Any], ui_manager) -> None:
        """Handle network status updates"""
        if any(s['status'] == 'Disconnected' for s in status.values()):
            ui_manager.update_status_message(
                "Network connectivity issues detected",
                is_network=True
            )

    @staticmethod
    async def cleanup_components(components: Dict[str, Any], exit_stack: AsyncExitStack) -> None:
        """Clean up system resources"""
        logger.info("Starting system cleanup")
        
        try:
            await exit_stack.aclose()
            
            for name, component in components.items():
                try:
                    if hasattr(component, 'cleanup'):
                        if asyncio.iscoroutinefunction(component.cleanup):
                            await component.cleanup()
                        else:
                            component.cleanup()
                    logger.info(f"Cleaned up {name} component")
                except Exception as e:
                    logger.error(f"Error cleaning up {name}: {e}")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            logger.info("System cleanup complete")