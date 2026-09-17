"""Token counting: tiktoken cl100k_base, with a zero-dependency fallback.

tiktoken needs to download its BPE data on first use; when it (or the
network) is unavailable we fall back to a ~4-chars-per-token heuristic so the
pipeline always works fully offline.
"""

from __future__ import annotations

_encoder: object | None = None
_encoder_tried = False
_name = "fallback-4char"


def _get_encoder() -> object | None:
    global _encoder, _encoder_tried, _name
    if _encoder_tried:
        return _encoder
    _encoder_tried = True
    try:
        import tiktoken

        _encoder = tiktoken.get_encoding("cl100k_base")
        _name = "cl100k_base"
    except Exception:
        _encoder = None
        _name = "fallback-4char"
    return _encoder


def count_tokens(text: str) -> int:
    """Approximate token count; always >= 1 for non-empty text."""
    if not text:
        return 0
    enc = _get_encoder()
    if enc is not None:
        return len(enc.encode(text))  # type: ignore[attr-defined]
    return max(1, len(text) // 4)


def tokenizer_name() -> str:
    """Name of the estimator currently in use."""
    _get_encoder()
    return _name
