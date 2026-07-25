import warnings

import app_gradio


def test_css_is_attached_to_blocks_and_not_passed_to_launch(monkeypatch):
    captured = {}

    def fake_launch(**kwargs):
        captured.update(kwargs)
        return "launched"

    monkeypatch.setattr(app_gradio.demo, "launch", fake_launch)
    assert app_gradio.CSS in app_gradio.demo.css
    assert app_gradio.launch_app() == "launched"
    assert captured["inbrowser"] is True
    assert captured["server_port"] == 7864
    assert "css" not in captured


def test_gradio_css_compatibility_warning_is_narrowly_suppressed():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        block = app_gradio._styled_blocks()
    assert app_gradio.CSS in block.css
    assert not any("css' parameter" in str(item.message) for item in caught)


def test_examples_internal_deprecation_warning_is_suppressed():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with app_gradio._styled_blocks():
            textbox = app_gradio.gr.Textbox()
            app_gradio._examples(textbox)
    assert not any("show_api" in str(item.message) for item in caught)
