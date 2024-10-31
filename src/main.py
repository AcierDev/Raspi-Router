# src/main.py
import asyncio
import argparse
import logging
import sys
from pathlib import Path

from .system.state import SystemState
from .system.lifecycle import SystemLifecycle
from .system.inspection import InspectionSystem
from .config import IMAGE_URL, INFERENCE_URL, LOG_LEVEL, NETWORK_CHECK_INTERVAL

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path('inspection_system.log'))
    ]
)
logger = logging.getLogger(__name__)

async def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(
        description='Run the inspection system with either curses or framebuffer UI'
    )
    parser.add_argument(
        '--hdmi',
        action='store_true',
        help='Use HDMI output (framebuffer) instead of curses'
    )
    args = parser.parse_args()

    # Create system state
    state = SystemState()
    
    try:
        # Initialize components
        components, exit_stack = await SystemLifecycle.initialize_components(args.hdmi, state)
        
        # Set up signal handlers
        await SystemLifecycle.setup_signal_handlers(state)
        
        # Create inspection system
        system = InspectionSystem(components, state)
        
        # Start network monitoring
        network = components['network']
        monitoring_task = asyncio.create_task(
            network.start_monitoring(
                IMAGE_URL,
                INFERENCE_URL,
                NETWORK_CHECK_INTERVAL
            )
        )

        # Main processing loop
        while not state.shutdown_requested:
            try:
                await system.process_cycle()
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Processing cycle error: {e}")
                state.error_state = True

        # Clean shutdown
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass

    except Exception as e:
        logger.critical(f"Fatal error in main loop: {e}")
        return 1
    finally:
        if 'exit_stack' in locals():
            await SystemLifecycle.cleanup_components(components, exit_stack)

    return 0

if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)