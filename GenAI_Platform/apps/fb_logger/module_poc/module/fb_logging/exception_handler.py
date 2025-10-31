import sys
from .core import logger

def handle_exception(exc_type, exc_value, exc_traceback):
    """
    Handles uncaught exceptions and logs a custom error message.

    Args:
        exc_type (type): Exception type.
        exc_value (Exception): Exception instance.
        exc_traceback (traceback): Traceback object.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        # Ignore KeyboardException but just redirect
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.stacktrace((exc_type, exc_value, exc_traceback), start_message="UNEXPECTED FATAL ERROR OCCURRED!!!")

# Override global exception hook
sys.excepthook = handle_exception
