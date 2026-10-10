"""강조원·클릭·휠·포인터 설정과 공통 검증·저장을 관리합니다.

화면 입력과 설정 파일에 동일한 타입·범위·색상 검증을 적용합니다.
설정은 변경 불가능한 객체로 관리하여 프리뷰값과 적용값을 구분합니다.
파일 읽기는 원본을 변경하지 않으며, 저장은 임시 파일을 완성한 뒤
기존 파일을 교체하는 방식으로 처리합니다.
"""

import re
import configparser
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


COLOR_PATTERN = re.compile(r"\A#[0-9A-F]{6}\Z")

MIN_DIAMETER = 20
MAX_DIAMETER = 600
MIN_LINE_WIDTH = 1
MAX_LINE_WIDTH = 10
MIN_CLICK_DURATION_MS = 50
MAX_CLICK_DURATION_MS = 2000
MIN_WHEEL_DURATION_MS = 50
MAX_WHEEL_DURATION_MS = 2000
MIN_CURSOR_LEVEL = 1
MAX_CURSOR_LEVEL = 15


def normalize_color(value: str) -> str:
    """정확한 #RRGGBB 형식만 허용하고 대문자로 반환합니다."""
    if not isinstance(value, str):
        raise ValueError("색상은 문자열이어야 합니다.")

    # 소문자는 허용하지만 앞뒤 공백·개행은 제거하지 않습니다.
    # 잘못된 입력을 정상 값으로 바꾸어 허용하는 것을 방지합니다.
    normalized = value.upper()

    if COLOR_PATTERN.fullmatch(normalized) is None:
        raise ValueError("색상은 #RRGGBB 형식이어야 합니다.")

    return normalized


def validate_integer(
    name: str, value: int, minimum: int, maximum: int
) -> None:
    """정수 타입과 허용 범위를 검사합니다."""
    # Python의 bool은 int의 하위 타입이므로 정확한 타입을 비교합니다.
    if type(value) is not int:
        raise ValueError(f"{name}은 정수여야 합니다.")

    if not minimum <= value <= maximum:
        raise ValueError(f"{name}은 {minimum}~{maximum} 범위여야 합니다.")


@dataclass(frozen=True)
class HighlightSettings:
    """네 기능의 검증된 설정을 변경 불가능한 객체로 보관합니다.

    생성 시 타입·범위·색상·표시 방식을 검증합니다.
    값 변경은 새로운 객체를 생성하여 처리하므로,
    프리뷰 중에도 마지막 적용값을 별도로 유지할 수 있습니다.
    """

    enabled: bool = True
    diameter: int = 60
    color: str = "#FFFF00"
    opacity: int = 30
    style: str = "fill"
    line_width: int = 3
    # 클릭 효과는 지속 강조 원과 독립적으로 활성화합니다.
    click_enabled: bool = True
    left_click_color: str = "#00AAFF"
    right_click_color: str = "#FF6600"
    click_duration_ms: int = 180
    click_style: str = "outline"
    click_line_width: int = 3
    # 휠 설정은 클릭 효과·지속 강조 원과 독립적으로 관리합니다.
    wheel_enabled: bool = True    
    wheel_color: str = "#00CC66"
    wheel_duration_ms: int = 250
    wheel_line_width: int = 3
    # 기본값은 비활성화하여 최초 실행 시 시스템 커서를 바꾸지 않습니다.
    cursor_enabled: bool = False
    cursor_level: int = 1    

    def __post_init__(self) -> None:
        """설정 생성 시 공통 검증을 수행합니다."""
        if type(self.enabled) is not bool:
            raise ValueError("활성화 값은 True 또는 False여야 합니다.")

        validate_integer(
            "지름", self.diameter, MIN_DIAMETER, MAX_DIAMETER
        )
        validate_integer("불투명도", self.opacity, 0, 100)
        validate_integer(
            "선 두께", self.line_width, MIN_LINE_WIDTH, MAX_LINE_WIDTH
        )

        if self.style not in ("fill", "outline"):
            raise ValueError("표시 방식은 fill 또는 outline이어야 합니다.")

        # frozen 객체의 초기화 시점에만 정규화된 값을 설정합니다.
        object.__setattr__(self, "color", normalize_color(self.color))

        if type(self.click_enabled) is not bool:
            raise ValueError("클릭 효과 활성화 값은 True 또는 False여야 합니다.")

        validate_integer(
            "클릭 효과 시간",
            self.click_duration_ms,
            MIN_CLICK_DURATION_MS,
            MAX_CLICK_DURATION_MS,
        )

        # 강조 원과 클릭 효과가 같은 색상 검증 규칙을 사용합니다.
        object.__setattr__(
            self, "left_click_color", normalize_color(self.left_click_color)
        )
        object.__setattr__(
            self, "right_click_color", normalize_color(self.right_click_color)
        )

        if self.click_style not in ("fill", "outline"):
            raise ValueError("클릭 표시 방식은 fill 또는 outline이어야 합니다.")

        validate_integer(
            "클릭 선 두께",
            self.click_line_width,
            MIN_LINE_WIDTH,
            MAX_LINE_WIDTH,
        )

        if type(self.wheel_enabled) is not bool:
            raise ValueError("휠 효과 활성화 값은 True 또는 False여야 합니다.")        

        validate_integer(
            "휠 효과 시간",
            self.wheel_duration_ms,
            MIN_WHEEL_DURATION_MS,
            MAX_WHEEL_DURATION_MS,
        )

        validate_integer(
            "휠 선 두께",
            self.wheel_line_width,
            MIN_LINE_WIDTH,
            MAX_LINE_WIDTH,
        )

        object.__setattr__(
            self, "wheel_color", normalize_color(self.wheel_color)
        )

        if type(self.cursor_enabled) is not bool:
            raise ValueError("포인터 확대 활성화 값은 True 또는 False여야 합니다.")

        validate_integer(
            "포인터 크기 단계",
            self.cursor_level,
            MIN_CURSOR_LEVEL,
            MAX_CURSOR_LEVEL,
        )

