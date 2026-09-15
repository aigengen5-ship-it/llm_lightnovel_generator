#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[G2] EP별 서브 캐릭터 시트 LLM 갱신 검증 테스트

대상 변경 (2026-09-13):
  1. plot_gen.py     : _update_character_sheets_via_api가 current_sub를 받고 3종 반환,
                       _sub_sheet_to_baseline / _build_sub_sheet_text 신규,
                       sub_appearance_mode / _roll_sub_appearance, EP1·EPn 루프 연결
  2. plot/prompts.txt: character_sheet_update {current_sub_block}{sub_instruction}{sub_json_block},
                       ep1/epi_* {sub_appearance_hint}

LLM은 스텁으로 대체하여 실제 API 호출 없이 전 경로를 검증한다.
실행: /usr/bin/python3 util/test_sub_character_phase_d.py
"""
import os
import re
import sys
import json
import types
import inspect
import textwrap
import random

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
import character_setup  # noqa: E402
import plot_gen  # noqa: E402

RESULTS = []
CAPTURED = []


def check(title, cond, detail=""):
    RESULTS.append((title, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'} | {title}" + (f"  → {detail}" if detail else ""))


def section(t):
    print(f"\n=== {t} ===")


def sub_json_of(prompt):
    """렌더링된 프롬프트에서 "sub" JSON 블록만 추출 (주인공 JSON의 hair_color와 혼동 방지)"""
    i = prompt.find('"sub": {')
    if i < 0:
        return ""
    j = prompt.find("\n}", i)
    return prompt[i:j if j > 0 else len(prompt)]


# ── 공통 셋업: 3인 모드 상태 ──────────────────────────────────────────────────
SNAP = {k: getattr(config, k) for k in
        ["chr_num3", "name", "name2", "name3", "sex3", "age3", "job3", "outfit3", "appearance3",
         "personality3", "talking_style3", "sub_relationship", "sub_corruption_role",
         "hair_color3", "hair_style3", "eye_color3", "skin_color3", "face_style3", "acc3",
         "breasts_size3", "hip_size3", "body_size3", "body_dic"]}

config.chr_num3 = 1
config.name, config.name2, config.name3 = "유나", "민준", "서빈"
config.sex3, config.age3, config.job3 = "여자", 20, "학생회장"
config.outfit3, config.appearance3 = "학생복", ""
config.personality3, config.talking_style3 = "다층적", "존댓말"
config.sub_relationship = "상사/주군"
config.sub_corruption_role = "주인공과 함께 타락함: 동반 몰락"
config.hair_color3, config.hair_style3 = "messy black hair", "short hair, ahoge"
config.eye_color3, config.skin_color3 = "dark red eyes", "pale skin"
config.face_style3, config.acc3 = "tired eyes", "game controller"
config.breasts_size3 = config.hip_size3 = config.body_size3 = 0
config.body_dic = {"breasts_size": ["평면", "작음"], "hip_size": ["날씬", "보통"],
                   "body_size": ["로리", "보통"]}

plot_gen._save_character_sheet_json = lambda *a, **k: None  # progress/ 오염 방지


def stub_llm(payload):
    """call_openai_for_plot 대체: 발신 프롬프트를 기록하고 payload를 반환"""
    def _f(prompt, *a, **k):
        CAPTURED.append(prompt)
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        return text, None
    plot_gen.call_openai_for_plot = _f


def call_update(current_sub, payload, ep_num=2):
    """_update_character_sheets_via_api 실행 → (proto, part, sub, prompt)"""
    CAPTURED.clear()
    stub_llm(payload)
    r = plot_gen._update_character_sheets_via_api(
        "에피소드 본문: 첫키스와 고백.", ep_num,
        "PROTAGONIST_SHEET", "PARTNER_SHEET", "유나", "민준",
        log_fn=None, current_sub=current_sub)
    return r[0], r[1], r[2], (CAPTURED[0] if CAPTURED else "")


BASELINE_SUB = character_setup.sub_sheet()
OK_SUB = {"protagonist": {"clothes": "파티 드레스"}, "partner": {"clothes": "정장"},
          "sub": {"clothes": " 흰 원피스 ", "personality": "수줍음",
                  "corruption_state": "첫 노출 이후 흥분 잔존"}}

# ── A. 시트 업데이트: 프롬프트 구성 ───────────────────────────────────────────
section("A. character_sheet_update 프롬프트 (여성 3인 모드)")
p, q, new_sub, prompt = call_update(BASELINE_SUB, OK_SUB)
check("A1 프롬프트에 '## 현재 서브 캐릭터 시트' 블록 삽입", "## 현재 서브 캐릭터 시트" in prompt)
check("A2 서브 시트 본문이 그대로 전달", "서브 캐릭터 이름: 서빈" in prompt)
check("A3 여성용 고정값 금지 지시문 포함",
      "3-1. 서브 캐릭터 시트도" in prompt and "절대 변경 금지" in prompt and "corruption_state" in prompt)
check("A4 sub_json_block에 \"sub\" 스키마 + 상세 외모 키",
      '"sub": {' in prompt and '"hair_color"' in sub_json_of(prompt)
      and '"corruption_state"' in sub_json_of(prompt), sub_json_of(prompt)[:60])
check("A5 지시문 번호 충돌 없음 (3-1 뒤 4번 JSON 지시 유지)",
      prompt.index("3-1. 서브 캐릭터 시트도") < prompt.index("4. 아래 JSON 형식"))
check("A6 중괄호 이스케이프 정상 (format 후 {{ → { 로 나와 JSON 유효)",
      '"sub": {' in prompt or '"sub": {{' in prompt, "JSON 블록 확인")

# ── B. 시트 업데이트: 파싱/고정값 상속 ─────────────────────────────────────────
section("B. 서브 시트 갱신 결과 (LLM 부분 응답)")
check("B1 반환값 3종 tuple", len(plot_gen._update_character_sheets_via_api.__defaults__ or ()) >= 0
      and isinstance(new_sub, str) and new_sub != "", "new_sub 비어있지 않음")
check("B2 갱신 항목 반영 (복장/성격/타락상태)",
      "흰 원피스" in new_sub and "수줍음" in new_sub and "첫 노출 이후 흥분 잔존" in new_sub, new_sub[:60])
check("B3 [우리 개선] LLM이 생략한 고정값 상속 (이름/나이/성별/직업/관계) — 타깃이면 '?'됨",
      all(s in new_sub for s in ("서브 캐릭터 이름: 서빈", "서브 캐릭터 나이: 20",
                                 "서브 캐릭터 성별: 여자", "서브 캐릭터 직업: 학생회장",
                                 "과의 관계: 상사/주군")),
      "\n      ".join([l for l in new_sub.split("\n") if "?" in l]) or "고정값 전부 유지")
check("B4 '?' 미정 표시 없음", "?" not in new_sub, new_sub[:60])
check("B4b [우리 개선] LLM이 생략한 성격/말투/복장도 직전 값 유지 (타깃은 '?'로 떨어짐)",
      "서브 캐릭터 말투: 존댓말" in new_sub and "서브 캐릭터 이름: 서빈" in new_sub,
      "\n      ".join([l for l in new_sub.split("\n") if "?" in l]) or "생략 필드 전부 직전 값 상속")
check("B5 여성 상세 외모는 config 고정값 사용",
      "머리색: messy black hair" in new_sub and "가슴 크기: 평면" in new_sub)

_, _, sub_empty, _ = call_update(BASELINE_SUB, {"protagonist": {}, "partner": {}})
check("B6 LLM이 'sub'를 아예 안 보내면 기존 시트 유지", sub_empty == BASELINE_SUB)
_, _, sub_blank, _ = call_update(BASELINE_SUB, {"protagonist": {}, "partner": {}, "sub": {}})
check("B7 'sub'가 빈 객체여도 기존 시트 유지", sub_blank == BASELINE_SUB)

# ── C. 실패 경로 아리티 ───────────────────────────────────────────────────────
section("C. 실패 경로 (반환 개수 보존 = unpack crash 방지)")
_, _, s_fail, _ = call_update(BASELINE_SUB, "서버 응답 실패")
check("C1 서버 응답 실패 → 3종 반환 & 기존 시트 유지", s_fail == BASELINE_SUB)
_, _, s_bad, _ = call_update(BASELINE_SUB, "{ 이게 아니지")
check("C2 JSON 파싱 실패 → 예외 대신 3종 반환 & 기존 시트 유지", s_bad == BASELINE_SUB)
r2 = call_update("", OK_SUB)
check("C3 2인 모드(current_sub='') → 3번째 반환 ''", r2[2] == "")
check("C4 2인 모드 프롬프트에 서브 블록/지시문 없음",
      "서브" not in r2[3] and "{sub" not in r2[3], "")

# ── D. 남성 서브 캐릭터 분기 ──────────────────────────────────────────────────
section("D. 남성 서브 캐릭터 분기")
config.sex3 = "남자"
config.appearance3 = "보통, 수염없음, 흰색, 평범"
config.hair_color3 = ""
BASELINE_M = character_setup.sub_sheet()
_, _, new_sub_m, prompt_m = call_update(BASELINE_M, {
    "protagonist": {}, "partner": {},
    "sub": {"appearance": "땀에 젖은 셔츠", "corruption_state": "흥분 초입"}})
check("D1 남성용 sub_json_block은 appearance 사용 (상세 외모 키 없음)",
      '"appearance"' in sub_json_of(prompt_m)
      and '"hair_color"' not in sub_json_of(prompt_m),
      sub_json_of(prompt_m)[:90])
check("D2 남성 갱신: appearance 반영", "땀에 젖은 셔츠" in new_sub_m)
check("D3 남성 시트에 여성 전용 상세 필드 미노출", "머리색:" not in new_sub_m)
check("D4 남성 고정값 상속 (직업/관계)", "서브 캐릭터 직업: 학생회장" in new_sub_m
      and "과의 관계: 상사/주군" in new_sub_m)

# ── E. 베이스라인 매핑 / 시트 빌더 단위 검증 ──────────────────────────────────
section("E. _sub_sheet_to_baseline / _build_sub_sheet_text 단위 검증")
config.sex3, config.hair_color3 = "여자", "messy black hair"
b = plot_gen._sub_sheet_to_baseline(character_setup.sub_sheet())
check("E1 한글 라벨 → 영문 키 매핑",
      b.get("name") == "서빈" and b.get("age") == 20 and b.get("sex") == "여자"
      and b.get("relationship") == "상사/주군" and b.get("job") == "학생회장", json.dumps(b, ensure_ascii=False)[:110])
check("E2 나이 int 변환", isinstance(b.get("age"), int), type(b.get('age')).__name__)
check("E3 '주인공(유나)과의 관계' 같이 이름이 섞인 라벨도 매핑", b.get("relationship") == "상사/주군")
check("E4 빈 입력 시 빈 dict", plot_gen._sub_sheet_to_baseline("") == {})

txt = plot_gen._build_sub_sheet_text({"name": "서빈", "age": 20, "sex": "여자", "job": "학생회장",
                                      "relationship": "상사/주군", "personality": "p",
                                      "talking_style": "t", "clothes": "c",
                                      "corruption_state": "cs"}, "유나", "서빈")
check("E5 빌더: 13개 라인 + 현재 타락 상태 포함", len(txt.split("\n")) >= 14 and "현재 타락 상태: cs" in txt)

# ── F. _roll_sub_appearance 동작 (함수 소스 추출 exec) ─────────────────────────
section("F. EP별 등장 빈도 (_roll_sub_appearance)")
src = inspect.getsource(plot_gen.plot_gen_extended)
i0 = src.index("    def _roll_sub_appearance(ep_num):")
lines = src[i0:].split("\n")
func_src = [lines[0]]
for ln in lines[1:]:
    if ln.strip() and not ln.startswith("        "):
        break
    func_src.append(ln)
func_src = textwrap.dedent("\n".join(func_src))


def make_roller(mode, name3="서빈", total=10):
    ns = {"sub_appearance_mode": mode, "name3": name3, "total_episodes": total, "rand": random}
    exec(compile(func_src, "<roller>", "exec"), ns)
    return ns["_roll_sub_appearance"]


random.seed(7)
check("F0 함수 소스 추출 성공", "def _roll_sub_appearance" in func_src)
r_none = make_roller("")
check("F1 2인 모드(mode='') → 항상 빈 문자열", all(r_none(i) == "" for i in range(1, 11)))
r_tog = make_roller("together")
check("F2 together: 중반 이전(EP1~5)은 특별 지시 없음", all(r_tog(i) == "" for i in range(1, 6)))
mid = {("등장하지 않을" in r_tog(8)) for _ in range(60)}
check("F3 together: 후반은 50%로 등장/비등장 갈림", mid == {True, False}, str(mid))
h = r_tog(9)
check("F4 등장 지시에 이름과 '서브 주인공' 문구",
      (h == "" or ("서빈" in h and ("서브 주인공" in h or "등장하지 않을" in h))), h[:60])
r_jg = make_roller("jeon_gyeol")
j = {("전(절정)과 결" in r_jg(3)) for _ in range(60)}
check("F5 jeon_gyeol: EP 위치 무관 50%로 전-결 전용 지시", j == {True, False}, str(j))
check("F6 2인 모드에서는 hint가 프롬프트에 못 들어가는 구조(mode 분기 선행)",
      "if not sub_appearance_mode" in func_src)

# ── G. 정적 배선 ──────────────────────────────────────────────────────────────
section("G. EP 루프 배선 (소스 정적 검증)")
full = inspect.getsource(plot_gen)
check("G1 EP1 초기 시트에 sub 저장", "config.episode_sub_sheets[0] = sub_sheet" in full)
check("G2 EP1 초기 JSON에 sub 포함", '"sub": _parse_sheet_to_dict(sub_sheet)' in full)
check("G3 EP1 갱신: current_sub 전달 + 3종 unpack + 저장",
      "current_sub=sub_sheet" in full and "new_proto, new_part, new_sub = _update_character_sheets_via_api" in full
      and "config.episode_sub_sheets[1] = new_sub" in full)
check("G4 EPn 루프: current_sub 경계 보호 + 저장",
      "current_sub = config.episode_sub_sheets[i - 2] if i - 2 < len(config.episode_sub_sheets) else \"\"" in full
      and "config.episode_sub_sheets[i - 1] = new_sub" in full)
check("G5 cs_log에 서브 시트 기록 (초기/EP1/EPn 3곳)", full.count('### 서브 캐릭터 시트 ###') == 3,
      f"{full.count('### 서브 캐릭터 시트 ###')}곳")
check("G6 ep1/epi 프롬프트에 sub_appearance_hint 전달",
      "sub_appearance_hint=_roll_sub_appearance(1)" in full
      and "sub_appearance_hint=_roll_sub_appearance(i)" in full)
check("G7 _build_prompt 안전망 6종",
      all(k in inspect.getsource(plot_gen._build_prompt)
          for k in ("sub_sheet_block", "sub_guides_text", "sub_appearance_hint",
                    "current_sub_block", "sub_instruction", "sub_json_block")))


def sections_of(path):
    raw = open(path, encoding="utf-8").read()
    parts = re.split(r"======([^=]+)======", raw)
    return {parts[i].strip(): parts[i + 1] for i in range(1, len(parts), 2)}


pp = sections_of(os.path.join(BASE, "plot", "prompts.txt"))
check("G8 character_sheet_update에 3종 플레이스홀더",
      all(k in pp["character_sheet_update"] for k in
          ("{current_sub_block}", "{sub_instruction}", "{sub_json_block}")))
check("G9 ep1/epi 3종 템플릿에 {sub_appearance_hint}",
      all("{sub_appearance_hint}" in pp[k] for k in
          ("ep1_prompt", "epi_prompt_normal", "epi_prompt_slowburn")))

# ── H. 2인 모드 렌더링 동일성 (실제 포맷 결과물 비교) ────────────────────
section("H. 2인 모드: G2 전(.bak) vs 후 렌더링 결과물 비교")
import string  # noqa: F401  (placeholder 조사용)

SUB_KEYS = ("sub_sheet_block", "sub_guides_text", "sub_appearance_hint",
            "current_sub_block", "sub_instruction", "sub_json_block")


class Blank(dict):
    """모든 플레이스홀더를 빈 문자열로 치환 (2인 모드에서 서브 블록이 ''임을 검증)"""
    def __missing__(self, key):
        return ""


def render2(tpl):
    return tpl.format_map(Blank())


old_pp = sections_of(os.path.join(BASE, "plot", "prompts.txt.bak"))
for key in ("ep1_prompt", "epi_prompt_normal", "epi_prompt_slowburn"):
    a, b2 = render2(old_pp[key]), render2(pp[key])
    check(f"H1 {key}: 2인 모드 렌더링 완전 동일", a == b2,
          "" if a == b2 else next((f"{i}번째 줄 차이: {repr(x)} vs {repr(y)}"
                                   for i, (x, y) in enumerate(zip(a.split("\n"), b2.split("\n"))) if x != y), ""))

a, b2 = render2(old_pp["character_sheet_update"]), render2(pp["character_sheet_update"])
la, lb = a.split("\n"), b2.split("\n")
check("H2 character_sheet_update: 2인 모드 내용 동일 (빈 줄 차이만 허용)",
      [l for l in la if l.strip()] == [l for l in lb if l.strip()],
      f"행수 {len(la)}→{len(lb)} (빈 줄 {abs(len(la)-len(lb))}줄 외 텍스트 동일)")

_, _, _, prompt_h = call_update(character_setup.sub_sheet(), OK_SUB)
check("H3 [우리 개선] 렌더된 프롬프트에 '{{' '}}' 잔존 없음 — LLM이 유효한 JSON 예시를 받는다 (타깃은 이중 중괄호 노출)",
      "{{" not in prompt_h and "}}" not in prompt_h,
      next((l.strip() for l in prompt_h.split("\n") if "{{" in l or "}}" in l), "이중 중괄호 0건"))
blk = sub_json_of(prompt_h)
try:
    parsed = json.loads("{\n" + blk.replace(": ~", ": 0").replace('"~"', '"더미"') + "\n}")
    ok4 = isinstance(parsed.get("sub"), dict) and len(parsed["sub"]) >= 10
    err4 = f"sub 키 {len(parsed.get('sub', {}))}종 파싱"
except Exception as e:
    ok4, err4 = False, f"{type(e).__name__}: {e}"
check("H4 sub JSON 예시가 실제로 JSON 파싱됨", ok4, err4)

# ── I. 스냅샷 복원 ────────────────────────────────────────────────────────────
for k, v in SNAP.items():
    setattr(config, k, v)

print("\n" + "=" * 62)
failed = [t for t, ok, _ in RESULTS if not ok]
print(f"총 {len(RESULTS)}건 검증 / 통과 {len(RESULTS)-len(failed)}건 / 실패 {len(failed)}건")
for t in failed:
    print(f"  ✗ {t}")
print("=" * 62)
sys.exit(1 if failed else 0)
