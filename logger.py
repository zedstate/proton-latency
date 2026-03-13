# logger.py - full updated file (colors kept, purple avoided via level styles)

import structlog
import logging
from logging.handlers import RotatingFileHandler
import sys

def setup_logging():
    # Custom level styles to prevent purple/magenta tones
    level_styles = structlog.dev.LevelStyles(
        debug=dict(color='cyan'),           # blue/cyan
        info=dict(color='green'),           # green for normal info & polls
        warning=dict(color='yellow'),       # yellow/orange
        error=dict(color='red'),            # red
        critical=dict(color='red', bright=True),  # bright red instead of magenta/purple
    )

    # Configure structlog processors
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Pretty console renderer with custom level colors
    console_renderer = structlog.dev.ConsoleRenderer(
        colors=True,
        level_styles=level_styles,          # applies the overrides
        sort_keys=False,
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=console_renderer,
        foreign_pre_chain=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        ]
    ))

    # JSON rolling file handler (10 MB, 5 backups)
    file_handler = RotatingFileHandler(
        "/data/vpn-monitor.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    # Attach handlers to root logger
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    return structlog.get_logger()
