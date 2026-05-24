# tests/test_config.py
import pytest
from config import load_config


def test_load_config_creates_default_file(tmp_path):
    config_file = tmp_path / "config.toml"
    cfg = load_config(str(config_file))
    assert config_file.exists()
    assert cfg.audio.mode == "microphone"
    assert cfg.transcription.model == "base"
    assert cfg.display.lines == 3
    assert cfg.display.port == 8765
    assert cfg.translation.enabled is False


def test_load_config_reads_existing_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[audio]\nmode = "loopback"\n\n[transcription]\nmodel = "tiny"\nlanguage = "ja"\ndevice = "cpu"\n\n[display]\nlines = 2\nport = 9000\n\n[translation]\nenabled = false\n',
        encoding="utf-8",
    )
    cfg = load_config(str(config_file))
    assert cfg.audio.mode == "loopback"
    assert cfg.transcription.model == "tiny"
    assert cfg.transcription.language == "ja"
    assert cfg.display.lines == 2
    assert cfg.display.port == 9000


def test_load_config_partial_file_uses_defaults(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[audio]\nmode = "both"\n', encoding="utf-8")
    cfg = load_config(str(config_file))
    assert cfg.audio.mode == "both"
    assert cfg.transcription.model == "base"  # default
