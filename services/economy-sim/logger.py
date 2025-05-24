"""
logger.py

Configures Python's standard logging to:
 - Write all logs (DEBUG+) to a file.
 - Print only INFO+ to console.
"""

import logging

def setup_logging(logfile="detailed.log"):
    """
    Set up a root logger that:
     - Writes all logs (DEBUG and above) to `logfile`.
     - Prints only INFO and above to console.
    """
    logger = logging.getLogger()       # root logger
    logger.setLevel(logging.DEBUG)     # capture everything in the file

    # Clear existing handlers (avoid duplication if re-run)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # 1) File handler for detailed logs
    fh = logging.FileHandler(logfile, mode="w")
    fh.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(file_formatter)
    logger.addHandler(fh)

    # 2) Console handler for summaries
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
    ch.setFormatter(console_formatter)
    logger.addHandler(ch)

    return logger
