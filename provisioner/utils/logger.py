import logging
from logging.handlers import TimedRotatingFileHandler
import os
from datetime import datetime
from provisioner.config.settings import DefaultSettings

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

# File handler with date-based rotation
log_dir = DefaultSettings.LOG_PATH
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f"provisioner_{datetime.now().strftime('%Y-%m-%d')}.log")
file_handler = TimedRotatingFileHandler(log_file, when='midnight', interval=1, backupCount=7, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)