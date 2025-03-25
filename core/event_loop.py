# core/event_loop.py
import asyncio
import logging
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class EventLoopManager:
    """
    Manages the event loop lifecycle to prevent 'Event loop is closed' errors.
    """
    
    def __init__(self):
        self._loop = None
        self._loop_lock = threading.Lock()
    
    @contextmanager
    def get_loop(self):
        """Get or create an event loop that's guaranteed to be open."""
        with self._loop_lock:
            try:
                # Check if we have a loop and it's still running
                if self._loop is None or self._loop.is_closed():
                    self._loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self._loop)
                    logger.debug("Created new event loop")
                
                yield self._loop
            except Exception as e:
                logger.error(f"Error in event loop: {str(e)}")
                # Clean up if there was an error
                if self._loop and not self._loop.is_closed():
                    self._loop.close()
                self._loop = None
                raise
    
    def run_async(self, coro):
        """Run a coroutine in the managed event loop."""
        with self.get_loop() as loop:
            return loop.run_until_complete(coro)
    
    def close(self):
        """Close the current event loop if it exists."""
        with self._loop_lock:
            if self._loop and not self._loop.is_closed():
                self._loop.close()
                self._loop = None
                logger.debug("Closed event loop")

# Create a global instance
loop_manager = EventLoopManager()