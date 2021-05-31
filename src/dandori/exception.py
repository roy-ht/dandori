class DandoriError(Exception):
    """Root Exception class"""


class Cancel(DandoriError):
    """Cancel"""


class Failure(DandoriError):
    """Failure"""
