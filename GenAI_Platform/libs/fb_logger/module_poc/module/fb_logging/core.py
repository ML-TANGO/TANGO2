import os
import json
import sys
import traceback
from .constants import DEBUG, INFO, ERROR
from importlib import import_module
from pathlib import Path
import inspect


class Logger:
    def __init__(self, level = os.getenv('LOG_LEVEL', INFO)):
        """
        Initializes the Logger instance with a default log level.
        """
        self.LOG_LEVEL = level

    def set_level(self, level):
        """
        Sets the logging level.

        Args:
            level (int): The log level to set. Use fb_logging.DEBUG, fb_logging.INFO, or fb_logging.ERROR.
        """
        self.LOG_LEVEL = level

    def _log(self, level, message, multiline_start=False, multiline_continued=False):
        """
        Logs a message with specified log level and formatting options.

        Args:
            level (int): The log level to use.
            message (str): The message to log.
            multiline_start (bool, optional): Whether to append "(MultilineStart)" to the message. Defaults to False.
            multiline_continued (bool, optional): Whether to format the message as a continued line. Defaults to False.
        """
        if multiline_start and multiline_continued:
            multiline_continued = False  # MultilineStart takes precedence

        if level == DEBUG:
            header = "[JFB/DEBUG]"
        elif level == INFO:
            header = "[JFB/INFO]"
        elif level == ERROR:
            header = "[JFB/ERROR]"

        if multiline_start:
            message = f"{header} {message} (MultilineStart)"
        elif multiline_continued:
            message = f"| {message}"
        else:
            message = f"{header} {message}"

        print(message, file=sys.stderr)

    def debug(self, message, multiline_start=False, multiline_continued=False):
        """
        Logs a debug message.

        Args:
            message (str): The message to log.
            multiline_start (bool, optional): Whether to append "(MultilineStart)" to the message. Defaults to False.
            multiline_continued (bool, optional): Whether to format the message as a continued line. Defaults to False.
        """
        if self.LOG_LEVEL <= DEBUG:
            self._log(DEBUG, message, multiline_start, multiline_continued)

    def info(self, message, multiline_start=False, multiline_continued=False):
        """
        Logs an info message.

        Args:
            message (str): The message to log.
            multiline_start (bool, optional): Whether to append "(MultilineStart)" to the message. Defaults to False.
            multiline_continued (bool, optional): Whether to format the message as a continued line. Defaults to False.
        """
        if self.LOG_LEVEL <= INFO:
            self._log(INFO, message, multiline_start, multiline_continued)

    def error(self, message, multiline_start=False, multiline_continued=False):
        """
        Logs an error message.

        Args:
            message (str): The message to log.
            multiline_start (bool, optional): Whether to append "(MultilineStart)" to the message. Defaults to False.
            multiline_continued (bool, optional): Whether to format the message as a continued line. Defaults to False.
        """
        if self.LOG_LEVEL <= ERROR:
            self._log(ERROR, message, multiline_start, multiline_continued)

    def stacktrace(self, exc, start_message="An error occurred", log_level=ERROR, end_message="----- MultilineEnd -----"):
        """
        Logs the stack trace of an exception with optional start and end messages.

        Args:
            exc (Exception or tuple): Exception instance or tuple (exc_type, exc_value, exc_traceback).
            start_message (str, optional): The message to log before the stack trace. Set to None to disable. Defaults to "An error occurred".
            log_level (int, optional): The log level to use for the start message. Defaults to ERROR.
            end_message (str, optional): The message to log after the stack trace. Set to None to disable. Defaults to "----- MultilineEnd -----".
        """
        if start_message is not None:
            self._log(log_level, start_message, multiline_start=True)

        if isinstance(exc, tuple):
            trace = traceback.format_exception(*exc)
        else:
            trace = traceback.format_exception(type(exc), exc, exc.__traceback__)

        for line in trace:
            for subline in line.rstrip().split('\n'):
                self._log(log_level, subline, multiline_continued=True)

        if end_message is not None:
            print(end_message, file=sys.stderr)


    def usage(self, data=None, data_string=None, skip_validation=False):
        """
        Logs usage data in JSON format. Accepts JSON string or dictionary/list as input.

        Args:
            data (dict or list): Dictionary or list to be logged as JSON.
            data_string (str): JSON string to be logged.
            skip_validation (bool, optional): Whether to skip validation of JSON string. Defaults to False.
        """
        if data is not None:
            json_data = json.dumps(data)
        elif data_string is not None:
            if not skip_validation:
                try:
                    json.loads(data_string)  # Validate if it is a proper JSON string
                except json.JSONDecodeError:
                    raise ValueError("Invalid JSON string provided")
            json_data = data_string
        else:
            raise ValueError("No valid data provided. Use data or data_string.")

        print(f"[JFB/USAGE] {json_data}", file=sys.stdout)


logger = Logger()

def load_dynamic_functions(logger_instance, package_name):
    """
    Dynamically loads all functions from the specified package and attaches them to the logger instance.

    Args:
        logger_instance (Logger): The logger instance to which functions will be attached.
        package_name (str): The name of the package to load functions from.
    """
    package_path = Path(package_name.replace('.', '/'))
    # Iterate for .py file not starting with _.
    for path in package_path.rglob('[!_]*.py'):
        logger.debug(f"(fb_logging) Loading functions from {path}...")
        module_name = f"{package_name}.{path.stem}"
        module = import_module(module_name)
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith('_'):
                logger.debug(f"(fb_logging) Attaching {name} function on {path} to logger instance")
                setattr(logger_instance, name, obj.__get__(logger_instance))

load_dynamic_functions(logger, 'fb_logging.usage') # import all ./usage/*.py functions to logger instance