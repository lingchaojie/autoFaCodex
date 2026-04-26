from pathlib import Path


def test_runner_prompt_forbids_full_page_screenshot():
    text = Path("agent_assets/runner/runner.system.md").read_text(encoding="utf-8")
    assert "full-page screenshot" in text
    assert "Validator report" in text


def test_validator_prompt_requires_every_page():
    text = Path("agent_assets/validator/validator.system.md").read_text(encoding="utf-8")
    assert "every page" in text
    assert "editable" in text