# 작은 설정 파일만 읽어 과도하게 큰 파일 처리를 방지합니다.
MAX_CONFIG_BYTES = 64 * 1024
logger = logging.getLogger(__name__)


def get_config_path() -> Path:
    """프로젝트 밖의 사용자 전용 설정 파일 경로를 반환합니다."""
    local_directory = os.environ.get("LOCALAPPDATA")

    if local_directory:
        root = Path(local_directory)
    else:
        root = Path.home() / "AppData" / "Local"

    return root / "Spotlight" / "settings.ini"


def load_settings(path: Path) -> tuple[HighlightSettings, str | None]:
    """설정 객체와 읽기 오류 안내 문구를 함께 반환합니다.

    파일이 없으면 기본값과 None을 반환합니다.
    읽기·파싱·검증 오류가 발생하면 전체 기본값과 안내 문구를 반환합니다.
    기존 파일에 없는 설정 항목은 해당 항목의 기본값으로 보완합니다.
    읽기 과정에서는 원본 파일을 수정하거나 삭제하지 않습니다.
    """
    defaults = HighlightSettings()

    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_CONFIG_BYTES + 1)

        if len(data) > MAX_CONFIG_BYTES:
            raise ValueError("설정 파일이 허용 크기를 초과했습니다.")

        text = data.decode("utf-8")

        # ConfigParser는 값 앞뒤 공백을 제거합니다.
        # 잘못된 색상이 정상 값으로 바뀌어 검증을 통과하지 않도록
        # 파싱 전에 원문의 값도 확인합니다. 저장 형식은 key=value입니다.
        for line in text.splitlines():
            if not line.strip() or line.lstrip().startswith(("#", ";")):
                continue

            if "=" in line:
                _, value = line.split("=", 1)
                if value != value.strip():
                    raise ValueError("설정값 앞뒤에 공백이 있습니다.")

        parser = configparser.ConfigParser(
            interpolation=None,
            delimiters=("=",),
        )
        parser.read_string(text)
        section = parser["highlight"]

        # GUI와 같은 모델을 생성하여 범위·색상·표시 방식을 검증합니다.
        settings = HighlightSettings(
            enabled=section.getboolean(
                "enabled", fallback=defaults.enabled
            ),
            diameter=section.getint(
                "diameter", fallback=defaults.diameter
            ),
            color=section.get("color", fallback=defaults.color),
            opacity=section.getint(
                "opacity", fallback=defaults.opacity
            ),
            style=section.get("style", fallback=defaults.style),
            line_width=section.getint(
                "line_width", fallback=defaults.line_width
            ),
            # 이전 설정 파일에 없는 항목은 현재 기본값으로 보완합니다.
            click_enabled=section.getboolean(
                "click_enabled", fallback=defaults.click_enabled
            ),
            left_click_color=section.get(
                "left_click_color", fallback=defaults.left_click_color
            ),
            right_click_color=section.get(
                "right_click_color", fallback=defaults.right_click_color
            ),
            click_duration_ms=section.getint(
                "click_duration_ms", fallback=defaults.click_duration_ms
            ),
            click_style=section.get(
                "click_style", fallback=defaults.click_style
            ),
            click_line_width=section.getint(
                "click_line_width", fallback=defaults.click_line_width
            ),
            wheel_enabled=section.getboolean(
                "wheel_enabled", fallback=defaults.wheel_enabled
            ),            
            wheel_color=section.get(
                "wheel_color", fallback=defaults.wheel_color
            ),
            wheel_duration_ms=section.getint(
                "wheel_duration_ms", fallback=defaults.wheel_duration_ms
            ),
            wheel_line_width=section.getint(
                "wheel_line_width", fallback=defaults.wheel_line_width
            ),
            cursor_enabled=section.getboolean(
                "cursor_enabled", fallback=defaults.cursor_enabled
            ),
            cursor_level=section.getint(
                "cursor_level", fallback=defaults.cursor_level
            ),            
        )
        return settings, None

    except FileNotFoundError:
        return defaults, None

    except (OSError, UnicodeError, configparser.Error, ValueError, KeyError) as error:
        return defaults, (
            "설정 파일을 읽을 수 없어 기본값을 사용합니다.\n"
            f"파일: {path}\n"
            f"원인: {error}"
        )


