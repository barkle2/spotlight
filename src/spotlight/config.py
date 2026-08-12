from __future__ import annotations

import configparser
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SETTINGS = """; Spotlight 사용자 설정
; 포인터 크기: 1~15 단계
; 그 외 크기: 논리 픽셀
; 색상: #RRGGBB
; 투명도: 0~100
; 시간: 밀리초

[pointer]
size=1

[spotlight]
enabled=true
diameter=120
color=#FFFF00
opacity=30
style=fill
border_width=3

[click]
enabled=true
left_color=#FF3B30
right_color=#007AFF
duration_ms=180

[wheel]
enabled=true
color=#34C759
duration_ms=250
line_width=4
"""


@dataclass(frozen=True)
class PointerSettings:
    size: int = 1


@dataclass(frozen=True)
class SpotlightSettings:
    enabled: bool = True
    diameter: int = 120
    color: str = "#FFFF00"
    opacity: int = 30
    style: str = "fill"
    border_width: int = 3


@dataclass(frozen=True)
class ClickSettings:
    enabled: bool = True
    left_color: str = "#FF3B30"
    right_color: str = "#007AFF"
    duration_ms: int = 180


@dataclass(frozen=True)
class WheelSettings:
    enabled: bool = True
    color: str = "#34C759"
    duration_ms: int = 250
    line_width: int = 4


@dataclass(frozen=True)
class Settings:
    pointer: PointerSettings = PointerSettings()
    spotlight: SpotlightSettings = SpotlightSettings()
    click: ClickSettings = ClickSettings()
    wheel: WheelSettings = WheelSettings()


def settings_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA 환경변수를 찾을 수 없습니다.")
    return Path(local_app_data) / "Spotlight"


def settings_path() -> Path:
    return settings_directory() / "settings.ini"


def recovery_path() -> Path:
    return settings_directory() / "cursor_recovery.json"


def ensure_default_settings(path: Path | None = None) -> Path:
    destination = path or settings_path()
    if destination.exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix="settings-", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(DEFAULT_SETTINGS)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return destination


def _integer(
    parser: configparser.ConfigParser,
    section: str,
    option: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        value = parser.getint(section, option)
    except (configparser.Error, ValueError):
        return default
    return value if minimum <= value <= maximum else default


def _boolean(
    parser: configparser.ConfigParser, section: str, option: str, default: bool
) -> bool:
    try:
        return parser.getboolean(section, option)
    except (configparser.Error, ValueError):
        return default


def _color(
    parser: configparser.ConfigParser, section: str, option: str, default: str
) -> str:
    try:
        value = parser.get(section, option).strip().upper()
    except configparser.Error:
        return default
    if len(value) == 7 and value.startswith("#"):
        try:
            int(value[1:], 16)
            return value
        except ValueError:
            pass
    return default


def load_settings(path: Path | None = None) -> Settings:
    source = ensure_default_settings(path)
    parser = configparser.ConfigParser(interpolation=None)
    try:
        with source.open("r", encoding="utf-8") as handle:
            parser.read_file(handle)
    except (OSError, UnicodeError, configparser.Error):
        parser = configparser.ConfigParser(interpolation=None)

    style = parser.get("spotlight", "style", fallback="fill").strip().lower()
    if style not in {"fill", "outline"}:
        style = "fill"

    return Settings(
        pointer=PointerSettings(
            size=_integer(parser, "pointer", "size", 1, 1, 15)
        ),
        spotlight=SpotlightSettings(
            enabled=_boolean(parser, "spotlight", "enabled", True),
            diameter=_integer(parser, "spotlight", "diameter", 120, 20, 1000),
            color=_color(parser, "spotlight", "color", "#FFFF00"),
            opacity=_integer(parser, "spotlight", "opacity", 30, 0, 100),
            style=style,
            border_width=_integer(parser, "spotlight", "border_width", 3, 1, 50),
        ),
        click=ClickSettings(
            enabled=_boolean(parser, "click", "enabled", True),
            left_color=_color(parser, "click", "left_color", "#FF3B30"),
            right_color=_color(parser, "click", "right_color", "#007AFF"),
            duration_ms=_integer(parser, "click", "duration_ms", 180, 50, 2000),
        ),
        wheel=WheelSettings(
            enabled=_boolean(parser, "wheel", "enabled", True),
            color=_color(parser, "wheel", "color", "#34C759"),
            duration_ms=_integer(parser, "wheel", "duration_ms", 250, 50, 2000),
            line_width=_integer(parser, "wheel", "line_width", 4, 1, 50),
        ),
    )


def serialize_settings(settings: Settings) -> str:
    return f"""; Spotlight 사용자 설정
; 포인터 크기: 1~15 단계
; 그 외 크기: 논리 픽셀
; 색상: #RRGGBB
; 투명도: 0~100
; 시간: 밀리초

[pointer]
size={settings.pointer.size}

[spotlight]
enabled={str(settings.spotlight.enabled).lower()}
diameter={settings.spotlight.diameter}
color={settings.spotlight.color}
opacity={settings.spotlight.opacity}
style={settings.spotlight.style}
border_width={settings.spotlight.border_width}

[click]
enabled={str(settings.click.enabled).lower()}
left_color={settings.click.left_color}
right_color={settings.click.right_color}
duration_ms={settings.click.duration_ms}

[wheel]
enabled={str(settings.wheel.enabled).lower()}
color={settings.wheel.color}
duration_ms={settings.wheel.duration_ms}
line_width={settings.wheel.line_width}
"""


def save_settings(settings: Settings, path: Path | None = None) -> Path:
    destination = path or settings_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix="settings-", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialize_settings(settings))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return destination
