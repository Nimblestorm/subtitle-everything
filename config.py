import re
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
mic_model = "base"
loopback_model = "base"
language = "en"
device = "cpu"

[display]
lines = 3
port = 8765
font_family = "Arial"
font_size = 36
font_color = "#ffffff"
bg_color = "#000000"
bg_opacity = 0.75
max_chars_per_line = 80
fade_duration = 0.0
mic_color = "#ffffff"
mic_position = "bottom"
loopback_color = "#00d4ff"
loopback_position = "top"

[translation]
enabled = false
url = "http://localhost:5000"
source_lang = "en"
target_lang = "es"
dual_language = false
"""

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_FONT_FAMILY_RE = re.compile(r'^[A-Za-z0-9 ,\-]+$')


def _toml_str(value: str) -> str:
    """Escape string values for safe TOML output."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\x00", "")


@dataclass
class AudioConfig:
    mode: str = "microphone"
    mic_device: str = "default"
    loopback_device: str = "default"


@dataclass
class TranscriptionConfig:
    mic_model: str = "base"
    loopback_model: str = "base"
    language: str = "en"
    device: str = "cpu"


@dataclass
class DisplayConfig:
    lines: int = 3
    port: int = 8765
    font_family: str = "Arial"
    font_size: int = 36
    font_color: str = "#ffffff"
    bg_color: str = "#000000"
    bg_opacity: float = 0.75
    max_chars_per_line: int = 80
    fade_duration: float = 0.0
    mic_color: str = "#ffffff"
    mic_position: str = "bottom"
    loopback_color: str = "#00d4ff"
    loopback_position: str = "top"


@dataclass
class TranslationConfig:
    enabled: bool = False
    url: str = "http://localhost:5000"
    source_lang: str = "en"
    target_lang: str = "es"
    dual_language: bool = False


@dataclass
class AppConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)


def build_config_section(cls, data: dict):
    known = {f.name for f in dc_fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known})


def validate_config(cfg: "AppConfig") -> None:
    if not isinstance(cfg.display.port, int):
        raise ValueError(f"[display] port must be an integer, got {cfg.display.port!r}")
    if not isinstance(cfg.display.lines, int):
        raise ValueError(f"[display] lines must be an integer, got {cfg.display.lines!r}")
    if not isinstance(cfg.translation.enabled, bool):
        raise ValueError(f"[translation] enabled must be a boolean, got {cfg.translation.enabled!r}")
    if cfg.display.lines < 1:
        raise ValueError(f"[display] lines must be >= 1, got {cfg.display.lines!r}")
    if cfg.display.font_size < 8:
        raise ValueError(f"[display] font_size must be >= 8, got {cfg.display.font_size!r}")
    if not (0.0 <= cfg.display.bg_opacity <= 1.0):
        raise ValueError(f"[display] bg_opacity must be 0.0–1.0, got {cfg.display.bg_opacity!r}")
    if cfg.display.max_chars_per_line < 20:
        raise ValueError(f"[display] max_chars_per_line must be >= 20, got {cfg.display.max_chars_per_line!r}")
    if cfg.display.fade_duration < 0.0:
        raise ValueError(f"[display] fade_duration must be >= 0.0, got {cfg.display.fade_duration!r}")
    if not _HEX_COLOR_RE.match(cfg.display.font_color):
        raise ValueError(f"[display] font_color must be #rrggbb hex, got {cfg.display.font_color!r}")
    if not _HEX_COLOR_RE.match(cfg.display.bg_color):
        raise ValueError(f"[display] bg_color must be #rrggbb hex, got {cfg.display.bg_color!r}")
    if cfg.transcription.mic_model not in ("tiny", "base"):
        raise ValueError(f"[transcription] mic_model must be 'tiny' or 'base', got {cfg.transcription.mic_model!r}")
    if cfg.transcription.loopback_model not in ("tiny", "base"):
        raise ValueError(f"[transcription] loopback_model must be 'tiny' or 'base', got {cfg.transcription.loopback_model!r}")
    if not _HEX_COLOR_RE.match(cfg.display.mic_color):
        raise ValueError(f"[display] mic_color must be #rrggbb hex, got {cfg.display.mic_color!r}")
    if not _HEX_COLOR_RE.match(cfg.display.loopback_color):
        raise ValueError(f"[display] loopback_color must be #rrggbb hex, got {cfg.display.loopback_color!r}")
    if cfg.display.mic_position not in ("top", "bottom"):
        raise ValueError(f"[display] mic_position must be 'top' or 'bottom', got {cfg.display.mic_position!r}")
    if cfg.display.loopback_position not in ("top", "bottom"):
        raise ValueError(f"[display] loopback_position must be 'top' or 'bottom', got {cfg.display.loopback_position!r}")
    if not _FONT_FAMILY_RE.match(cfg.display.font_family):
        raise ValueError(f"[display] font_family contains invalid characters: {cfg.display.font_family!r}")
    # Validate audio.mode
    if cfg.audio.mode not in ("microphone", "loopback", "both"):
        raise ValueError(f"[audio] mode must be 'microphone', 'loopback', or 'both', got {cfg.audio.mode!r}")
    # Validate transcription.device
    if cfg.transcription.device not in ("cpu", "cuda"):
        raise ValueError(f"[transcription] device must be 'cpu' or 'cuda', got {cfg.transcription.device!r}")
    # Validate transcription.language
    if not cfg.transcription.language or not isinstance(cfg.transcription.language, str):
        raise ValueError("[transcription] language must be a non-empty string")
    # Validate translation.url — must be http:// or https:// only
    if cfg.translation.enabled:
        if not re.match(r'^https?://', cfg.translation.url):
            raise ValueError(f"[translation] url must start with http:// or https://, got {cfg.translation.url!r}")


