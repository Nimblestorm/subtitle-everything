# tests/test_config.py
import pytest
from config import load_config


def test_load_config_creates_default_file(tmp_path):
    config_file = tmp_path / "config.toml"
    cfg = load_config(str(config_file))
    assert config_file.exists()
    assert cfg.audio.mode == "microphone"
    assert cfg.transcription.mic_model == "base"
    assert cfg.transcription.loopback_model == "base"
    assert cfg.display.lines == 3
    assert cfg.display.port == 8765
    assert cfg.translation.enabled is False


def test_load_config_reads_existing_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[audio]\nmode = "loopback"\n\n[transcription]\nmic_model = "tiny"\nloopback_model = "base"\nlanguage = "ja"\ndevice = "cpu"\n\n[display]\nlines = 2\nport = 9000\n\n[translation]\nenabled = false\n',
        encoding="utf-8",
    )
    cfg = load_config(str(config_file))
    assert cfg.audio.mode == "loopback"
    assert cfg.transcription.mic_model == "tiny"
    assert cfg.transcription.loopback_model == "base"
    assert cfg.transcription.language == "ja"
    assert cfg.display.lines == 2
    assert cfg.display.port == 9000


def test_load_config_partial_file_uses_defaults(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[audio]\nmode = "both"\n', encoding="utf-8")
    cfg = load_config(str(config_file))
    assert cfg.audio.mode == "both"
    assert cfg.transcription.mic_model == "base"  # default
    assert cfg.transcription.loopback_model == "base"  # default


def test_load_config_ignores_unknown_keys(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[audio]\nmode = "microphone"\nunknown_key = "value"\n',
        encoding="utf-8",
    )
    cfg = load_config(str(config_file))
    assert cfg.audio.mode == "microphone"


def test_load_config_raises_on_invalid_port_type(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[display]\nport = "not_an_int"\nlines = 3\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="port must be an integer"):
        load_config(str(config_file))


def test_display_config_new_defaults(tmp_path):
    cfg = load_config(str(tmp_path / "config.toml"))
    assert cfg.display.font_family == "Arial"
    assert cfg.display.font_size == 36
    assert cfg.display.font_color == "#ffffff"
    assert cfg.display.bg_color == "#000000"
    assert cfg.display.bg_opacity == 0.75
    assert cfg.display.max_chars_per_line == 80
    assert cfg.display.fade_duration == 0.0


def test_translation_config_new_defaults(tmp_path):
    cfg = load_config(str(tmp_path / "config.toml"))
    assert cfg.translation.url == "http://localhost:5000"
    assert cfg.translation.source_lang == "en"
    assert cfg.translation.target_lang == "es"
    assert cfg.translation.dual_language is False


def test_load_config_raises_on_invalid_font_size(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text("[display]\nfont_size = 4\n", encoding="utf-8")
    with pytest.raises(ValueError, match="font_size"):
        load_config(str(f))


def test_load_config_raises_on_invalid_bg_opacity(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text("[display]\nbg_opacity = 1.5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bg_opacity"):
        load_config(str(f))


def test_load_config_raises_on_invalid_font_color(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[display]\nfont_color = "red"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="font_color"):
        load_config(str(f))


def test_load_config_raises_on_invalid_max_chars(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text("[display]\nmax_chars_per_line = 5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="max_chars_per_line"):
        load_config(str(f))


def test_write_config_roundtrip(tmp_path):
    from config import write_config, AppConfig, DisplayConfig, TranslationConfig
    cfg = AppConfig()
    cfg.display.font_size = 48
    cfg.display.font_color = "#ffff00"
    cfg.translation.target_lang = "fr"
    p = str(tmp_path / "out.toml")
    write_config(cfg, p)
    loaded = load_config(p)
    assert loaded.display.font_size == 48
    assert loaded.display.font_color == "#ffff00"
    assert loaded.translation.target_lang == "fr"


def test_transcription_config_new_defaults(tmp_path):
    cfg = load_config(str(tmp_path / "config.toml"))
    assert cfg.transcription.mic_model == "base"
    assert cfg.transcription.loopback_model == "base"
    assert not hasattr(cfg.transcription, "model")


def test_display_source_defaults(tmp_path):
    cfg = load_config(str(tmp_path / "config.toml"))
    assert cfg.display.mic_color == "#ffffff"
    assert cfg.display.mic_position == "bottom"
    assert cfg.display.loopback_color == "#00d4ff"
    assert cfg.display.loopback_position == "top"


def test_load_config_raises_on_invalid_mic_model(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[transcription]\nmic_model = "large"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="mic_model"):
        load_config(str(f))


def test_load_config_raises_on_invalid_loopback_model(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[transcription]\nloopback_model = "medium"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="loopback_model"):
        load_config(str(f))


def test_load_config_raises_on_invalid_mic_position(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[display]\nmic_position = "center"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="mic_position"):
        load_config(str(f))


def test_load_config_raises_on_invalid_mic_color(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[display]\nmic_color = "blue"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="mic_color"):
        load_config(str(f))


def test_load_config_raises_on_invalid_loopback_color(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[display]\nloopback_color = "blue"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="loopback_color"):
        load_config(str(f))


def test_load_config_raises_on_invalid_loopback_position(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[display]\nloopback_position = "center"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="loopback_position"):
        load_config(str(f))


def test_load_config_raises_on_invalid_audio_mode(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[audio]\nmode = "both_ears"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="audio.*mode"):
        load_config(str(f))


def test_load_config_raises_on_invalid_transcription_device(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[transcription]\ndevice = "tpu"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="device"):
        load_config(str(f))


def test_load_config_raises_on_empty_language(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[transcription]\nlanguage = ""\n', encoding="utf-8")
    with pytest.raises(ValueError, match="language"):
        load_config(str(f))


def test_load_config_raises_on_invalid_translation_url(tmp_path):
    f = tmp_path / "config.toml"
    f.write_text('[translation]\nenabled = false\nurl = "file:///etc/passwd"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="url"):
        load_config(str(f))


def test_load_config_raises_on_nan_fade_duration(tmp_path):
    from config import AppConfig, validate_config
    import math
    cfg = AppConfig()
    cfg.display.fade_duration = float('nan')
    with pytest.raises(ValueError, match="fade_duration"):
        validate_config(cfg)


def test_write_config_roundtrip_source_fields(tmp_path):
    from config import write_config, AppConfig
    cfg = AppConfig()
    cfg.transcription.mic_model = "tiny"
    cfg.transcription.loopback_model = "base"
    cfg.display.mic_color = "#ff0000"
    cfg.display.mic_position = "top"
    cfg.display.loopback_color = "#00ff00"
    cfg.display.loopback_position = "bottom"
    p = str(tmp_path / "out.toml")
    write_config(cfg, p)
    loaded = load_config(p)
    assert loaded.transcription.mic_model == "tiny"
    assert loaded.transcription.loopback_model == "base"
    assert loaded.display.mic_color == "#ff0000"
    assert loaded.display.mic_position == "top"
    assert loaded.display.loopback_color == "#00ff00"
    assert loaded.display.loopback_position == "bottom"
