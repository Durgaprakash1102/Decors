import logging

logger = logging.getLogger("licensing")

from .logger import logger

logger.info("License Activated")

logger.warning("License Expired")

logger.error("Invalid Signature")