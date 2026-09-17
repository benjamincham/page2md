"""Pipeline errors."""


class Page2mdError(Exception):
    """Base class for page2md failures."""


class CaptureError(Page2mdError):
    """Browser capture failed (missing binary, non-zero exit, bad PDF, ...)."""


class ParseError(Page2mdError):
    """PDF parsing failed."""
