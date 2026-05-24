import sys
from dataclasses import dataclass, field, fields as dc_fields
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

DEFAULT_CONFIG = """\
[audio]
mode = "microphone"
mic_device = "default"
loopback_device = "default"

[transcription]
model = "base"
language = "en"
device = "cpu"

[display]
lines = 3
port = 8765

[translation]
enabled = false
"""


@dataclass
class AudioConfig:
    mode: str = "microphone"
    mic_device: str = "default"
    loopback_device: str = "default"


@dataclass
class TranscriptionConfig:
    model: str = "base"
    language: str = "en"
    device: str = "cpu"


@dataclass
class DisplayConfig:
    lines: int = 3
    port: int = 8765


@dataclass
class TranslationConfig:
    enabled: bool = False


@dataclass
class AppConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)


def _build(cls, data: dict):
    known = {f.name for f in dc_fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known})


def load_config(path: str = "config.toml") -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
        print(f"Created default config at {config_path}")

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    cfg = AppConfig(
        audio=_build(AudioConfig, data.get("audio", {})),
        transcription=_build(TranscriptionConfig, data.get("transcription", {})),
        display=_build(DisplayConfig, data.get("display", {})),
        translation=_build(TranslationConfig, data.get("translation", {})),
    )

    if not isinstance(cfg.display.port, int):
        raise ValueError(f"config.toml: [display] port must be an integer, got {cfg.display.port!r}")
    if not isinstance(cfg.display.lines, int):
        raise ValueError(f"config.toml: [display] lines must be an integer, got {cfg.display.lines!r}")
    if not isinstance(cfg.translation.enabled, bool):
        raise ValueError(f"config.toml: [translation] enabled must be a boolean, got {cfg.translation.enabled!r}")

    return cfg
