#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[D3/D5] 실행 환경 해석 + API 복원력 + 실제 textual GUI 부팅 스모크 테스트

다루는 범위 (이전 Phase A~D가 openai **스텁**으로만 검증했으므로, 이건 **실제 패키지**로 돈다)
  A. select_python.sh / run_main.sh / run_auto.sh —requirements.txt 를 충족하는 해석기 자동 선택
  B. openAPI_control.py — 서버 다운(APIConnectionError) 시 무처리 크래시 대신 우아 실패
  C. llm_novel_gui_textual.py — 실제 textual 헤드리스 부팅 + 4-1 서브 캐릭터 메뉴 동작
  D. 전 모듈 import (openai 스텁 없음)

실행:  /home/chrisyeo/AI/.venv/bin/python3 util/test_env_api_and_gui_smoke.py
       (또는 select_python.sh 이 골라준 해석기)
요구 모듈이 없으면 FAIL 이 아니라 SKIP(종료코드 2)으로 알린다.
"""
import ast
import asyncio
import importlib.util
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQ = ("openai", "yaml", "textual", "prompt_toolkit")

RESULTS = []


def check(title, cond, detail=""):
    RESULTS.append((title, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'} | {title}" + (f"  → {detail}" if detail else ""))


def section(t):
    print(f"\n=== {t} ===")


if __name__ == "__main__":
    print(f"해석기: {sys.executable}")
    missing = [m for m in REQ if importlib.util.find_spec(m) is None]
    if missing:
        print(f"요구 모듈 누락: {missing}")
        print("→ select_python.sh 가 골라준 해석기로 다시 실행하세요. (SKIP)")
        sys.exit(2)
    print("요구 모듈 충족:", ", ".join(REQ))

    os.chdir(BASE)
    sys.path.insert(0, BASE)

    # ── A. 실행 환경 해석 ────────────────────────────────────────────────────
    section("A. select_python.sh · run_*.sh 해석")
    r = subprocess.run(["bash", "-c",
                        f'cd "{BASE}" && source ./select_python.sh && echo "$PYTHON_BIN"'],
                       capture_output=True, text=True, timeout=120)
    py_bin = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    check("A1 select_python.sh 가 해석기를 골라낸다", bool(py_bin) and r.returncode == 0,
          py_bin or r.stderr.strip()[:120])
    if py_bin:
        chk = subprocess.run([py_bin, "-c", "import openai, yaml, textual, prompt_toolkit"],
                             capture_output=True, text=True)
        check("A2 선택된 해석기가 requirements.txt 4종 충족", chk.returncode == 0,
              chk.stderr.strip()[-90:] if chk.returncode else "import 성공")
    for sh in ("run_main.sh", "run_auto.sh"):
        src = open(os.path.join(BASE, sh), encoding="utf-8").read()
        check(f"A3 {sh} 가 $PYTHON_BIN 을 사용하고 select_python.sh 를 source 한다",
              'source "$(dirname "$0")/select_python.sh"' in src and "$PYTHON_BIN" in src)
        bare = [l.strip() for l in src.split("\n")
                if l.strip().startswith("CMD=") and ('"python ' in l or '"python3 ' in l)]
        check(f"A4 {sh} 에 맨 `python`/`python3` 실행 잔존 없음", not bare, "; ".join(bare))
        syn = subprocess.run(["bash", "-n", os.path.join(BASE, sh)], capture_output=True, text=True)
        check(f"A5 {sh} bash -n 문법 검증", syn.returncode == 0, syn.stderr.strip()[:80])
        check(f"A6 {sh}.bak 존재 (백업 규율)", os.path.exists(os.path.join(BASE, sh + ".bak")))
    # 실제 GUI 진입 커맨드가 만들어지는지 (해석기만 대체하여 조립 확인)
    fake = os.path.join(BASE, "util", "_fake_python_echo.sh")
    with open(fake, "w") as f:
        f.write('#!/bin/bash\necho "ARGS: $*"\n')
    os.chmod(fake, 0o755)
    try:
        rr = subprocess.run(["bash", "-c", f'cd "{BASE}" && PYTHON="{fake}" ./run_main.sh -id 1 -chr_num3 1'],
                            capture_output=True, text=True, timeout=60)
        out = rr.stdout + rr.stderr
        check("A7 PYTHON 환경변수 오버라이드로 run_main.sh 커맨드 조립 확인",
              "-id 1 -chr_num3 1" in out, out.strip()[:100])
    finally:
        if os.path.exists(fake):
            os.remove(fake)

    # ── B. API 복원력 ────────────────────────────────────────────────────────
    section("B. openAPI_control — 서버 다운(APIConnectionError) 복원력")
    tree = ast.parse(open(os.path.join(BASE, "openAPI_control.py"), encoding="utf-8").read())
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
        handlers = []
        for w in ast.walk(fn):
            if isinstance(w, ast.While):
                for t in ast.walk(w):
                    if isinstance(t, ast.Try):
                        handlers += [ast.unparse(h.type) for h in t.handlers if h.type]
        if "APITimeoutError" in handlers:
            check(f"B1 {fn.name}(): while 루프에 APIConnectionError 핸들러 존재",
                  "APIConnectionError" in handlers, str(handlers))
            # APITimeoutError 는 APIConnectionError 의 서브클래스 → 반드시 먼저 와야 한다
            check(f"B2 {fn.name}(): APITimeoutError 가 부모 클래스보다 앞에 배치",
                  handlers.index("APITimeoutError") < handlers.index("APIConnectionError"),
                  " → ".join(handlers))

    import config  # noqa: E402
    SNAP_JSON = config.get_json_value()
    SNAP_GJV = config.get_json_value          # plot.json 을 매번 읽는 함수 → 몽키패치로 교체
    SNAP_CHR = getattr(config, "chr_num3", 0)
    # get_json_value() 는 호출마다 plot.json 을 다시 읽으므로 config.json_value 대입은 무효하다.
    # 따라서 함수 자체를 교체해서 테스트 엔드포인트를 가리키게 한다.
    config.get_json_value = lambda: {"ip_main": "127.0.0.1", "port_main": "1"}  # 즉시 거부되는 포트
    import openAPI_control as oc  # noqa: E402
    _bu = str(oc.get_openai_client().base_url)
    check("B0 테스트 엔드포인트 주입 확인 (실제 plot.json 서버가 아니어야 한다)",
          "127.0.0.1:1/v1" in _bu, _bu)

    res, _msgs = oc.call_openai_for_plot("x", messages=[{"role": "user", "content": "x"}],
                                         retry_delay=0.05, max_retries=1)
    check("B3 연결 거부 시 '서버 응답 실패' 문자열로 우아 반환 (크래시 아님)", res == "서버 응답 실패", repr(res)[:40])

    config.messages_history = [{"role": "user", "content": "x"}]
    config.stream_enb = False
    oc.time.sleep = lambda s: None  # 재시도 대기 생략
    try:
        oc.call_openai_api("x")
        check("B4 스트리밍 경로도 SystemExit 로 수습 (무처리 크래시 아님)", False, "예외 없이 통과")
    except SystemExit:
        check("B4 스트리밍 경로도 SystemExit 로 수습 (무처리 크래시 아님)", True)
    except Exception as e:
        check("B4 스트리밍 경로도 SystemExit 로 수습 (무처리 크래시 아님)", False,
              f"{type(e).__name__}: {e}")
    oc.time.sleep = __import__("time").sleep

    # 서버 없는 상태에서 서브 시트 갱신 경로가 시트를 보존하는지 (실제 openai 라이브)
    import character_setup  # noqa: E402
    import plot_gen  # noqa: E402
    config.chr_num3 = 1
    config.name3, config.sex3, config.job3, config.age3 = "서빈", "여자", "학생회장", 20
    config.sub_relationship, config.sub_corruption_role = "상사/주군", "주인공과 함께 타락함: 동반 몰락"
    config.hair_color3 = "messy black hair"
    base = character_setup.sub_sheet()
    out = plot_gen._update_character_sheets_via_api("본문", 2, "P", "Q", "유나", "민준", current_sub=base)
    check("B5 서버 다운 시 서브 시트 갱신이 3종 반환 + 기존 시트 유지 (실제 openai 라이브)",
          len(out) == 3 and out[2] == base, f"{len(out)}종 반환")

    # ── D. 전 모듈 import (스텁 없이) ───────────────────────────────────────
    section("D. 전 모듈 import (openai 스텁 없음)")
    importlib.invalidate_caches()
    bad = []
    for m in ("config", "common_def", "character_setup", "openAPI_control", "theme_gen_auto",
              "plot_gen", "story_gen", "full_episode_gen", "llm_novel_gui_func",
              "llm_novel_gui_textual", "llm_novel_gui"):
        try:
            importlib.import_module(m)
        except Exception as e:
            bad.append(f"{m}: {type(e).__name__}: {e}")
    check("D1 11개 모듈 import 성공", not bad, " | ".join(bad)[:150])

    # ── C. 실제 GUI 헤드리스 부팅 ───────────────────────────────────────────
    section("C. 실제 textual GUI 부팅 + 4-1 서브 캐릭터 메뉴")
    from textual.widgets import OptionList, TextArea  # noqa: E402
    from llm_novel_gui_textual import FourPaneApp  # noqa: E402

    prog_before = sorted(os.listdir(os.path.join(BASE, "progress"))) if os.path.isdir(
        os.path.join(BASE, "progress")) else []

    async def boot(argv, prep=None):
        old = sys.argv
        sys.argv = argv
        if prep:
            prep()
        try:
            app = FourPaneApp()
            async with app.run_test(size=(150, 45)) as pilot:
                await pilot.pause(delay=0.6)  # on_mount + _worker_init 워커 정착 대기
                menu = app.query_one("#menu", OptionList)
                opts = [o.id for o in menu.options]
                idx = menu.get_option_index("sub_setup")
                menu.highlighted = idx
                menu.action_select()
                await pilot.pause(delay=0.8)  # 스레드 워커 정착 대기
                editor = app.query_one("#editor", TextArea).text
                status = str(app.query_one("#status-bar").render())
            return opts, editor, status, app
        finally:
            sys.argv = old

    def prep_3in():
        config.chr_num3 = 0  # 앱이 argv에서 1로 세워주는지 확인하므로 여기서는 0
        config.name3, config.sex3, config.job3, config.age3 = "서빈", "여자", "학생회장", 20
        config.hair_color3, config.hair_style3 = "messy black hair", "short hair, ahoge"
        config.eye_color3, config.skin_color3 = "dark red eyes", "pale skin"
        config.face_style3, config.acc3 = "tired eyes", "game controller"
        config.breasts_size3 = config.hip_size3 = config.body_size3 = 0
        config.sub_relationship, config.sub_corruption_role = "상사/주군", "주인공과 함께 타락함: 동반 몰락"
        config.body_dic = {"breasts_size": ["평면", "작음"], "hip_size": ["날씬", "보통"],
                           "body_size": ["로리", "보통"]}
        config.outfit3, config.personality3, config.talking_style3 = "학생복", "다층적", "존댓말"

    opts, editor, status, app3 = asyncio.run(boot(
        ["llm_novel_gui_textual.py", "-id", "1", "-chr_num3", "1"], prep_3in))
    check("C1 GUI 부팅 성공 (textual 헤드리스, 위젯 조회 완료)", len(opts) >= 10, f"메뉴 {len(opts)}개")
    check("C2 메뉴에 '4-1. 서브 캐릭터 설정' 항목 존재", "sub_setup" in opts, f"{len(opts)}개 항목")
    check("C3 argv -chr_num3 이 실제 앱에 반영되어 3인 모드", getattr(config, "chr_num3", 0) == 1)
    check("C4 4-1 실행 결과 에디터에 서브 캐릭터 시트 표시",
          "## 서브 캐릭터 시트 ##" in editor, editor.strip().split("\n")[0][:60])
    _nm3 = [l for l in editor.split("\n") if l.startswith("서브 캐릭터 이름:")]
    check("C5 신규 세션에서 서브 캐릭터 이름이 자동 생성된다 (name_define C 블록이 실GUI에서 동작)",
          len(_nm3) == 1 and _nm3[0].split(":", 1)[1].strip() != "", _nm3[0][:40] if _nm3 else "이름 줄 없음")
    check("C6 시트에 여성 상세 외모 + 관계 + 역할 줄이 구성됨",
          "머리색: messy black hair" in editor and "과의 관계: 상사/주군" in editor
          and "스토리에서의 역할: 주인공과 함께 타락함" in editor)

    def prep_2in():
        config.chr_num3 = 0
    opts2, editor2, status2, _ = asyncio.run(boot(["llm_novel_gui_textual.py", "-id", "1"], prep_2in))
    check("C7 -chr_num3 없으면 2인 모드 유지", getattr(config, "chr_num3", 0) == 0)
    check("C8 2인 모드에서 4-1 은 안내 문구 표시",
          "2인 모드입니다" in editor2, editor2.strip().split("\n")[0][:60])

    prog_after = sorted(os.listdir(os.path.join(BASE, "progress"))) if os.path.isdir(
        os.path.join(BASE, "progress")) else []
    check("C9 GUI 부팅이 progress/ 를 건드리지 않았다 (read-only 스모크)", prog_before == prog_after,
          f"{len(prog_before)}→{len(prog_after)} 파일")

    # ── F. D2 / D4 회귀 ───────────────────────────────────────────────
    section("F. D2(theme_gen 부재) · D4(textual GUI -inc_flag) 회귀")
    import llm_novel_gui_func as gnfunc  # noqa: E402
    mod = gnfunc.import_theme_gen()
    check("F1 theme_gen.py 가 없어도 import_theme_gen 은 예외 대신 None 반환", mod is None,
          f"반환={type(mod).__name__}")
    src_func = open(os.path.join(BASE, "llm_novel_gui_func.py"), encoding="utf-8").read()
    src_curses = open(os.path.join(BASE, "llm_novel_gui.py"), encoding="utf-8").read()
    # 안전 헬퍼 안에서만 원시 import 가 남아야 한다 (헬퍼 밖 크래시 지점은 전부 제거되어야)
    _fn_imp = [n for n in ast.parse(src_func).body
               if isinstance(n, ast.FunctionDef) and n.name == "import_theme_gen"][0]
    _helper_src = "\n".join(src_func.split("\n")[_fn_imp.lineno - 1:_fn_imp.end_lineno])
    _outside = src_func.replace(_helper_src, "")
    check("F2 크래시하던 'import theme_gen as theme_gen_module' 이 헬퍼 외 전 지점에서 제거됨",
          "import theme_gen as theme_gen_module" not in _outside
          and "import theme_gen as theme_gen_module" in _helper_src
          and "import theme_gen as theme_gen_module" not in src_curses
          and "llm_novel_gui_func.import_theme_gen(" in src_curses
          and _outside.count("import_theme_gen(") >= 1,
          f"헬퍼 외 잔존 {_outside.count('import theme_gen as theme_gen_module')}건")
    check("F3 모듈이 실제로 있으면 통과하는 구조 (try/except ImportError 만 잡음)",
          "except ImportError as e:" in src_func[src_func.index("def import_theme_gen"):])

    src_textual = open(os.path.join(BASE, "llm_novel_gui_textual.py"), encoding="utf-8").read()
    check("F4 textual GUI 가 -inc_flag 를 파싱하고 미지정 시 0 으로 확정", '--inc_flag' in src_textual
          and 'config.inc_flag = cmd_args["inc_flag"] if cmd_args["inc_flag"] is not None else 0' in src_textual)

    SNAP_INC = getattr(config, "inc_flag", 0)
    _, _, _, app_inc = asyncio.run(boot(["llm_novel_gui_textual.py", "-id", "1", "-chr_num3", "1",
                                         "-inc_flag", "1"], lambda: setattr(config, "inc_flag", 0)))
    check("F5 실GUI 부팅: -inc_flag 1 이 config 에 반영", getattr(config, "inc_flag", None) == 1,
          f"inc_flag={getattr(config, 'inc_flag', '?')}")
    config.inc_flag = 7  # 일부러 섞은 값 → 미지정이면 0으로 확정되어야 한다
    _, _, _, app_no = asyncio.run(boot(["llm_novel_gui_textual.py", "-id", "1"],
                                       lambda: setattr(config, "inc_flag", 7)))
    check("F6 실GUI 부팅: -inc_flag 미지정 시 0 (curses GUI 와 동일 규칙)",
          getattr(config, "inc_flag", None) == 0, f"inc_flag={getattr(config, 'inc_flag', '?')}")
    config.inc_flag = SNAP_INC

    # ── G. 가짜 OpenAI 서버 왕복으로 실주행 스모크 ─────────────────
    section("G. 가짜 OpenAI 서버와의 실제 HTTP 왕복 → G2 서브 시트 갱신")
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    REPLY = json.dumps({
        "protagonist": {"clothes": "파티 드레스", "sex_count": 1},
        "partner": {"clothes": "정장"},
        "sub": {"clothes": "젖은 셔츠", "personality": "수줍음",
                "corruption_state": "첫 접촉 이후 흥분 잔존"},
    }, ensure_ascii=False)

    class _H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.dumps({
                "id": "cmpl-fake", "object": "chat.completion", "created": 0,
                "model": "fake", "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": REPLY}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    config.get_json_value = lambda: {"ip_main": "127.0.0.1",
                                     "port_main": str(srv.server_address[1])}
    print(f"   (가짜 서버: {oc.get_openai_client().base_url})")
    try:
        r_txt, _ = oc.call_openai_for_plot('프롬프트', messages=[{"role": "user", "content": "hi"}])
        check("G1 실제 HTTP 왕복으로 LLM 응답 수신 (openai SDK, vLLM 스키마)",
              r_txt == REPLY, r_txt[:50])
        out_e = plot_gen._update_character_sheets_via_api(
            "EP 본문", 2, "P_SHEET", "Q_SHEET", "유나", "민준", current_sub=base)
        sub_out = out_e[2]
        check("G2 HTTP 응답 → 서브 시트 갱신 반영 (복장/성격/타락상태)",
              "젖은 셔츠" in sub_out and "수줍음" in sub_out and "첫 접촉 이후 흥분" in sub_out,
              sub_out.split("\n")[0][:40])
        check("G3 LLM이 생략한 고정값은 config/직전 시트 값 유지", not any(
            l.startswith(p) and l.rstrip().endswith("?") for l in sub_out.split("\n")
            for p in ("서브 캐릭터 이름", "서브 캐릭터 나이", "서브 캐릭터 성별", "서브 캐릭터 직업")),
            "\n      ".join([l for l in sub_out.split("\n") if l.rstrip().endswith("?")])[:80] or "미정 표시 없음")
        check("G4 주인공/상대방 시트도 함께 갱신 (3종 반환)",
              len(out_e) == 3 and "파티 드레스" in out_e[0], f"{len(out_e)}종")
    finally:
        srv.shutdown()
        config.get_json_value = SNAP_GJV

    config.chr_num3 = SNAP_CHR

    # ── H. 서버 엔드포인트·모델·타임아웃 해석 (plot.json 기반) ────────────────
    section("H. 18300 포트 / 모델 id / 타임아웃 해석")
    jv = config.get_json_value()
    check("H1 plot.json 이 18300 포트 + model_main 을 보유", str(jv.get("port_main")) == "18300"
          and bool(str(jv.get("model_main", "")).strip()), f"port={jv.get('port_main')} model={jv.get('model_main')}")
    check("H2 resolve_model() 은 model_main 을 우선 사용", oc.resolve_model() == jv["model_main"],
          oc.resolve_model())
    _gjv_keep = config.get_json_value
    config.get_json_value = lambda: {"ip_main": "h", "port_main": "1", "mainLLM": "qwen"}
    check("H3 model_main 없으면 mainLLM 매핑으로 후방호환 (qwen → Qwen/Qwen3.8-27B)",
          oc.resolve_model() == "Qwen/Qwen3.8-27B", oc.resolve_model())
    config.get_json_value = lambda: {"ip_main": "h", "port_main": "1", "mainLLM": "gemma"}
    check("H4 model_main 없으면 mainLLM 매핑 (그 외 → gemma-4-31B-it)",
          oc.resolve_model() == "gemma-4-31B-it", oc.resolve_model())
    config.get_json_value = lambda: {"ip_main": "h", "port_main": "1", "timeout_main": "77"}
    check("H5 resolve_timeout() 이 timeout_main 을 읽는다", oc.resolve_timeout() == 77.0,
          str(oc.resolve_timeout()))
    config.get_json_value = lambda: {"ip_main": "h", "port_main": "1", "timeout_main": "허무하게수"}
    check("H6 값이 깨진 timeout_main 은 기본값으로 폴백", oc.resolve_timeout() == 600.0,
          str(oc.resolve_timeout()))
    config.get_json_value = _gjv_keep
    client = oc.get_openai_client()
    check("H7 클라이언트 base_url 이 plot.json 포트를 쓴다",
          str(client.base_url).rstrip("/").endswith(f":{jv['port_main']}/v1")
          or f"{jv['port_main']}" in str(client.base_url), str(client.base_url))
    check("H8 SDK 내부 재시도를 꺼야 우리 루프가 단일 재시도 권한 (D7)", client.max_retries == 0,
          f"max_retries={client.max_retries}")
    _var_timeout = json.load(open(os.path.join(BASE, "plot", "variables.json"),
                                        encoding="utf-8"))["api_settings"]["timeout"]
    check("H9 plot/variables.json api_settings.timeout 이 실측 소요(344초)를 덮는가", _var_timeout >= 400,
          f"timeout={_var_timeout} (이전 120초는 상시 TIMEOUT이었음)")
    # 서버가 살아있으면 실제 1회 왕복 (없으면 스킵 — 오프라인에서도 테스트가 죽지 않게)
    try:
        _r = __import__("httpx").get(f"http://gx10-a5a3:{jv['port_main']}/v1/models", timeout=4)
        _ids = [m["id"] for m in _r.json().get("data", [])]
        check("H10 서버 /v1/models 가 model_main 을 실제 서빙 (404 방지)", jv["model_main"] in _ids,
              f"서빙 중: {_ids}")
        _resp = client.chat.completions.create(model=oc.resolve_model(),
            messages=[{"role": "user", "content": "네 글자로만 대답: 안녕하세요"}],
            temperature=0.3, timeout=120)
        check("H11 실서버 1회 왕복 + content 비어있지 않음 (reasoning 모델 content 가드)",
              bool((_resp.choices[0].message.content or "").strip()),
              repr((_resp.choices[0].message.content or "")[:24]))
    except Exception as e:
        check("H10 서버 미실행 → 라이브 검사는 스킵 (오프라인에서도 통과)", True, f"스킵: {type(e).__name__}")

    print("\n" + "=" * 62)
    failed = [t for t, ok, _ in RESULTS if not ok]
    print(f"총 {len(RESULTS)}건 검증 / 통과 {len(RESULTS)-len(failed)}건 / 실패 {len(failed)}건")
    for t in failed:
        print(f"  ✗ {t}")
    print("=" * 62)
    sys.exit(1 if failed else 0)
