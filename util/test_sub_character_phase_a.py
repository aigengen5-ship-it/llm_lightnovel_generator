#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[Phase A] 3인자(서브 캐릭터) 도입 검증 테스트

대상 변경 (2026-09-13):
  1. config.py        : Character C 블록 24종 + §3 누락 변수 12종 명시 정의
  2. theme/sub_character.yaml : 서브 캐릭터 데이터 (관계 15 / 타락역할 14)
  3. common_def.py    : name_chg(line, name, name2, name3="") 로 확장
  4. llm_novel_gui_func.py : export_order / theme_auto_vars / reset 보존

실행: (프로젝트 루트에서) /usr/bin/python3 util/test_sub_character_phase_a.py
"""
import os
import sys
import types
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_CONFIG = "/run/media/chrisyeo/AIDATA/AI/LLM/llm_shortnovel_generator_gui/config.py"

# ── 3rd-party 스텁 주입 (이 환경의 system python엔 openai가 없다) ────────────
def _install_stubs():
    try:
        import openai  # noqa: F401
    except ModuleNotFoundError:
        stub = types.ModuleType("openai")

        def _factory(name):
            def _make(*a, **k):
                return types.SimpleNamespace()
            _make.__name__ = name
            return _make

        class _Any:
            def __init__(self, *a, **k):
                pass
            def __getattr__(self, item):
                return _factory(item)()

        stub.__getattr__ = lambda name: _Any()          # PEP 562
        for n in ("OpenAI", "APITimeoutError", "APIStatusError",
                  "BadRequestError", "APIError", "RateLimitError"):
            setattr(stub, n, type(n, (Exception,), {}) if "Error" in n else _Any)
        sys.modules["openai"] = stub


_install_stubs()
sys.path.insert(0, BASE)
os.chdir(BASE)  # config.py가 plot.json / data/episode_setup.json 를 상대경로로 읽는다

import yaml  # noqa: E402
import config  # noqa: E402
import llm_novel_gui_func as fn  # noqa: E402
from common_def import name_chg  # noqa: E402

# ── 검증 대상 변수 목록 ───────────────────────────────────────────────────────
SUB_SHEET_VARS = [
    "chr_num3", "name3", "sex3", "nationality3", "age3", "job3",
    "appearance3", "personality3", "outfit3", "talking_style3",
    "hair_color3", "hair_style3", "eye_color3", "skin_color3",
    "face_style3", "acc3", "breasts_size3", "hip_size3", "body_size3",
    "sub_relationship", "sub_corruption_role", "sub_femboy",
]
SUB_ALL = ["episode_sub_sheets"] + SUB_SHEET_VARS + ["sub_corruption_guides"]
FIXED_VARS = [  # §3: export_order만 참조되고 config에 없던 것들
    "change_awareness", "corruption_flow", "corruption_reason", "resistance_reason",
    "sex_count", "masturbation_count", "patting_count", "normal_sex_count",
    "reverse_sex_count", "cowboy_sex_count", "anal_sex_count", "pose_sex_count",
]

RESULTS = []


def check(title, cond, detail=""):
    RESULTS.append((title, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'} | {title}" + (f"  → {detail}" if detail else ""))


def section(t):
    print(f"\n=== {t} ===")


# ── A. 서브 캐릭터 데이터 파일 ───────────────────────────────────────────────
section("A. theme/sub_character.yaml 스키마")
sub_yaml = os.path.join(BASE, "theme", "sub_character.yaml")
check("A1 데이터 파일 존재", os.path.exists(sub_yaml))
data = yaml.load(open(sub_yaml, encoding="utf-8"), Loader=yaml.FullLoader)
rels, roles = data.get("sub_relationships", []), data.get("sub_corruption_roles", [])
check("A2 sub_relationships 15종", len(rels) == 15, f"{len(rels)}종")
check("A3 sub_corruption_roles 14종", len(roles) == 14, f"{len(roles)}종")
bad_rel = [r.get("label") for r in rels if not r.get("label") or "age_delta" not in r
           or not (isinstance(r.get("gender"), str) or r.get("gender") is None)]
check("A4 관계 항목 스키마(label/gender/age_delta)", not bad_rel, str(bad_rel[:3]))
bad_role = [r.get("name") for r in roles
            if not r.get("name") or not r.get("desc") or not r.get("jinshugai_ids")]
check("A5 역할 항목 스키마(name/desc/jinshugai_ids)", not bad_role, str(bad_role[:3]))
gender_vals = {r.get("gender") for r in rels}
check("A6 gender 값은 남자/여자/None(50:50) 뿐", gender_vals <= {"남자", "여자", None}, str(gender_vals))
# 우리 프로젝트 jinshugai id 커버리지
tt = yaml.load(open(os.path.join(BASE, "theme", "theme_templates.yaml"), encoding="utf-8"),
               Loader=yaml.FullLoader)
our_ids = {t.get("id") for t in tt.get("jinshugai_templates", [])}
covered = set().union(*[set(r.get("jinshugai_ids", [])) for r in roles]) if roles else set()
uncovered = sorted(our_ids - covered)
check("A7 우리 jinshugai id가 모두 서브 역할과 매핑", not uncovered,
      f"우리 id={sorted(our_ids)}, 매핑안됨={uncovered}")
for gid in sorted(our_ids):
    n = sum(1 for r in roles if gid in r.get("jinshugai_ids", []))
    check(f"A8 id={gid} 선택 가능한 서브 역할 수 >= 1", n >= 1, f"{n}종")

# ── B. config 변수 정의 & 타깃과 기본값 parity ───────────────────────────────
section("B. config.py 변수 정의 및 타깃 parity")
for grp, name in ((SUB_ALL, "B1 3인자 변수"), (FIXED_VARS, "B2 §3 누락 변수")):
    miss = [v for v in grp if not hasattr(config, v)]
    check(f"{name} 전부 정의", not miss, f"누락={miss}")

if os.path.exists(TARGET_CONFIG):
    import ast

    def _defaults(path):
        out = {}
        for n in ast.parse(open(path, encoding="utf-8").read()).body:
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        try:
                            out[t.id] = ast.literal_eval(n.value)
                        except Exception:
                            out[t.id] = "<expr>"
        return out
    ours, theirs = _defaults(os.path.join(BASE, "config.py")), _defaults(TARGET_CONFIG)
    diff = [(k, ours.get(k, "<없음>"), theirs.get(k, "<없음>"))
            for k in SUB_ALL if ours.get(k, "<없음>") != theirs.get(k, "<없음>")]
    check("B3 3인자 기본값이 타깃과 완전 일치 (merge divergence 방지)", not diff, str(diff))
else:
    print("  SKIP | B3 타깃 config 없음")

check("B4 chr_num3 기본값 0 (= 2인 모드, 기존 동작 무변경)", config.chr_num3 == 0)
check("B5 corruption_flow 기본값 dict (code가 ['name'] 접근)", isinstance(config.corruption_flow, dict))

# ── C. common_def.name_chg 3인자 확장 ────────────────────────────────────────
section("C. common_def.name_chg")
# [D1 수정 완료] 예전에는 조사 직속 분기가 '이름+조사'가 아니라 조사만 남겼으나(타깃 동일),
#       이제 이름+교정된 조사로 치환된다. 아래 C1b~C1d 가 그 회귀를 고정한다.
s3 = name_chg("[NAME]와 [NAME2]와 [NAME3]가 등장", "유나", "민준", "서빈")
check("C1 name3 지정 시 [NAME3] 치환", "서빈" in s3 and "[NAME3]" not in s3, repr(s3))
check("C1b [D1 수정] 조사 직속 토큰은 '이름 + 올바른 조사'로 남는다 (받침 없음 → 가/를/는/와)",
      name_chg("[NAME]이 간다", "유나", "민준") == "유나가 간다"
      and name_chg("[NAME2]을 봤다", "유나", "민준") == "민준을 봤다", repr(s3))
check("C1c [D1 수정] 받침 있는 이름은 이/을/은/과", name_chg("[NAME]이 [NAME2]을", "서빈", "민준")
      == "서빈이 민준을", repr(name_chg("[NAME]이 [NAME2]을", "서빈", "민준")))
check("C1d [D1 수정] 서브 캐릭터도 동일 (3인자)",
      name_chg("[NAME3]은 왔다", "유나", "민준", "서빈") == "서빈은 왔다"
      and name_chg("[NAME3]은 왔다", "유나", "민준") == "[NAME3]은 왔다")
s2 = name_chg("[NAME]와 [NAME2]가 등장", "유나", "민준")  #기존 positional 3-arg 호출
check("C2 기존 2인자 호출 후방호환 (name3 기본값)", "[NAME" not in s2 and "유나" in s2, repr(s2))
check("C3 name3='' 면 [NAME3] 미포함 시 문장 unchanged",
      name_chg("그저 본문", "유나", "민준") == "그저 본문")
check("C4 받침 유무 조사 파생", name_chg("[NAME3]", "유나", "민준", "서빈") == "서빈")

# ── D. export → restore 왕복 (3인자 전 변수) ─────────────────────────────────
section("D. export_config_to_file / restore_config_from_file 왕복")
SNAPSHOT = {v: getattr(config, v) for v in SUB_ALL + FIXED_VARS}
PROBE = {
    "chr_num3": 1, "name3": "서빈", "sex3": "여자", "nationality3": "일본", "age3": 21,
    "job3": "학생회장", "appearance3": "단아", "personality3": "다층적", "outfit3": "학생복",
    "talking_style3": "존댓말", "hair_color3": "갈색", "hair_style3": "긴 머리",
    "eye_color3": "brown eyes", "skin_color3": "fair skin", "face_style3": "귀여운",
    "acc3": "리본", "breasts_size3": 3, "hip_size3": 2, "body_size3": 1,
    "sub_relationship": "상사/주군", "sub_corruption_role": "주인공과 함께 타락함",
    "sub_femboy": True, "episode_sub_sheets": ["EP1시트", "EP2시트"],
    "sub_corruption_guides": "EP1 가이드",
    "change_awareness": "인지", "corruption_flow": {"name": "n", "desc": "d", "flow": "f"},
    "corruption_reason": "사유", "resistance_reason": "저항", "sex_count": 7,
    "masturbation_count": 3, "patting_count": 2, "normal_sex_count": 4,
    "reverse_sex_count": 5, "cowboy_sex_count": 6, "anal_sex_count": 8, "pose_sex_count": 9,
}
for k, v in PROBE.items():
    setattr(config, k, v)

tmp_yaml = os.path.join(BASE, "log", "_phase_a_export.yaml")
os.makedirs(os.path.dirname(tmp_yaml), exist_ok=True)
msg = fn.export_config_to_file(tmp_yaml)
check("D1 export 성공", "성공" in msg, msg)

saved = yaml.load(open(tmp_yaml, encoding="utf-8"), Loader=yaml.FullLoader)
not_saved = [k for k in PROBE if k not in saved]
check("D2 3인자+§3 변수가 YAML에 실저장", not not_saved, f"누락={not_saved}")

for k in PROBE:
    setattr(config, k, type(SNAPSHOT[k])() if not isinstance(SNAPSHOT[k], (str, int, bool, dict, list)) else SNAPSHOT[k])
msg2 = fn.restore_config_from_file(tmp_yaml)
check("D3 restore 성공", "성공" in msg2, msg2)
lost = [k for k in PROBE if getattr(config, k) != PROBE[k]]
check("D4 restore 후 값 완전 복원", not lost, f"불일치={[(k, getattr(config,k)) for k in lost]}")
check("D5 episode_sub_sheets 리스트 복원", getattr(config, "episode_sub_sheets") == ["EP1시트", "EP2시트"])
check("D6 corruption_flow dict 구조 복원", getattr(config, "corruption_flow", {}).get("flow") == "f")

os.remove(tmp_yaml)

# ── E. export_order ↔ config 정합성 (AGENTS 규칙) ────────────────────────────
section("E. export_order ↔ config.py 정합성")
src = open(os.path.join(BASE, "llm_novel_gui_func.py"), encoding="utf-8").read()
import re
blk = re.search(r"def export_config_to_file.*?export_order = \[(.*?)\]", src, re.S).group(1)
export_order = re.findall(r'"([a-zA-Z_][a-zA-Z0-9_]*)"', blk)
silent = [v for v in export_order if not hasattr(config, v)]
check("E1 export_order 참조 변수가 config.py에 전부 실존 (조용한 누락 0건)", not silent, f"{silent}")
check("E2 export_order 개수", len(export_order) == 141 + len(SUB_ALL),
      f"{len(export_order)}개 (기존 141 + 서브 {len(SUB_ALL)})")
check("E3 서브 변수가 export_order 에 순서보장 포함",
      all(v in export_order for v in SUB_ALL), f"미포함={[v for v in SUB_ALL if v not in export_order]}")

# ── F. 메뉴1 스냅샷(theme_auto_vars)에 서브 변수 포함 ─────────────────────────
section("F. get_theme_auto_updated_vars (메뉴1 스냅샷)")
snap = fn.get_theme_auto_updated_vars()
missing = [v for v in ["chr_num3", "name3", "sex3", "age3", "job3", "sub_relationship",
                       "sub_corruption_role", "sub_femboy", "sub_corruption_guides"]
           if v not in snap]
check("F1 메뉴1 저장 스냅샷에 3인자 항목 포함 (타깃엔 없던 우리 개선)", not missing, f"누락={missing}")

# ── G. reset_config_state 가 chr_num3 를 보존하는지 ───────────────────────────
section("G. reset_config_state 의 chr_num3 보존")
STATE = fn.SAVE_STATE_FILE
backup = STATE + ".phase_a_bak"
existed = os.path.exists(STATE)
if existed:
    shutil.move(STATE, backup)
try:
    config.chr_num3 = 1
    config.name3 = "유지확인"
    fn.reset_config_state()
    check("G1 reload 후 chr_num3=1 유지", getattr(config, "chr_num3") == 1,
          f"chr_num3={getattr(config, 'chr_num3')}")
    check("G2 reload 후 name3는 기본값으로 초기화 (스위치만 보존)",
          getattr(config, "name3") == "", f"name3={getattr(config, 'name3')!r}")
finally:
    if existed:
        shutil.move(backup, STATE)
    elif os.path.exists(backup):
        os.remove(backup)
    for k, v in SNAPSHOT.items():
        setattr(config, k, v)
    config.chr_num3 = 0

# ── 결과 ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
failed = [t for t, ok, _ in RESULTS if not ok]
print(f"총 {len(RESULTS)}건 검증 / 통과 {len(RESULTS)-len(failed)}건 / 실패 {len(failed)}건")
for t in failed:
    print(f"  ✗ {t}")
print("=" * 62)
sys.exit(1 if failed else 0)
