import logging
import sys
import time
import typing as T

SILENT = logging.CRITICAL + 1
CRITICAL = logging.CRITICAL
ERROR = logging.ERROR
WARNING = logging.WARNING
INFO = logging.INFO
VERBOSE1 = logging.INFO - 1
VERBOSE2 = logging.INFO - 2
VERBOSE3 = logging.INFO - 3
DEBUG = logging.DEBUG
NOTSET = logging.NOTSET

_LEVELS = {
    SILENT: ("SILENT", "S"),
    CRITICAL: ("CRITICAL", "C"),
    ERROR: ("ERROR", "E"),
    WARNING: ("WARNING", "W"),
    INFO: ("INFO", "I"),
    VERBOSE1: ("VERBOSE1", "V"),
    VERBOSE2: ("VERBOSE2", "V2"),
    VERBOSE3: ("VERBOSE3", "V3"),
    DEBUG: ("DEBUG", "D"),
    NOTSET: ("NOTSET", "N"),
}

DEFAULT_FORMAT = "%(prefix)s%(message)s"


class ModuleLogFormatter(logging.Formatter):
    """Custom Logger"""

    converter = time.gmtime  # asctime as a UTC time

    def __init__(self, *args, **kwargs):
        """logging formatter"""
        super().__init__(*args, **kwargs)
        self.fmt_str = kwargs.get("fmt")

    def format(self, record):
        """custom format"""
        levelname = _LEVELS.get(record.levelno)
        if levelname:
            record.prefix = levelname[0].capitalize() + ": " if record.levelno > INFO else ""
            record.levelname = levelname[0]
            record.shortlevelname = levelname[1]
        else:
            record.shortlevelname = ""

        s = super().format(record)
        return s


class Logger:
    """Simple Logger wrapper"""

    def __init__(self, name):
        """Simple Logger wrapper"""
        self._logger = logging.getLogger(name)

    def __getattr__(self, name):
        """Redirect to logging.Logger"""
        return getattr(self._logger, name)

    def verbose1(self, msg, *args, **kwargs):
        """additional log level"""
        if self._logger.isEnabledFor(VERBOSE1):
            self._logger._log(VERBOSE1, msg, args, **kwargs)  # pylint: disable=protected-access

    def verbose2(self, msg, *args, **kwargs):
        """additional log level"""
        if self._logger.isEnabledFor(VERBOSE2):
            self._logger._log(VERBOSE2, msg, args, **kwargs)  # pylint: disable=protected-access

    def verbose3(self, msg, *args, **kwargs):
        """additional log level"""
        if self._logger.isEnabledFor(VERBOSE3):
            self._logger._log(VERBOSE3, msg, args, **kwargs)  # pylint: disable=protected-access


def get_logger(name: T.Optional[str] = None):
    """Return logger"""
    _init_root_logger()
    if name is None:
        name = "dandori"
    return Logger(name)


def get_level() -> int:
    """get current log level"""
    return get_logger().level


def set_level(level: T.Union[str, int]):
    """set log level"""
    lvl = level
    if isinstance(lvl, str):
        lvl = _level_name_to_num(lvl)
    if not isinstance(lvl, int):
        raise ValueError(f"Unknown level: {level}")
    get_logger().setLevel(lvl)
    if lvl <= DEBUG:
        set_format("[%(pathname)s(%(lineno)s):%(funcName)s] " + DEFAULT_FORMAT)


def set_format(fmt):
    """Change logging format"""
    logger = get_logger()
    logger.handlers[0].setFormatter(ModuleLogFormatter(fmt=fmt))


def _level_name_to_num(levelname: str):
    """Find integer level by its name"""
    n = levelname.upper()
    for levelno, (name, short_name) in _LEVELS.items():
        if n in (name, short_name):
            return levelno
    return None


def _init_root_logger():
    if hasattr(_init_root_logger, "__initialized"):
        return
    # initialize only once
    logger = logging.getLogger("dandori")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ModuleLogFormatter(fmt=DEFAULT_FORMAT))
    handler.setLevel(NOTSET)
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(INFO)
    setattr(_init_root_logger, "__initialized", True)
