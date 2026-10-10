"""실제 화면 이미지를 내장한 오프라인 HTML 사용설명서를 생성합니다."""

import base64
from html import escape
from pathlib import Path


DOCS_DIRECTORY = Path(__file__).resolve().parent
IMAGE_DIRECTORY = DOCS_DIRECTORY / "manual-images"
OUTPUT_PATH = DOCS_DIRECTORY / "사용설명서.html"


def create_screenshot(name: str, caption: str) -> str:
    """PNG를 문서에 내장하여 별도 이미지 파일 없이 표시합니다."""
    image_path = IMAGE_DIRECTORY / f"{name}.png"
    data = image_path.read_bytes()

    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"PNG 파일이 아닙니다: {image_path}")

    encoded = base64.b64encode(data).decode("ascii")
    caption_text = escape(caption)

    return f"""
    <figure>
      <button class="screenshot" type="button"
              aria-label="{caption_text} 확대">
        <img src="data:image/png;base64,{encoded}"
             alt="{caption_text}">
      </button>
      <figcaption>{caption_text} · 클릭하면 확대됩니다.</figcaption>
    </figure>
    """


def create_manual() -> str:
    """목차·사용 절차·실제 화면·메뉴 예시를 하나의 HTML로 구성합니다."""
    sections = [
        (
            "start",
            "1. 실행과 트레이 메뉴",
            """
            <ol>
              <li>배포받은 Spotlight 폴더 전체를 원하는 위치에 둡니다.</li>
              <li><strong>Spotlight.exe</strong>를 실행합니다.</li>
              <li>작업표시줄 알림 영역에서 노란 원과 흰색 커서 아이콘을 찾습니다.
                  숨겨져 있으면 숨겨진 아이콘 표시 버튼을 누릅니다.</li>
              <li>아이콘을 우클릭하여 정보·설정·종료를 선택합니다.
                  더블 클릭하면 설정 창이 열립니다.</li>
            </ol>
            <div class="notice">
              EXE와 <code>_internal</code> 폴더를 함께 유지해 주세요.
              실행 PC에 Python을 설치할 필요는 없습니다.
            </div>
            <figure class="tray-example">
              <svg viewBox="0 0 360 190" role="img"
                   aria-labelledby="tray-title">
                <title id="tray-title">트레이 메뉴 예시: 정보, 설정, 종료</title>
                <rect x="10" y="140" width="340" height="40"
                      rx="8" fill="#e8edf3"/>
                <circle cx="55" cy="160" r="16" fill="#FFD54F"/>
                <path d="M55 160 L55 174 L59 171 L62 178
                         L66 176 L63 169 L69 169 Z"
                      fill="white" stroke="#182235" stroke-width="1.2"/>
                <text x="85" y="165" font-size="13" fill="#334155">
                  Spotlight 아이콘
                </text>
                <rect x="200" y="12" width="140" height="122"
                      rx="6" fill="white" stroke="#94a3b8"/>
                <text x="220" y="43" font-size="15">정보</text>
                <text x="220" y="77" font-size="15">설정</text>
                <line x1="210" y1="91" x2="330" y2="91"
                      stroke="#e2e8f0"/>
                <text x="220" y="118" font-size="15">종료</text>
              </svg>
              <figcaption>
                트레이 메뉴 예시 — 실제 캡처가 아닌 안내 그림입니다.
                Windows 환경에 따라 위치와 모양이 달라집니다.
              </figcaption>
            </figure>
            """,
            None,
        ),
        (
            "highlight",
            "2. 강조원 설정",
            """
            <p>트레이에서 <strong>설정 → 강조원</strong>을 선택합니다.</p>
            <ul>
              <li><strong>활성화:</strong> 커서를 따라가는 강조원을 켜거나 끕니다.</li>
              <li><strong>지름:</strong> 원의 크기를 조절합니다.</li>
              <li><strong>색상:</strong> 색상 선택 버튼으로 팔레트를 열거나
                  <code>#RRGGBB</code> 형식으로 입력합니다.</li>
              <li><strong>불투명도:</strong> 높을수록 진하게 표시됩니다.
                  0%에서는 보이지 않습니다.</li>
              <li><strong>표시 방식:</strong> 채움 또는 테두리를 선택합니다.</li>
              <li><strong>선 두께:</strong> 테두리 방식에서 조절합니다.</li>
            </ul>
            <p class="result">확인 결과: 변경한 강조원이 커서를 따라 표시됩니다.</p>
            """,
            "highlight",
        ),
        (
            "click",
            "3. 클릭 효과 설정",
            """
            <p><strong>클릭</strong> 탭을 선택합니다.</p>
            <ul>
              <li>활성화 체크로 클릭 효과만 켜거나 끕니다.</li>
              <li>왼쪽·오른쪽 클릭 색상을 각각 선택합니다.</li>
              <li>지속 시간은 효과가 표시되는 시간이며 단위는 ms입니다.
                  1000ms는 1초입니다.</li>
              <li>채움 또는 테두리를 선택하고, 테두리에서는 선 두께를 조절합니다.</li>
            </ul>
            <p class="result">확인 결과: 클릭한 위치에 효과가 나타났다가 사라집니다.
               마우스를 움직여도 효과는 생성 위치에 남습니다.</p>
            """,
            "click",
        ),
        (
            "wheel",
            "4. 휠 효과 설정",
            """
            <p><strong>휠</strong> 탭을 선택합니다.</p>
            <ul>
              <li>활성화 체크로 휠 효과만 켜거나 끕니다.
                  원래 스크롤은 유지됩니다.</li>
              <li>색상·지속 시간·선 두께를 조절합니다.</li>
              <li>위로 돌리면 테두리가 커지고, 아래로 돌리면 작아집니다.</li>
            </ul>
            <p class="result">확인 결과: 생성 당시 강조원 범위 안에서 효과가
               확대·축소됩니다. 효과 위치는 생성된 위치에 고정됩니다.</p>
            <p>클릭과 휠 효과는 합계 최대 3개까지 표시됩니다.</p>
            """,
            "wheel",
        ),
        (
            "pointer",
            "5. 포인터 확대",
            """
            <p><strong>포인터</strong> 탭을 선택합니다.</p>
            <ol>
              <li>포인터 확대 사용을 체크합니다.</li>
              <li>슬라이더로 1~15단계를 선택합니다.</li>
              <li>슬라이더를 놓고 실제 포인터 크기를 확인합니다.</li>
            </ol>
            <p>드래그 중에는 단계와 크기 문구가 바뀌고,
               놓으면 시스템 커서에 반영됩니다.</p>
            <p class="result">확인 결과: 화살표뿐 아니라 텍스트 입력·링크 등에서
               사용하는 커서도 확대됩니다. 확대를 끄면 현재 Windows 설정으로 복원됩니다.</p>
            <div class="notice">아래 캡처는 확대 사용이 켜진 1단계 상태입니다.
              최초 기본값은 확대 꺼짐입니다. 1단계는 32×32px,
              5단계는 96×96px, 15단계는 256×256px입니다.</div>
            """,
            "pointer",
        ),
        (
            "save",
            "6. 저장·취소·전체 초기화",
            """
            <p>입력값을 변경하면 저장 전에 화면에 미리 반영됩니다.</p>
            <table>
              <thead><tr><th>버튼</th><th>동작</th></tr></thead>
              <tbody>
                <tr><td>적용</td><td>설정을 저장하고 창을 유지합니다.</td></tr>
                <tr><td>확인</td><td>설정을 저장하고 창을 닫습니다.</td></tr>
                <tr><td>취소·X·Esc</td><td>마지막 적용값으로 돌아갑니다.
                  적용하지 않은 변경은 저장하지 않습니다.</td></tr>
                <tr><td>전체 초기화</td><td>모든 설정을 기본값으로 미리 표시합니다.
                  적용 또는 확인을 눌러야 저장됩니다.</td></tr>
              </tbody>
            </table>
            <p>적용 → 추가 변경 → 취소 순서에서는 앞서 적용한 값이 유지됩니다.
               초기화 후에도 저장 전에는 취소로 되돌릴 수 있습니다.</p>
            <p>기본값: 강조원 지름 60·노란색·불투명도 30%·채움,
               클릭 효과 테두리, 휠 효과 켜짐, 포인터 확대 꺼짐입니다.</p>
            """,
            None,
        ),
        (
            "info",
            "7. 정보 확인과 종료",
            """
            <p>트레이의 <strong>정보</strong>를 선택하면 별도 정보 창이 열립니다.
               제품명·버전·배포 주체·저작권과 실행 파일의 SHA-256을 확인할 수 있습니다.</p>
            <p>해시 대상 경로는 설치 위치에 따라 달라집니다.
               파일이 변경되거나 재빌드되면 해시도 달라질 수 있습니다.
               소스 실행에서는 배포 EXE 대신 run_spotlight.py의 해시를 표시합니다.</p>
            <p>닫기·X·Esc는 정보 창만 닫습니다.
               프로그램을 끝내려면 트레이의 <strong>종료</strong>를 선택합니다.</p>
            <p class="result">확인 결과: 강조원·효과·트레이 아이콘과 열린 창이 닫히고,
               확대했던 시스템 커서는 현재 Windows 설정으로 복원됩니다.</p>
            """,
            "info",
        ),
        (
            "notes",
            "8. 발표·녹화와 사용 시 참고",
            """
            <ul>
              <li><strong>Office Home 2016:</strong> 슬라이드쇼에서 강조원이 회색으로
                  보이면 파일 → 옵션 → 고급 → 표시의
                  ‘하드웨어 그래픽 가속 사용 안 함’을 체크한 조건에서
                  정상 색상을 확인했습니다.</li>
              <li><strong>Windows 캡처 도구:</strong> 화면 영역 녹화에서
                  강조원·클릭·휠 효과가 포함되는 것을 확인했습니다.
                  PC에 녹화 기능이 있는지 확인해 주세요.</li>
              <li><strong>Xbox Game Bar:</strong> 화면에서는 효과가 보여도
                  녹화 영상에는 누락될 수 있습니다.</li>
              <li><strong>oCam:</strong> 최소화 후 Chrome 녹화는 정상입니다.
                  oCam 자체 창 위에서는 클릭·휠 효과가 표시되지 않는 제한이 있습니다.</li>
            </ul>
            <p>Windows 11, 두 모니터의 100·150·175%와 혼합 배율에서 확인했습니다.
               Windows 10·200%·원격 환경·관리자 앱 등은 별도 미검증입니다.</p>
            <p>설정과 로그는 <code>%LOCALAPPDATA%\\Spotlight</code>에 저장됩니다.
               강제 종료 후에는 프로그램을 다시 실행하여 복구하도록 해 주세요.
               복구 오류가 있으면 표식을 임의 삭제하지 말고 로그를 확인해 주세요.</p>
            """,
            None,
        ),
    ]

    navigation = []
    contents = []

    for section_id, title, text, image_name in sections:
        navigation.append(
            f'<a href="#{section_id}">{escape(title)}</a>'
        )
        screenshot = (
            create_screenshot(image_name, title)
            if image_name else ""
        )
        contents.append(
            f'<section id="{section_id}">'
            f'<h2>{escape(title)}</h2>{text}{screenshot}</section>'
        )

    template = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spotlight 1.0 사용설명서</title>
