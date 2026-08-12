from __future__ import annotations

import base64
import html
from pathlib import Path


DOCS = Path(__file__).resolve().parent
IMAGES = DOCS / "images"
OUTPUT = DOCS / "SPOTLIGHT_USER_GUIDE.html"


def image(name: str, alt: str) -> str:
    data = base64.b64encode((IMAGES / name).read_bytes()).decode("ascii")
    return (
        '<figure><img src="data:image/png;base64,'
        f'{data}" alt="{html.escape(alt)}"><figcaption>{html.escape(alt)}</figcaption>'
        "</figure>"
    )


def main() -> int:
    document = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spotlight 사용설명서</title>
<style>
  :root {{ color-scheme: light; --accent:#d6a900; --ink:#202124; --muted:#5f6368; --line:#dadce0; --panel:#f8f9fa; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:#eef1f4; color:var(--ink); font-family:"Malgun Gothic","Apple SD Gothic Neo",Arial,sans-serif; line-height:1.7; }}
  main {{ max-width:900px; margin:32px auto; padding:48px 56px; background:white; border-radius:14px; box-shadow:0 5px 24px rgba(0,0,0,.09); }}
  h1 {{ margin:0 0 12px; font-size:2.15rem; line-height:1.25; }}
  h1::before {{ content:""; display:inline-block; width:18px; height:18px; margin-right:12px; border:7px solid #ffd60a; border-radius:50%; vertical-align:1px; }}
  h2 {{ margin:46px 0 16px; padding-bottom:8px; border-bottom:2px solid var(--line); font-size:1.45rem; }}
  h3 {{ margin:30px 0 8px; font-size:1.1rem; }}
  p {{ margin:10px 0; }}
  ul {{ padding-left:24px; }}
  li {{ margin:6px 0; }}
  code {{ padding:2px 6px; background:#f1f3f4; border-radius:4px; font-family:Consolas,monospace; }}
  pre {{ overflow:auto; padding:16px 18px; background:#202124; color:#f8f9fa; border-radius:8px; line-height:1.5; }}
  pre code {{ padding:0; background:none; color:inherit; }}
  figure {{ margin:22px 0 26px; text-align:center; }}
  img {{ max-width:100%; height:auto; border:1px solid #c9cdd1; border-radius:7px; box-shadow:0 2px 8px rgba(0,0,0,.08); }}
  figcaption {{ margin-top:7px; color:var(--muted); font-size:.88rem; }}
  .intro {{ color:#3c4043; font-size:1.06rem; }}
  .note {{ margin:16px 0; padding:12px 16px; border-left:4px solid var(--accent); background:#fffbea; }}
  @media (max-width:700px) {{ body {{ background:white; }} main {{ margin:0; padding:28px 20px; border-radius:0; box-shadow:none; }} }}
  @media print {{ body {{ background:white; }} main {{ max-width:none; margin:0; padding:0; box-shadow:none; }} h2 {{ break-after:avoid; }} figure {{ break-inside:avoid; }} }}
</style>
</head>
<body>
<main>
<h1>Spotlight 사용설명서</h1>
<p class="intro">Spotlight는 마우스 포인터와 클릭·휠 동작을 화면에서 쉽게 알아볼 수 있도록 표시하는 Windows 프로그램입니다. 실행하면 작업표시줄 창을 만들지 않고 시스템 트레이에서 동작합니다.</p>

<h2>실행과 종료</h2>
<p><code>spotlight.exe</code>를 더블 클릭해 실행합니다.</p>
<p>실행 후 Windows 알림 영역의 Spotlight 아이콘을 마우스 오른쪽 버튼으로 누릅니다.</p>
{image("tray-menu.png", "Spotlight 트레이 메뉴")}
<ul><li><code>설정</code>: 설정 화면을 엽니다.</li><li><code>프로그램 종료</code>: Spotlight를 종료하고 원래 시스템 커서를 복원합니다.</li></ul>
<p class="note">창을 강제로 닫기보다 트레이 메뉴의 <code>프로그램 종료</code>를 사용하는 것이 안전합니다.</p>

<h2>포인터 설정</h2>
{image("settings-pointer.png", "포인터 설정")}
<p>슬라이더에서 포인터 크기를 1~15단계로 선택합니다. 1단계는 32px이며 단계마다 16px씩 커집니다.</p>
<ul><li>슬라이더 이동: 커서 크기를 임시로 미리 봅니다.</li><li><code>Apply</code>: 현재 크기를 저장하고 설정 창을 유지합니다.</li><li><code>확인</code>: 현재 크기를 저장하고 설정 창을 닫습니다.</li><li><code>취소</code>: 마지막으로 저장한 크기로 되돌리고 창을 닫습니다.</li></ul>
<p><code>Apply</code>를 누른 뒤 다시 슬라이더를 움직이고 취소하면 가장 최근에 Apply한 크기로 돌아갑니다.</p>

<h2>강조 원 설정</h2>
{image("settings-spotlight-fill.png", "채움 방식 강조 원 설정")}
<ul><li><code>강조 원 표시</code>: 강조 원을 켜거나 끕니다.</li><li><code>원 크기</code>: 강조 원의 지름을 지정합니다. 클릭 효과의 최대 크기와 휠 효과의 바깥 크기도 이 값을 사용합니다.</li><li><code>색상</code>: 색상 선택기를 사용하거나 <code>#RRGGBB</code> 값을 직접 입력합니다.</li><li><code>불투명도</code>: 강조 원의 투명도를 조절합니다.</li><li><code>표시 방식</code>: <code>채움</code> 또는 <code>테두리</code>를 선택합니다.</li></ul>
<p>채움 방식에서는 테두리 두께가 비활성화됩니다. 테두리 방식을 선택하면 두께를 조절할 수 있습니다.</p>
{image("settings-spotlight-outline.png", "테두리 방식 강조 원 설정")}

<h2>클릭 효과 설정</h2>
{image("settings-click.png", "클릭 효과 설정")}
<ul><li>왼쪽 클릭과 오른쪽 클릭의 색상을 각각 지정할 수 있습니다.</li><li>지속 시간은 클릭 효과가 화면에 남아 있는 시간입니다.</li><li>클릭 효과의 최대 크기는 강조 원의 <code>원 크기</code>와 같습니다.</li></ul>
<p>클릭하면 클릭 위치에 불투명한 원형 효과가 나타납니다.</p>
{image("click-effect.png", "클릭 효과")}

<h2>휠 효과 설정</h2>
{image("settings-wheel.png", "휠 효과 설정")}
<ul><li><code>색상</code>: 휠 효과의 색상을 지정합니다.</li><li><code>지속 시간</code>: 애니메이션이 재생되는 시간을 지정합니다.</li><li><code>선 두께</code>: 원형 효과의 선 두께를 지정합니다.</li></ul>
<p>휠을 위로 움직이면 원이 안쪽에서 바깥쪽으로 커지고, 아래로 움직이면 바깥쪽에서 안쪽으로 작아집니다. 바깥쪽 크기는 강조 원의 <code>원 크기</code>와 같고 안쪽 크기는 그 25%입니다.</p>
{image("wheel-effect.png", "휠 효과")}

<h2>문제 해결</h2>
<h3>트레이 아이콘이 보이지 않을 때</h3><p>Windows 알림 영역의 숨겨진 아이콘 목록을 확인합니다. Spotlight는 작업표시줄에 일반 창을 표시하지 않습니다.</p>
<h3>커서가 원래 크기로 돌아오지 않을 때</h3><p>Spotlight를 다시 실행하면 이전 실행의 복구 표식을 확인해 저장된 Windows 커서 구성을 복원합니다. 이후 트레이 메뉴에서 정상 종료합니다.</p>
<h3>특정 프로그램에서 클릭이나 휠 효과가 나타나지 않을 때</h3><p>Spotlight를 일반 권한으로 실행한 경우 관리자 권한 프로그램의 입력을 감지하지 못할 수 있습니다. 관리자 권한 프로그램에 대한 입력 감지는 현재 공식 지원 범위에 포함되지 않습니다.</p>
<h3>화면 녹화에 효과가 포함되지 않을 때</h3><p>전체 화면 또는 디스플레이 캡처를 사용합니다. 특정 창만 캡처하면 별도의 Spotlight 오버레이가 제외될 수 있습니다.</p>
</main>
</body>
</html>
"""
    OUTPUT.write_text(document, encoding="utf-8", newline="\n")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
