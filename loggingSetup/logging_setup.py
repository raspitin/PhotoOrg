import logging
from pathlib import Path

class LoggingSetup:
    @staticmethod
    def setup_logging(log_path):
        log_file = Path(log_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file),
                #logging.StreamHandler()
            ]
        )