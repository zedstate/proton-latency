import structlog
import logging
from logging.handlers import RotatingFileHandler
import sys
import json

def setup_logging():
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        logger_factory=structlog.WriteLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Colored console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(structlog.dev.ConsoleRenderer(colors=True))

    # JSON file - 10MB rolling, keep 5 backups
    file_handler = RotatingFileHandler(
        "/data/vpn-monitor.log", maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    return structlog.get_logger()