def save_settings(path: Path, settings: HighlightSettings) -> None:
    """검증된 설정을 UTF-8 파일로 저장합니다.

    같은 폴더의 고유 임시 파일에 기록하고 flush·fsync한 뒤,
    파일을 닫고 os.replace로 기존 설정 파일을 교체합니다.
    저장 실패는 예외로 호출부에 전달하며 임시 파일 정리를 시도합니다.
    """
    if not isinstance(settings, HighlightSettings):
        raise TypeError("HighlightSettings 객체가 필요합니다.")

    parser = configparser.ConfigParser(interpolation=None)
    parser["highlight"] = {
        "enabled": str(settings.enabled).lower(),
        "diameter": str(settings.diameter),
        "color": settings.color,
        "opacity": str(settings.opacity),
        "style": settings.style,
        "line_width": str(settings.line_width),
        "click_enabled": str(settings.click_enabled).lower(),
        "left_click_color": settings.left_click_color,
        "right_click_color": settings.right_click_color,
        "click_duration_ms": str(settings.click_duration_ms),
        "click_style": settings.click_style,
        "click_line_width": str(settings.click_line_width),
        "wheel_enabled": str(settings.wheel_enabled).lower(),        
        "wheel_color": settings.wheel_color,
        "wheel_duration_ms": str(settings.wheel_duration_ms),
        "wheel_line_width": str(settings.wheel_line_width),
        "cursor_enabled": str(settings.cursor_enabled).lower(),
        "cursor_level": str(settings.cursor_level),        
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:
        # 같은 폴더에 만들어 교체 작업이 같은 파일시스템에서 이루어지게 합니다.
        # 임시 파일은 고유 이름을 사용하고 Windows에서 교체 전에 닫습니다.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix="settings-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            parser.write(stream, space_around_delimiters=False)
            stream.flush()
            os.fsync(stream.fileno())

        # 저장 중에는 원래 파일을 직접 덮어쓰지 않습니다.
        os.replace(temporary_path, path)

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                # 임시 파일 정리 오류가 최초 저장 오류를 가리지 않도록 합니다.
                logger.warning(
                    "임시 설정 파일 정리 실패: %s",
                    temporary_path,
                    exc_info=True,
                )