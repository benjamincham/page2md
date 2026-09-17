import sys

import pytest

import page2md.tokens as tokens


@pytest.fixture(autouse=True)
def _reset_tokens(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(tokens, "_encoder", None)
    monkeypatch.setattr(tokens, "_encoder_tried", False)
    monkeypatch.setattr(tokens, "_name", "fallback-4char")


def test_tiktoken_path() -> None:
    pytest.importorskip("tiktoken")
    n = tokens.count_tokens("hello world, this is a test of the tokenizer")
    assert n > 3
    assert tokens.tokenizer_name() == "cl100k_base"


def test_fallback_when_import_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate tiktoken being uninstalled / its data unfetchable offline.
    monkeypatch.setitem(sys.modules, "tiktoken", None)
    text = "x" * 400
    assert tokens.count_tokens(text) == 100  # len // 4
    assert tokens.count_tokens("hi") == 1  # floor of 1
    assert tokens.tokenizer_name() == "fallback-4char"


def test_empty_text() -> None:
    assert tokens.count_tokens("") == 0
