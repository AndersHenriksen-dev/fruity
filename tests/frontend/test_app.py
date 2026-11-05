"""The demo page starts."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from fruity.lib.shared.settings import CONFIG_DIR


def test_the_page_starts_without_an_error() -> None:
    page = AppTest.from_file(str(CONFIG_DIR.parent / "lib" / "frontend" / "app.py")).run(timeout=30)
    assert not page.exception
    assert page.title[0].value == "What food is this?"