<style>
* { box-sizing: border-box; }
body {
  margin: 0; color: #243044; background: #f4f6fa;
  font-family: "Malgun Gothic", sans-serif; line-height: 1.75;
}
nav {
  position: fixed; inset: 0 auto 0 0; width: 250px;
  padding: 28px 20px; overflow: auto;
  background: #172338; color: white;
}
nav strong { display: block; color: #ffd54f; font-size: 24px; }
nav a {
  display: block; margin-top: 12px;
  color: #e2e8f0; text-decoration: none;
}
nav a:hover, nav a:focus { color: #ffd54f; text-decoration: underline; }
main { max-width: 1150px; margin-left: 250px; padding: 36px; }
header, section {
  background: white; border: 1px solid #e2e8f0;
  border-radius: 12px; padding: 26px; margin-bottom: 24px;
}
h1 { margin: 0; font-size: 30px; }
h2 { margin-top: 0; font-size: 23px; }
section { scroll-margin-top: 20px; }
li { margin-bottom: 8px; }
.notice, .result {
  padding: 12px 16px; border-left: 4px solid #e9bc2b;
  background: #fff9df; border-radius: 4px;
}
.result { border-color: #3b82f6; background: #eff6ff; }
figure { margin: 24px 0 0; }
.screenshot {
  display: block; max-width: 100%; padding: 0;
  border: 0; background: transparent; cursor: zoom-in;
}
.screenshot img {
  display: block; max-width: 100%; height: auto;
  border-radius: 8px; border: 1px solid #d9e0ea;
}
figcaption { margin-top: 8px; font-size: 13px; color: #64748b; }
.tray-example { max-width: 420px; }
.tray-example svg { width: 100%; height: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px; border: 1px solid #d9e0ea; text-align: left; }
th { background: #f1f5f9; }
code { overflow-wrap: anywhere; }
dialog {
  max-width: 95vw; max-height: 95vh; padding: 20px;
  border: 0; border-radius: 12px; overflow: auto;
}
dialog::backdrop { background: rgba(15, 23, 42, .7); }
dialog img { display: block; max-width: 100%; height: auto; }
dialog button {
  margin-bottom: 12px; padding: 8px 18px;
  border: 1px solid #94a3b8; border-radius: 6px; cursor: pointer;
}
@media (max-width: 800px) {
  nav { position: static; width: auto; }
  main { margin-left: 0; padding: 16px; }
  header, section { padding: 20px; }
}
@media print {
  nav, dialog { display: none; }
  main { margin: 0; padding: 0; }
  body { background: white; }
  header, section { border: 0; }
  figure, table { break-inside: avoid; }
}
</style>
</head>
<body>
<nav aria-label="사용설명서 목차">
<strong>Spotlight</strong>
<p>1.0 사용설명서</p>
@@NAVIGATION@@
</nav>
<main>
<header>
<h1>마우스 움직임을 더 잘 보이게</h1>
<p>Spotlight 1.0.0 · 고용노동부 김동현</p>
<p>설정 화면을 따라 강조원·클릭·휠 효과와 포인터 확대를 사용해 보세요.</p>
<p>인터넷 연결 없이 읽을 수 있습니다. 화면 이미지는 클릭하여 확대합니다.</p>
</header>
@@CONTENTS@@
<footer>
<p>Copyright © 2026 고용노동부 김동현</p>
<p>문서 검토용 초안 · 실제 설정/정보 캡처 5개 포함 · 트레이 메뉴는 예시 그림</p>
</footer>
</main>
<dialog id="image-dialog" aria-label="화면 이미지 확대">
<button type="button" id="close-image">닫기</button>
<img id="expanded-image" alt="">
</dialog>
<script>
const imageDialog = document.getElementById("image-dialog");
const expandedImage = document.getElementById("expanded-image");

document.querySelectorAll(".screenshot").forEach(button => {
  button.addEventListener("click", () => {
    const image = button.querySelector("img");
    expandedImage.src = image.src;
    expandedImage.alt = image.alt;
    imageDialog.showModal();
  });
});

document.getElementById("close-image").addEventListener("click", () => {
  imageDialog.close();
});

imageDialog.addEventListener("click", event => {
  if (event.target === imageDialog) {
    const bounds = imageDialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right ||
        event.clientY < bounds.top || event.clientY > bounds.bottom) {
      imageDialog.close();
    }
  }
});
</script>
</body>
</html>
"""

    return (
        template.replace("@@NAVIGATION@@", "\n".join(navigation))
        .replace("@@CONTENTS@@", "\n".join(contents))
    )


def main() -> int:
    """이미지를 모두 읽은 뒤 HTML 초안을 저장합니다."""
    document = create_manual()
    OUTPUT_PATH.write_text(document, encoding="utf-8")
    print(f"MANUAL_CREATED: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())