def write_config(config: "AppConfig", path: str = "config.toml") -> None:
    a, tr, d, t = config.audio, config.transcription, config.display, config.translation
    toml = (
        f'[audio]\n'
        f'mode = "{_toml_str(a.mode)}"\n'
        f'mic_device = "{_toml_str(a.mic_device)}"\n'
        f'loopback_device = "{_toml_str(a.loopback_device)}"\n'
        f'\n'
        f'[transcription]\n'
        f'mic_model = "{_toml_str(tr.mic_model)}"\n'
        f'loopback_model = "{_toml_str(tr.loopback_model)}"\n'
        f'language = "{_toml_str(tr.language)}"\n'
        f'device = "{_toml_str(tr.device)}"\n'
        f'\n'
        f'[display]\n'
        f'lines = {d.lines}\n'
        f'port = {d.port}\n'
        f'font_family = "{_toml_str(d.font_family)}"\n'
        f'font_size = {d.font_size}\n'
        f'font_color = "{_toml_str(d.font_color)}"\n'
        f'bg_color = "{_toml_str(d.bg_color)}"\n'
        f'bg_opacity = {d.bg_opacity}\n'
        f'max_chars_per_line = {d.max_chars_per_line}\n'
        f'fade_duration = {d.fade_duration}\n'
        f'mic_color = "{_toml_str(d.mic_color)}"\n'
        f'mic_position = "{_toml_str(d.mic_position)}"\n'
        f'loopback_color = "{_toml_str(d.loopback_color)}"\n'
        f'loopback_position = "{_toml_str(d.loopback_position)}"\n'
        f'\n'
        f'[translation]\n'
        f'enabled = {"true" if t.enabled else "false"}\n'
        f'url = "{_toml_str(t.url)}"\n'
        f'source_lang = "{_toml_str(t.source_lang)}"\n'
        f'target_lang = "{_toml_str(t.target_lang)}"\n'
        f'dual_language = {"true" if t.dual_language else "false"}\n'
    )
    Path(path).write_text(toml, encoding="utf-8")


def load_config(path: str = "config.toml") -> "AppConfig":
    config_path = Path(path)
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
        print(f"Created default config at {config_path}")

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    cfg = AppConfig(
        audio=build_config_section(AudioConfig, data.get("audio", {})),
        transcription=build_config_section(TranscriptionConfig, data.get("transcription", {})),
        display=build_config_section(DisplayConfig, data.get("display", {})),
        translation=build_config_section(TranslationConfig, data.get("translation", {})),
    )

    validate_config(cfg)
    return cfg
