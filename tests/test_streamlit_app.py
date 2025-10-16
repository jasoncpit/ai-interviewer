from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_loads_without_exceptions():
    app_path = Path("src/streamlit_app.py")
    app = AppTest.from_file(str(app_path)).run()

    assert not app.exception
    assert app.title[0].value == "Prolific AI Interviewer"
    assert any(button.label == "Start Interview" for button in app.button)
