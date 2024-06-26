import argparse
import logging

import settings
import settings_logging
from chat_session import chat_session

logger = logging.getLogger("main")


def main():
    try:
        settings_logging.setup_logger(settings.LOG_LEVEL)

        parser = argparse.ArgumentParser(description="AI Helper Command Line Interface")
        parser.add_argument(
            "-w", "--work-dir", type=str, help="Working directory for the assistant"
        )

        args = parser.parse_args()

        if args.work_dir:
            settings.AGENT_WORK_DIR = args.work_dir
            logger.info(f"Using work dir: {args.work_dir}")
        chat_session()
    except KeyboardInterrupt:
        logger.info("Ctrl-C pressed, exiting...")


if __name__ == "__main__":
    main()
