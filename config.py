import sys
from dataclasses import dataclass, field
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


def load_config(path: str = "config.toml") -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
        print(f"Created default config at {config_path}")

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    return AppConfig(
        audio=AudioConfig(**data.get("audio", {})),
        transcription=TranscriptionConfig(**data.get("transcription", {})),
        display=DisplayConfig(**data.get("display", {})),
        translation=TranslationConfig(**data.get("translation", {})),
    )
