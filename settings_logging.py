import datetime
import logging
import os.path
from logging.handlers import RotatingFileHandler

from colorama import Fore, Style

from utils import tuple_get


class ColorFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.format_string = tuple_get(args, 0) or kwargs.get("fmt")

        self.formats = {
            logging.DEBUG: Fore.LIGHTBLACK_EX + self.format_string + Style.RESET_ALL,
            logging.INFO: Fore.WHITE + self.format_string + Style.RESET_ALL,
            logging.WARNING: Fore.YELLOW + self.format_string + Style.RESET_ALL,
            logging.ERROR: Fore.RED + self.format_string + Style.RESET_ALL,
            logging.CRITICAL: Fore.LIGHTRED_EX + self.format_string + Style.RESET_ALL,
        }

    def format(self, record):
        log_fmt = self.formats.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def setup_logger(level: int):
    logger = logging.getLogger()
    logger.setLevel(level)

    # One logfile per run
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
    log_dir = "logs"
    log_file_path = os.path.join(log_dir, f"agent_{timestamp}.log")
    os.makedirs(log_dir, exist_ok=True)

    # Create handlers for both file and console outputs
    file_handler = RotatingFileHandler(
        log_file_path, maxBytes=1024 * 1024 * 5, backupCount=5
    )
    console_handler = logging.StreamHandler()

    # Set the logging level for both handlers
    file_handler.setLevel(level)
    console_handler.setLevel(level)

    # Create a formatter for the log messages
    format = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )
    formatter = logging.Formatter(format)
    color_formatter = ColorFormatter(format)

    # Attach the formatter to the handlers
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(color_formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


if __name__ == "__main__":
    setup_logger(logging.DEBUG)
    logger = logging.getLogger()
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")