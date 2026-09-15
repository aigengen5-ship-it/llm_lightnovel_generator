#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[G1] theme_update 단계의 서브 캐릭터 필드 최적화 검증 테스트

대상 변경 (2026-09-13):
  1. theme/prompts.txt : theme_update_prompt 에 {sub_info_block} / {sub_update_items} / {sub_json_block}
  2. theme_gen_auto.py : _update_theme_template_with_llm 이 서브 3종 블록을 프롬프트에 넣고
                         응답의 sub_relationship / sub_corruption_role 을 파싱,
                         호출부가 config 에 'LLM이 실제로 바꾼 필드만' 반영
                         (함께 이식: config.intro/crisis/ending_actions blanket 동기화 제거 = G1b)

LLM 은 스텁으로 대체하여 실제 API 호출 없이 전 경로를 검증한다.
실행: /usr/bin/python3 util/test_sub_character_phase_f.py
"""
import json
import os
import re
import sys
import types

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
        for n in ("OpenAI", "APITimeoutError", "APIStatusError", "APIConnectionError"):
            setattr(stub, n, type(n, (Exception,), {}) if "Error" in n else _Any)
        sys.modules["openai"] = stub


_install_stubs()
sys.path.insert(0, BASE)
os.chdir(BASE)

import config  # noqa: E402
import theme_gen_auto as tga  # noqa: E402

RESULTS = []
CAPTURED = []


def check(title, cond, detail=""):
    RESULTS.append((title, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'} | {title}" + (f"  → {detail}" if detail else ""))


def section(t):
    print(f"\n=== {t} ===")


SNAP = {k: getattr(config, k) for k in
        ["chr_num3", "name", "name2", "name3", "job3", "sub_relationship", "sub_corruption_role",
         "inc_flag", "first_event", "second_event", "resistance_reason", "corruption_reason"]}

config.chr_num3 = 1
config.name, config.name2, config.name3 = "유나", "민준", "서빈"
config.job3 = "학생회장"
config.sub_relationship = "상사/주군"
config.sub_corruption_role = "주인공과 함께 타락함: 동반 몰락"
config.inc_flag = 0

TEMPLATE = {"id": 1, "name": "학원 메가데레", "concept": "설렘과 질투의 학원 생활"}
SELECTED = {
    "first_event": "우연한 접촉", "second_event": "비밀의 목격",
    "first_trigger": "손을 잡음", "second_trigger": "머리를 쓰다듬음",
    "intermediate_phase": ["A", "B"], "daily_corruption_changes": ["C", "D"],
    "selected_ending": "함께 몰락", "selected_resistance": "동생 때문", "selected_corruption_reason": "질투",
    "selected_relationship": "상사와 비서",
    "intro_location": {"name": "도서실", "desc": "저녁의 도서실"},
    "crisis_location": {"name": "옥상", "desc": "비 오는 옥상"},
    "ending_location": {"name": "졸업식장", "desc": "빈 강당"},
    "intro_actions": ["책을 함께 읽기"], "crisis_actions": ["비를 함께 맞기"],
    "ending_actions": ["손을 잡기"],
}
PROMPTS = tga._load_prompts()


def call_update(payload, selected=None, chr_num3=1):
    """_update_theme_template_with_llm 실행 → (updated_values, 발신 프롬프트)"""
    def _stub(prompt, *a, **k):
        CAPTURED.append(prompt)
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        return text, None
    old_chr = config.chr_num3
    config.chr_num3 = chr_num3
    tga.call_openai_for_plot = _stub
    sel = dict(selected or SELECTED)
    # 실제 호출부(theme_gen_auto_step2)와 동일하게 selected_values 에 서브 필드를 주입한다
    if chr_num3 == 1:
        sel["sub_relationship"] = config.sub_relationship
        sel["sub_corruption_role"] = config.sub_corruption_role
    CAPTURED.clear()
    try:
        uv = tga._update_theme_template_with_llm(TEMPLATE, "회사원", "비서", PROMPTS,
                                                 sel, log_fn=None)
    finally:
        config.chr_num3 = old_chr
    return uv, (CAPTURED[0] if CAPTURED else "")


# ── A. 프롬프트 구성 (3인 모드) ───────────────────────────────────────────────
section("A. theme_update 프롬프트에 서브 캐릭터 주입 (chr_num3=1)")
OK_PAYLOAD = {"first_event": "우연한 접촉(수정)", "sub_relationship": "상사/비서 (밀애)",
              "sub_corruption_role": "주인공과 함께 타락함: 질투의 삼각관계"}
uv, pr = call_update(OK_PAYLOAD)
check("A1 '## 서브 캐릭터 정보' 블록 삽입", "## 서브 캐릭터 정보" in pr)
check("A2 이름/직업/관계/역할 4줄이 실제 값으로 전달",
      all(f"* {k}" in pr for k in ("이름: 서빈", "서브 캐릭터 직업: 학생회장",
                                   "주인공(유나)과의 관계: 상사/주군",
                                   "스토리에서의 역할: 주인공과 함께 타락함: 동반 몰락")))
check("A3 블록 위치가 '상대방 정보' 뒤·'둘 사이의 관계' 앞",
      pr.find("* 상대방 직업:") < pr.find("## 서브 캐릭터 정보") < pr.find("## 둘 사이의 관계"))
check("A4 수정 항목 14·15 추가 (13번 뒤, 출력형식 앞)",
      all(x in pr for x in ("14. 서브 캐릭터 관계 (sub_relationship, 1개)",
                            "15. 서브 캐릭터 스토리 역할 (sub_corruption_role, 1개)"))
      and pr.find("13. 결 행동") < pr.find("14. 서브 캐릭터 관계") < pr.find("**출력 형식**"))
check("A5 관계의 본질/역할의 본질 유지 지시", pr.count("본질은 유지할 것") == 2)
check("A6 JSON 스키마에 sub 2필드 (ending_actions 뒤)",
      '"sub_relationship": "수정된 서브 캐릭터 관계"' in pr
      and '"sub_corruption_role": "수정된 서브 캐릭터 스토리 역할"' in pr
      and pr.find('"ending_actions"') < pr.find('"sub_relationship"'))
check("A7(format 후에도) 이중 중괄호 잔존 없음", "{{" not in pr and "}}" not in pr,
      next((l.strip() for l in pr.split("\n") if "{{" in l or "}}" in l), "0건"))

# ── B. 응답 파싱 ─────────────────────────────────────────────────────────────
section("B. LLM 응답 파싱 → updated_values 반영")
check("B1 sub_relationship 반영", uv.get("sub_relationship") == "상사/비서 (밀애)",
      str(uv.get("sub_relationship"))[:40])
check("B2 sub_corruption_role 반영", "질투의 삼각관계" in str(uv.get("sub_corruption_role")))
check("B3 기존 필드(first_event)도 정상 반영", uv.get("first_event") == "우연한 접촉(수정)")
check("B4 미반환 필드는 원본 유지", uv.get("selected_ending") == "함께 몰락")

fenced = "설명 텍스트\n```json\n" + json.dumps({"sub_relationship": "상사/주군 (수정)"},
                                              ensure_ascii=False) + "\n```\n맺음말"
uv2, _ = call_update(fenced)
check("B5 ```json 펜스/설명 섞인 응답도 파싱", uv2.get("sub_relationship") == "상사/주군 (수정)")
uv3, _ = call_update({"first_event": "X"})
check("B6 응답에 sub 키 없으면 원본 유지", uv3.get("sub_relationship") == "상사/주군"
      and uv3.get("sub_corruption_role") == "주인공과 함께 타락함: 동반 몰락")
BASELINE = dict(SELECTED, sub_relationship=config.sub_relationship,
               sub_corruption_role=config.sub_corruption_role)
uv4, _ = call_update("{파싱불가")
check("B7 파싱 실패 시 selected_values 그대로", uv4 == BASELINE)
uv5, pr5 = call_update(OK_PAYLOAD, chr_num3=0)
check("B8 2인 모드면 응답에 sub 키가 있어도 반영 안 함",
      "sub_relationship" not in uv5 and uv5.get("selected_ending") == "함께 몰락")

# ── C. 2인 모드 무해성 ───────────────────────────────────────────────────────
section("C. 2인 모드: G1 전(.bak) 프롬프트와 렌더링 비교")
check("C1 2인 모드 프롬프트에 '서브' 문구 자체가 없음", "서브" not in pr5,
      next((l.strip() for l in pr5.split("\n") if "서브" in l), "0건"))


def sections_of(path):
    raw = open(path, encoding="utf-8").read()
    parts = re.split(r"======([^=]+)======", raw)
    return {parts[i].strip(): parts[i + 1] for i in range(1, len(parts), 2)}


class Blank(dict):
    def __missing__(self, key):
        return ""


new_tpl = sections_of(os.path.join(BASE, "theme", "prompts.txt"))["theme_update_prompt"]
old_tpl = sections_of(os.path.join(BASE, "theme", "prompts.txt.bak"))["theme_update_prompt"]
a, b = old_tpl.format_map(Blank()), new_tpl.format_map(Blank())
check("C2 서브 플레이스홀더를 비우면 G1 전 템플릿과 완전 일치 (2인 모드 무영향)", a == b,
      "" if a == b else next((f"{i}번째 줄 {x!r} vs {y!r}" for i, (x, y)
                              in enumerate(zip(a.split("\n"), b.split("\n"))) if x != y), ""))
check("C3 신규 플레이스홀더는 서브 전용 3종뿐",
      set(re.findall(r"\{(\w+)\}", new_tpl)) - set(re.findall(r"\{(\w+)\}", old_tpl))
      == {"sub_info_block", "sub_update_items", "sub_json_block"})
src = open(os.path.join(BASE, "theme_gen_auto.py"), encoding="utf-8").read()
net = src[src.index("def _build_prompt"):src.index("def _load_yaml") if "def _load_yaml" in src
          else src.index("def _build_prompt") + 900]
check("C4 _build_prompt 안전망이 7종으로 확장",
      all(k in net for k in ("sub_character_block", "sub_guide_block", "sub_count_text",
                             "sub_review_block", "sub_info_block", "sub_update_items",
                             "sub_json_block")))

# ── D. 호출부 배선 ───────────────────────────────────────────────────────────
section("D. 호출부(theme_gen_auto_step2) 배선")
import ast  # noqa: E402
_tree = ast.parse(src)
_fn = [n for n in _tree.body if isinstance(n, ast.FunctionDef)
       and n.name == "theme_gen_auto_step2"][0]
step2 = "\n".join(src.split("\n")[_fn.lineno - 1:_fn.end_lineno])
check("D0 step2 함수 소스 추출 성공 (호출부 포함)", "_update_theme_template_with_llm(" in step2,
      f"{step2.count(chr(10))+1}줄")
check("D1 selected_values 에 서브 2필드 주입 (chr_num3 분기)",
      'selected_values["sub_relationship"] = config.sub_relationship' in step2
      and 'selected_values["sub_corruption_role"] = config.sub_corruption_role' in step2)
check("D2 config 반영이 '실제로 바뀐 필드만' 갱신 (1/2번 메뉴 수정값 덮어쓰기 방지)",
      'if updated_values["first_event"] != selected_values["first_event"]:' in step2
      and 'if updated_values.get("sub_relationship") != selected_values.get("sub_relationship"):' in step2)
# theme_update 이전의 초기 동기화(1회)는 남기고, 갱신 블록 안의 blanket 동기화만 제거되어야 한다
check("D3 theme_update 갱신 블록에서 intro/crisis/ending_actions blanket 동기화 제거 (G1b)",
      step2.count("config.intro_actions = intro_actions") == 1
      and step2.count("config.crisis_actions = crisis_actions") == 1
      and step2.count("config.ending_actions = ending_actions") == 1
      and "[G1b]" in step2,
      f"intro {step2.count('config.intro_actions = intro_actions')}회 (초기 1회만 기대)")
check("D4 theme_update 호출이 서브 블록 사용보다 앞 (갱신값이 가이드로 전파)",
      step2.index("_update_theme_template_with_llm(") < step2.index("_build_sub_guide_block("))

for k, v in SNAP.items():
    setattr(config, k, v)

print("\n" + "=" * 62)
failed = [t for t, ok, _ in RESULTS if not ok]
print(f"총 {len(RESULTS)}건 검증 / 통과 {len(RESULTS)-len(failed)}건 / 실패 {len(failed)}건")
for t in failed:
    print(f"  ✗ {t}")
print("=" * 62)
sys.exit(1 if failed else 0)
