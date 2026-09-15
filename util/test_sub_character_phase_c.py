#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[Phase C] 3인자 스위치(-chr_num3) CLI/UI 배선 검증 테스트

대상 변경 (2026-09-13):
  1. llm_novel_gui_textual.py : -chr_num3 파싱, 4-1번 서브 시트 메뉴, Step1/2/reset/복구 표시
  2. llm_novel_gui.py         : main/-auto/menu9 3곳에 -chr_num3 재적용
  3. run_main.sh / run_auto.sh: -chr_num3 전달

실행: /usr/bin/python3 util/test_sub_character_phase_c.py
"""
import os
import re
import sys
import types
import subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _install_stubs():
    try:
        import openai  # noqa: F401
    except ModuleNotFoundError:
        stub = types.ModuleType("openai")

        class _Any:
            def __init__(self, *a, **k):
                pass
            def __getattr__(self, item):
                return _Any()

        stub.__getattr__ = lambda name: _Any()
        for n in ("OpenAI", "APITimeoutError", "APIStatusError"):
            setattr(stub, n, type(n, (Exception,), {}) if "Error" in n else _Any)
        sys.modules["openai"] = stub


_install_stubs()
sys.path.insert(0, BASE)
os.chdir(BASE)

import config  # noqa: E402

RESULTS = []


def check(title, cond, detail=""):
    RESULTS.append((title, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'} | {title}" + (f"  → {detail}" if detail else ""))


def section(t):
    print(f"\n=== {t} ===")


def read(path):
    return open(os.path.join(BASE, path), encoding="utf-8").read()


# ── A. CLI 파싱 동작 (llm_novel_gui_textual) ──────────────────────────────────
section("A. textual GUI -chr_num3 파싱 (실제 코드 exec 검증)")
ttext = read("llm_novel_gui_textual.py")
m = re.search(r"(cmd_args = \{.*?config\.chr_num3 = cmd_args\[\"chr_num3\"\])", ttext, re.S)
check("A1 on_mount의 cmd_args 파싱 블록에서 chr_num3 추출 가능", bool(m))
if m:
    code = "\n".join([ln[8:] if ln.startswith(" " * 8) else ln for ln in m.group(1).split("\n")])

    def run_args(argv):
        config.chr_num3 = -1
        config.selected_jinshugai_id = None
        config.cmd_job = None
        config.cmd_job2 = None
        ns = {"sys": sys, "config": config}
        old = sys.argv
        sys.argv = ["llm_novel_gui_textual.py"] + argv
        try:
            exec(compile(code, "<cli>", "exec"), ns)
        finally:
            sys.argv = old
        return ns["cmd_args"]["chr_num3"], config.chr_num3

    v, c = run_args(["-chr_num3", "1"])
    check("A2 '-chr_num3 1' → config.chr_num3 = 1", v == 1 and c == 1, f"cmd_args={v}, config={c}")
    v, c = run_args(["--chr_num3", "0"])
    check("A3 '--chr_num3 0' → 0", v == 0 and c == 0, f"cmd_args={v}, config={c}")
    v, c = run_args(["-id", "3", "-job", "2"])
    check("A4 인자 없으면 None → config 미변경 (2인 모드 유지)", v is None and c == -1, f"cmd_args={v}, config={c}")
    v, c = run_args(["-chr_num3", "1", "-id", "5"])
    check("A5 다른 인자와 혼용 시에도 파싱", v == 1 and c == 1 and config.selected_jinshugai_id == 5,
          f"chr_num3={v}, id={config.selected_jinshugai_id}")
    config.chr_num3 = 0
    config.selected_jinshugai_id = None

# ── B. textual GUI 표시/메뉴 ──────────────────────────────────────────────────
section("B. textual GUI 메뉴·표시")
check("B1 메뉴에 서브 캐릭터 항목", 'id="sub_setup"' in ttext and "서브 캐릭터 설정" in ttext)
check("B2 설명(description) 맵에 sub_setup", '"sub_setup":' in ttext and "chr_num3=1" in ttext)
check("B3 worker_map에 sub_setup 연결", '"sub_setup": self._worker_sub_setup' in ttext)
check("B4 _worker_sub_setup 구현 (2인 모드 가드 + sub_sheet 호출)",
      "def _worker_sub_setup" in ttext and "character_setup.sub_sheet()" in ttext
      and "chr_num3', 0) != 1" in ttext)
check("B5 Step1 완료 메시지에 서브캐릭터 라인", "서브캐릭터: {config.name3}" in ttext)
check("B6 Step2 완료 메시지에 서브 가이드 수", "서브캐릭터 가이드 수:" in ttext)
check("B7 reset 결과에 모드 표시", "chr_num3: {getattr(config, 'chr_num3', 0)}" in ttext and "3인 모드" in ttext)
check("B8 세션 복구 메시지에 서브캐릭터", "progress_state.get('name3')" in ttext)

# ── C. curses GUI (llm_novel_gui.py) ─────────────────────────────────────────
section("C. curses GUI -chr_num3 재적용")
gtext = read("llm_novel_gui.py")
n_parse = len(re.findall(r'"-chr_num3", "--chr_num3"', gtext))
check("C1 main + _auto_run + menu9 총 3곳 파싱", n_parse == 3, f"{n_parse}곳")
check("C2 main()에서 config.chr_num3 반영", "config.chr_num3 = cmd_chr_num3" in gtext)
check("C3 인자 미지정 시 0 강제 (inc_flag 규칙과 동일)", gtext.count("config.chr_num3 = 0") == 2)

# ── D. 셸 스크립트 배선 ───────────────────────────────────────────────────────
section("D. run_main.sh / run_auto.sh")
for sh in ("run_main.sh", "run_auto.sh"):
    try:
        r = subprocess.run(["bash", "-n", os.path.join(BASE, sh)], capture_output=True, text=True)
        check(f"D1 {sh} 문법 정상", r.returncode == 0, r.stderr.strip()[:80])
    except Exception as e:
        check(f"D1 {sh} 문법 정상", False, str(e))
mtext = read("run_main.sh")
check("D2 run_main.sh -chr_num3 파싱 + 전달",
      '-chr_num3)' in mtext and 'CMD="$CMD -chr_num3 $CHR_NUM3"' in mtext)
atext = read("run_auto.sh")
check("D3 run_auto.sh -chr_num3 / CHR_NUM3 환경변수 지원",
      '-chr_num3)' in atext and 'CHR_NUM3="${CHR_NUM3:-}"' in atext)


def simulate_main(sh_path, extra_args):
    """스크립트 말미의 `$CMD` 실행을 echo로 치환해 명령 문자열을 회수한다."""
    src = read(sh_path)
    # 부수효과 방지: 로그를 지우는 'rm ...'와 venv 'source ...'는 무력화한다
    src = re.sub(r"^\s*rm\s", " : rm-skipped ", src, flags=re.M)
    src = re.sub(r"^\s*source\s", " : source-skipped ", src, flags=re.M)
    # select_python.sh 를 source 하지 않으므로 해석기 변수는 여기서 직접 부여한다 (명령 문자열을 실환경처럼 복원)
    src = 'PYTHON_BIN=python\n' + src
    patched = re.sub(r"^(\$CMD)$", 'echo "CMD>>$CMD"', src, flags=re.M)
    if "CMD>>$CMD" not in patched:
        patched = re.sub(r"(nohup )(\$CMD)", r'\1echo "CMD>>$CMD" #', patched)
    r = subprocess.run(["bash", "-s", "--"] + extra_args, input=patched,
                       capture_output=True, text=True, cwd=BASE)
    out = (r.stdout or "") + (r.stderr or "")
    mm = re.search(r"CMD>>(.*)", out)
    return mm.group(1).strip() if mm else out.strip()[-200:]


cmd = simulate_main("run_main.sh", ["-id", "1", "-chr_num3", "1"])
check("D4 run_main.sh '-id 1 -chr_num3 1' → 명령에 -chr_num3 1 포함",
      "-chr_num3 1" in cmd and "-id 1" in cmd, cmd[:110])
check("D4b run_main.sh 명령이 해석기로 시작 (빈 문자열 실행 아님)", cmd.startswith("python "), cmd[:40])
cmd2 = simulate_main("run_main.sh", ["-id", "1"])
check("D5 run_main.sh 인자 없으면 -chr_num3 미포함 (2인 모드 무영향)", "-chr_num3" not in cmd2, cmd2[:110])
cmd3 = simulate_main("run_auto.sh", ["-chr_num3", "1"])
check("D6 run_auto.sh '-chr_num3 1' → auto 커맨드에 포함", "-chr_num3 1" in cmd3 and "--auto" in cmd3, cmd3[:110])
check("D6b run_auto.sh 명령이 해석기로 시작", cmd3.startswith("python "), cmd3[:40])
cmd4 = simulate_main("run_auto.sh", [])
check("D7 run_auto.sh 인자 없으면 기존 명령 유지", "-chr_num3" not in cmd4 and "--auto" in cmd4, cmd4[:110])

# ── E. 백업 규율 (AGENTS) ─────────────────────────────────────────────────────
section("E. 수정 파일 백업 존재 (AGENTS 로컬 백업 규칙)")
for f in ("config.py", "common_def.py", "llm_novel_gui_func.py", "theme_gen_auto.py",
          "character_setup.py", "plot_gen.py", "story_gen.py", "full_episode_gen.py",
          "llm_novel_gui_textual.py", "llm_novel_gui.py", "run_main.sh", "run_auto.sh",
          "openAPI_control.py",
          "theme/elements.yaml", "theme/prompts.txt", "plot/prompts.txt",
          "episode/prompts.txt", "episode/variables.json"):
    p = os.path.join(BASE, f)
    check(f"E1 {f}.bak 존재", os.path.exists(p + ".bak"))

# ── 결과 ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
failed = [t for t, ok, _ in RESULTS if not ok]
print(f"총 {len(RESULTS)}건 검증 / 통과 {len(RESULTS)-len(failed)}건 / 실패 {len(failed)}건")
for t in failed:
    print(f"  ✗ {t}")
print("=" * 62)
sys.exit(1 if failed else 0)
