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
