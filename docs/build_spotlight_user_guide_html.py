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
        f'<figure><img src="data:image/png;base64,{data}" alt="{html.escape(alt)}">'
        f'<figcaption>{html.escape(alt)}</figcaption></figure>'
    )


def main() -> int:
    document = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>Spotlight 사용자 가이드</title>
<style>
@page {{ size:A4; margin:16mm 17mm 17mm; }}
:root {{ --yellow:#ffd60a; --ink:#202124; --muted:#60646b; --line:#d9dde2; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; color:var(--ink); font-family:"Malgun Gothic","Noto Sans KR",sans-serif; font-size:10.5pt; line-height:1.62; }}
h1 {{ margin:0 0 4mm; font-size:25pt; line-height:1.2; }}
h1:before {{ content:""; display:inline-block; width:13px; height:13px; margin-right:9px; border:6px solid var(--yellow); border-radius:50%; }}
h2 {{ margin:10mm 0 4mm; padding-bottom:2mm; border-bottom:1.5px solid var(--line); font-size:16pt; break-after:avoid; }}
h3 {{ margin:6mm 0 1mm; font-size:11.5pt; break-after:avoid; }}
p {{ margin:2mm 0; }} ul {{ margin:2mm 0; padding-left:6mm; }} li {{ margin:1mm 0; }}
code {{ padding:1px 4px; background:#f1f3f4; border-radius:3px; font-family:Consolas,monospace; }}
.intro {{ color:#3c4043; font-size:11pt; }}
.note {{ margin:4mm 0; padding:3mm 4mm; border-left:4px solid #d6a900; background:#fffbea; }}
figure {{ margin:4mm auto 5mm; text-align:center; break-inside:avoid; }}
img {{ max-width:100%; max-height:117mm; border:1px solid #c9cdd1; border-radius:5px; }}
figcaption {{ margin-top:1mm; color:var(--muted); font-size:8.5pt; }}
.cover {{ min-height:255mm; display:flex; flex-direction:column; justify-content:center; break-after:page; }}
.cover .tag {{ color:#806800; font-weight:700; letter-spacing:.08em; }}
.cover .summary {{ max-width:145mm; margin-top:5mm; font-size:13pt; color:#4a4d52; }}
.cover .meta {{ margin-top:18mm; color:var(--muted); }}
</style></head><body>
<section class="cover"><div class="tag">WINDOWS DESKTOP GUIDE</div><h1>Spotlight 사용자 가이드</h1>
<p class="summary">마우스 포인터와 클릭·휠 동작을 화면에서 쉽게 알아볼 수 있도록 표시하는 Spotlight의 실행, 설정, 종료 방법을 안내합니다.</p>
<p class="meta">지원 환경: Windows<br>문서 버전: 2026년 8월</p></section>

<h2>1. 시작하기</h2>
<p><code>spotlight.exe</code>를 더블 클릭해 실행합니다. Spotlight는 일반 창을 만들지 않고 Windows 알림 영역(시스템 트레이)에서 동작합니다.</p>
{image("tray-menu.png", "Spotlight 트레이 메뉴")}
<ul><li><code>설정</code>: 설정 창을 엽니다.</li><li><code>프로그램 종료</code>: Spotlight를 종료하고 원래 시스템 커서를 복원합니다.</li></ul>
<p class="note">작업 표시줄에 창이 보이지 않아도 정상입니다. 종료할 때는 가능하면 트레이 메뉴의 <code>프로그램 종료</code>를 사용하세요.</p>

<h2>2. 포인터 설정</h2>
{image("settings-pointer.png", "포인터 크기 설정")}
<p><code>포인터</code> 탭의 슬라이더에서 크기를 1~15단계로 선택합니다. 1단계는 32px이며, 단계마다 16px씩 커집니다. 슬라이더를 움직이면 즉시 미리 볼 수 있습니다.</p>
<ul><li><code>Apply</code>: 변경 내용을 저장하되 설정 창은 유지합니다.</li><li><code>확인</code>: 변경 내용을 저장하고 창을 닫습니다.</li><li><code>취소</code>: 마지막으로 적용한 크기로 되돌리고 창을 닫습니다.</li></ul>

<h2>3. 강조 원 설정</h2>
{image("settings-spotlight-fill.png", "채움 방식의 강조 원 설정")}
<ul><li><code>강조 원 표시</code>: 포인터 주변 강조 원을 켜거나 끕니다.</li><li><code>원 크기</code>: 강조 원의 지름을 지정합니다.</li><li><code>색상</code>: 색상 선택기를 사용하거나 <code>#RRGGBB</code> 값을 입력합니다.</li><li><code>불투명도</code>: 강조 원의 투명도를 조절합니다.</li><li><code>표시 방식</code>: <code>채움</code> 또는 <code>테두리</code>를 선택합니다.</li></ul>
<p>테두리 방식을 선택하면 <code>테두리 두께</code>를 조절할 수 있습니다. 원 크기는 클릭 효과의 최대 크기와 휠 효과의 바깥 크기에도 사용됩니다.</p>
{image("settings-spotlight-outline.png", "테두리 방식의 강조 원 설정")}

<h2>4. 클릭 효과 설정</h2>
{image("settings-click.png", "클릭 효과 설정")}
<p><code>클릭 효과 사용</code>을 켜면 클릭한 위치에 원형 애니메이션이 표시됩니다. 왼쪽 클릭과 오른쪽 클릭의 색상을 각각 지정하고, <code>지속 시간</code>으로 효과가 남아 있는 시간을 조절합니다.</p>
{image("click-effect.png", "화면에 표시된 클릭 효과")}

<h2>5. 휠 효과 설정</h2>
{image("settings-wheel.png", "휠 효과 설정")}
<p><code>휠 효과 사용</code>을 켜면 스크롤 방향을 원형 애니메이션으로 표시합니다. 색상, 지속 시간, 선 두께를 설정할 수 있습니다. 휠을 위로 움직이면 안쪽에서 바깥쪽으로 커지고, 아래로 움직이면 바깥쪽에서 안쪽으로 작아집니다.</p>
{image("wheel-effect.png", "화면에 표시된 휠 효과")}

<h2>6. 문제 해결</h2>
<h3>트레이 아이콘이 보이지 않을 때</h3><p>Windows 알림 영역의 숨겨진 아이콘 목록을 확인하세요. Spotlight는 작업 표시줄에 일반 창을 표시하지 않습니다.</p>
<h3>커서가 원래 크기로 돌아오지 않을 때</h3><p>Spotlight를 다시 실행하면 이전 실행의 복구 정보를 확인해 저장된 Windows 커서 구성을 복원합니다. 이후 트레이 메뉴에서 정상 종료하세요.</p>
<h3>특정 프로그램에서 효과가 나타나지 않을 때</h3><p>Spotlight를 일반 권한으로 실행하면 관리자 권한 프로그램의 입력을 감지하지 못할 수 있습니다. 관리자 권한 프로그램에 대한 입력 감지는 현재 지원 범위에 포함되지 않습니다.</p>
<h3>녹화 화면에 효과가 포함되지 않을 때</h3><p>전체 화면 또는 디스플레이 캡처를 사용하세요. 특정 창만 캡처하면 별도의 Spotlight 오버레이가 제외될 수 있습니다.</p>
</body></html>"""
    OUTPUT.write_text(document, encoding="utf-8", newline="\n")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
