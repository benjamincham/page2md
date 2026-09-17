"""page2md: URL -> ego-browser PDF -> local LLM-ready Markdown/chunks."""

from .errors import CaptureError, Page2mdError, ParseError
from .parse import parse_pdf
from .pipeline import DistillResult, distill_pdf, distill_url

__version__ = "0.1.0"

__all__ = [
    "CaptureError",
    "DistillResult",
    "ParseError",
    "Page2mdError",
    "__version__",
    "distill_pdf",
    "distill_url",
    "parse_pdf",
]
