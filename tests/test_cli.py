from __future__ import annotations

import os
from pathlib import Path

import pytest

from stateguard.cli import _load_dotenv


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)


def test_load_dotenv_sets_undeclared_variables(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "# a comment\n"
        "\n"
        'DEEPSEEK_API_KEY="sk-example"\n'
        "DEEPSEEK_MODEL=deepseek-chat\n"
        "not_a_valid_line_without_equals\n",
        encoding="utf-8",
    )

    _load_dotenv(dotenv)

    assert os.environ["DEEPSEEK_API_KEY"] == "sk-example"
    assert os.environ["DEEPSEEK_MODEL"] == "deepseek-chat"


def test_load_dotenv_never_overrides_a_real_environment_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-real-shell")
    dotenv = tmp_path / ".env"
    dotenv.write_text("DEEPSEEK_API_KEY=from-dotenv-file\n", encoding="utf-8")

    _load_dotenv(dotenv)

    assert os.environ["DEEPSEEK_API_KEY"] == "from-real-shell"


def test_load_dotenv_is_a_silent_noop_when_the_file_does_not_exist(tmp_path: Path) -> None:
    _load_dotenv(tmp_path / "does-not-exist.env")
    assert "DEEPSEEK_API_KEY" not in os.environ
