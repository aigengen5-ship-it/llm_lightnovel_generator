#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[Phase B] 3인자(서브 캐릭터) 생성 파이프라인 배선 검증 테스트

대상 변경 (2026-09-13):
  1. theme/elements.yaml   : partner_appearance / sub_character_appearance 이식
  2. theme/prompts.txt     : {sub_character_block} {sub_guide_block} {sub_count_text} {sub_review_block}
  3. theme_gen_auto.py     : 서브 헬퍼 7종 + Step 3-1-1 + 가이드 파싱 3축화
  4. character_setup.py    : name_define(name3) / sub_sheet() / sub_size_text()
  5. plot_gen.py           : episode_sub_sheets / ep_corruption_guides_map["sub"] / name2 병기
  6. story_gen.py          : plot_result 서브 문장 / _replace_names(NAME3)
  7. full_episode_gen.py   : EP별 서브 시트 주입 / _get_random_gyeol_pov
  8. episode/prompts.txt   : part1_ki {sub_sheet_block}
  9. episode/variables.json: pov_gyeol_sub

실행: /usr/bin/python3 util/test_sub_character_phase_b.py
"""
import os
import re
import sys
import types
import random
import inspect

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
        for n in ("OpenAI", "APITimeoutError", "APIStatusError",
                  "BadRequestError", "APIError", "RateLimitError"):
            setattr(stub, n, type(n, (Exception,), {}) if "Error" in n else _Any)
        sys.modules["openai"] = stub


_install_stubs()
sys.path.insert(0, BASE)
os.chdir(BASE)

import yaml  # noqa: E402
import config  # noqa: E402
import theme_gen_auto  # noqa: E402
import character_setup  # noqa: E402
import story_gen  # noqa: E402
import full_episode_gen  # noqa: E402
import plot_gen  # noqa: E402

SUB_PH = {"sub_character_block", "sub_guide_block", "sub_count_text", "sub_review_block",
          "sub_sheet_block", "sub_guides_text",
          "sub_appearance_hint", "current_sub_block", "sub_instruction", "sub_json_block",
          "sub_info_block", "sub_update_items"}
SHEET_PH = {"sub_character_block", "sub_guide_block", "sub_count_text", "sub_review_block"}

RESULTS = []


def check(title, cond, detail=""):
    RESULTS.append((title, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'} | {title}" + (f"  → {detail}" if detail else ""))


def section(t):
    print(f"\n=== {t} ===")


def sections_of(path):
    raw = open(path, encoding="utf-8").read()
    parts = re.split(r"======([^=]+)======", raw)
    out = {}
    for i in range(1, len(parts), 2):
        out[parts[i].strip()] = parts[i + 1]
    return out


def norm(text):
    """플레이스홀더 제거 + 빈 줄 정규화 (2인 모드 프롬프트 동일성 비교용)"""
    for ph in SUB_PH:
        text = text.replace("{" + ph + "}", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


# ── A. 프롬프트 파일: 신규 플레이스홀더 & 2인 모드 무변경 ─────────────────────
section("A. 프롬프트 템플릿 (신규 placeholder / 2인 모드 동일성)")
for fname, allowed in (("theme/prompts.txt", SHEET_PH | {"sub_info_block", "sub_update_items", "sub_json_block"}),
                       ("plot/prompts.txt", {"sub_sheet_block", "sub_guides_text",
                                             "sub_appearance_hint", "current_sub_block",
                                             "sub_instruction", "sub_json_block"}),
                       ("episode/prompts.txt", {"sub_sheet_block"})):
    new_p = os.path.join(BASE, fname)
    bak_p = new_p + ".bak"
    if not os.path.exists(bak_p):
        print(f"  SKIP | {fname} .bak 없음")
        continue
    new_s, old_s = sections_of(new_p), sections_of(bak_p)
    check(f"A1 {fname} 섹션 구성 유지", set(new_s) >= set(old_s),
          f"사라진 섹션={set(old_s) - set(new_s)}")
    added = {}
    for k in old_s:
        ph_new = set(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", new_s.get(k, "")))
        ph_old = set(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", old_s[k]))
        if ph_new - ph_old:
            added[k] = ph_new - ph_old
    unknown = {k: (v - allowed) for k, v in added.items() if v - allowed}
    check(f"A2 {fname} 신규 placeholder는 3인자 전용만", not unknown,
          f"추가={added} / 예상외={unknown or '없음'}")
    diff_sec = [k for k in old_s if k in new_s and norm(new_s[k]) != norm(old_s[k])]
    check(f"A3 {fname} 플레이스홀더 제거 시 기존과 동일 (2인 모드 무영향)", not diff_sec,
          f"차이={diff_sec[:3]}")

# ── B. _build_prompt 안전망 ───────────────────────────────────────────────────
section("B. _build_prompt 안전망 (미전달 시 KeyError/종료 방지)")
src_tga = inspect.getsource(theme_gen_auto._build_prompt)
check("B1 theme_gen_auto._build_prompt setdefault 4종",
      all(p in src_tga for p in SHEET_PH), "")
check("B2 plot_gen._build_prompt setdefault", "sub_sheet_block" in inspect.getsource(plot_gen._build_prompt))
check("B3 full_episode_gen._build_prompt setdefault",
      "sub_sheet_block" in inspect.getsource(full_episode_gen._build_prompt))
try:
    plot_gen._build_prompt("A{sub_sheet_block}B")
    ok = True
except Exception as e:
    ok = False
check("B5 plot_gen._build_prompt가 kwargs 없이도 통과", ok)
try:
    full_episode_gen._build_prompt("A{sub_sheet_block}B")
    ok = True
except Exception:
    ok = False
check("B6 full_episode_gen._build_prompt가 kwargs 없이도 통과", ok)

# ── C. theme_gen_auto 서브 헬퍼 ───────────────────────────────────────────────
section("C. theme_gen_auto 서브 헬퍼")
for fn in ("_load_sub_character", "_select_sub_corruption_role", "_derive_sub_gender_age",
           "_build_sub_character_block", "_build_sub_guide_block", "_build_sub_count_text",
           "_build_sub_review_block"):
    check(f"C0 {fn} 존재", hasattr(theme_gen_auto, fn))

SNAP = {k: getattr(config, k) for k in
        ["chr_num3", "name", "name2", "name3", "sex3", "age3", "job3", "outfit3", "appearance3",
         "personality3", "talking_style3", "sub_relationship", "sub_corruption_role",
         "hair_color3", "hair_style3", "eye_color3", "skin_color3", "face_style3", "acc3",
         "breasts_size3", "hip_size3", "body_size3"]}


def set_3p():
    config.chr_num3 = 1
    config.name, config.name2, config.name3 = "유나", "민준", "서빈"
    config.sex3, config.age3, config.job3 = "여자", 20, "학생회장"
    config.outfit3, config.appearance3 = "학생복", ""
    config.personality3, config.talking_style3 = "다층적", "존댓말"
    config.sub_relationship, config.sub_corruption_role = "상사/주군", "주인공과 함께 타락함"
    config.hair_color3, config.hair_style3 = "messy black hair", "short hair, ahoge, unkempt"
    config.eye_color3, config.skin_color3 = "dark red eyes", "pale skin"
    config.face_style3, config.acc3 = "tired eyes", "game controller"
    config.breasts_size3, config.hip_size3, config.body_size3 = 0, 0, 0


config.chr_num3 = 0
empty = [theme_gen_auto._build_sub_character_block(), theme_gen_auto._build_sub_guide_block(),
         theme_gen_auto._build_sub_count_text(5), theme_gen_auto._build_sub_review_block()]
check("C1 chr_num3=0 이면 4개 블록 모두 빈 문자열 (2인 모드)", all(b == "" for b in empty), repr(empty))

set_3p()
blk = theme_gen_auto._build_sub_character_block()
check("C2 chr_num3=1 정보 블록에 이름/관계/역할/직업 포함",
      all(s in blk for s in ("서빈", "학생회장", "상사/주군", "주인공과 함께 타락함", "3인자")), "")
check("C3 정보 블록에 중괄호 없음 (str.format 삽입 안전)", "{" not in blk and "}" not in blk)
gb = theme_gen_auto._build_sub_guide_block()
check("C4 가이드 블록에 [서브캐릭터 가이드: 서빈] 헤더", "[서브캐릭터 가이드: 서빈]" in gb, "")
check("C5 가이드 블록에 중괄호 없음", "{" not in gb and "}" not in gb)
check("C6 개수 텍스트 형식", theme_gen_auto._build_sub_count_text(7) == ", 서브캐릭터 7개")
rb = theme_gen_auto._build_sub_review_block()
check("C7 리뷰 블록에 개수/관계/역할 질문 3줄", rb.count("\n* ") >= 3 and "서빈" in rb)

# 가이드 블록에 이름이 들어가면 안 되는 항목: 가이드 개수 변수 혼입 방지
check("C8 가이드 블록이 protagonist 헤더를 침범하지 않음", "[주인공 가이드" not in gb)

# ── D. 데이터 로더 / 역할 선택 / 나이 파생 ───────────────────────────────────
section("D. 데이터 로더·역할 선택·나이 파생")
sub_data = theme_gen_auto._load_sub_character()
rels, roles = sub_data["sub_relationships"], sub_data["sub_corruption_roles"]


def _check_str_rel():
    """'이름: 설명' 단일 key dict / 순수 문자열 역할도 text로 승격되는지 (하위 호환)"""
    orig = theme_gen_auto._load_theme_yaml
    try:
        theme_gen_auto._load_theme_yaml = lambda fn: {
            "sub_relationships": ["가족 (여동생)", {"label": "소꿉친구", "gender": None}],
            "sub_corruption_roles": ["순수 문자열 역할", {"이름": "설명"},
                                     {"name": "역할A", "desc": "설명A", "jinshugai_ids": [1]}],
        }
        d = theme_gen_auto._load_sub_character()
    finally:
        theme_gen_auto._load_theme_yaml = orig
    r0, r1 = d["sub_relationships"][0], d["sub_relationships"][1]
    ok_rel = (r0["label"] == "가족 (여동생)" and r0["gender"] is None
              and r0["age_delta"] == [-2, 2] and r0["job_sync"] is False
              and r1["label"] == "소꿉친구" and r1["age_delta"] == [-2, 2])
    ts = [x["text"] for x in d["sub_corruption_roles"]]
    ok_role = (ts[0] == "순수 문자열 역할" and ts[1] == "이름: 설명"
               and ts[2] == "역할A: 설명A"
               and d["sub_corruption_roles"][2]["jinshugai_ids"] == [1])
    return ok_rel and ok_role


check("D1 관계 15종 정규화(label/gender/age_delta/job_sync)",
      len(rels) == 15 and all({"label", "gender", "age_delta", "job_sync"} <= set(r) for r in rels))
check("D2 역할 14종 정규화(text/jinshugai_ids)",
      len(roles) == 14 and all({"text", "jinshugai_ids"} <= set(r) for r in roles))
check("D3 문자열 관계 항목도 dict로 승격 (하위 호환)", _check_str_rel())

random.seed(11)
picked = theme_gen_auto._select_sub_corruption_role(roles, 1)
id1 = [r["text"] for r in roles if 1 in r["jinshugai_ids"]]
check("D4 jinshugai id=1 → id=1 역할풀에서만 선택", picked in id1, f"{len(id1)}종 중 선택")
logs = []
picked2 = theme_gen_auto._select_sub_corruption_role(roles, 999, log_fn=logs.append)
check("D5 매칭 없는 id → 전체 랜덤 폴백 + 로그", picked2 in [r["text"] for r in roles] and logs,
      logs[0][:48] if logs else "로그 없음")

sx, ag = theme_gen_auto._derive_sub_gender_age({"gender": "여자", "age_delta": [-6, -1]}, 25)
check("D6 gender 고정 존중", sx == "여자")
check("D7 age_delta 반영 (19~24)", 19 <= ag <= 24, f"age3={ag}")
seen = {theme_gen_auto._derive_sub_gender_age({"gender": None, "age_delta": [0, 0]}, 30)[0]
        for _ in range(200)}
check("D8 gender null → 50/50 랜덤 (양쪽 모두 출현)", seen == {"남자", "여자"}, str(seen))
check("D9 상한 clamp 60", theme_gen_auto._derive_sub_gender_age({"gender": None, "age_delta": [18, 25]}, 55)[1] == 60)
check("D10 하한 clamp 18", theme_gen_auto._derive_sub_gender_age({"gender": None, "age_delta": [-6, -1]}, 19)[1] == 18)

# ── E. elements.yaml 서브 외모 데이터 ─────────────────────────────────────────
section("E. elements.yaml 서브 캐릭터 데이터")
el = yaml.load(open(os.path.join(BASE, "theme", "elements.yaml"), encoding="utf-8"), Loader=yaml.FullLoader)
sp = el.get("sub_character_appearance", {})
need_f = {"hair_color", "hair_style", "eye_color", "skin_color", "face_style", "accessory",
          "breasts_size", "hip_size", "body_size"}
need_m = {"appearance", "appearance_femboy", "talking_style", "talking_style_femboy",
          "personality", "outfit", "outfit_femboy"}
check("E1 female 필드 완비", need_f <= set(sp.get("female", {})), str(need_f - set(sp.get("female", {}))))
check("E2 male 필드 완비", need_m <= set(sp.get("male", {})), str(need_m - set(sp.get("male", {}))))
check("E3 partner_appearance 말투/성격 풀 존재",
      bool(el.get("partner_appearance", {}).get("talking_styles")) and
      bool(el.get("partner_appearance", {}).get("personalities")))

# ── F. character_setup ───────────────────────────────────────────────────────
section("F. character_setup (서브 시트 / 이름 생성)")
config.body_dic = {"breasts_size": ["평면", "작음", "보통"], "hip_size": ["날씬", "보통"],
                   "body_size": ["로리", "보통"]}
check("F1 sub_size_text 정상 인덱스", character_setup.sub_size_text("breasts_size", 1) == "작음")
check("F2 sub_size_text -1 → 미설정", character_setup.sub_size_text("breasts_size", -1) == "미설정")
check("F3 sub_size_text 범위 초과 → 미설정", character_setup.sub_size_text("breasts_size", 99) == "미설정")

sh = character_setup.sub_sheet()
check("F4 sub_sheet: 이름/나이/성별/직업/관계/역할",
      all(s in sh for s in ("서빈", "20", "여자", "학생회장", "상사/주군", "주인공과 함께 타락함")))
check("F5 sub_sheet(여성): 상세 외모 필드 사용", "머리색: messy black hair" in sh and "가슴 크기: 평면" in sh, "")
config.sex3 = "남자"
config.appearance3 = "보통, 수염없음, 흰색, 평범"
sh_m = character_setup.sub_sheet()
check("F6 sub_sheet(남성): appearance3 사용 & 상세 필드 미노출",
      "서브 캐릭터 외모: 보통, 수염없음, 흰색, 평범" in sh_m and "머리색:" not in sh_m)

config.chr_num3 = 0
config.name3 = ""
config.nationality3 = ""
character_setup.name_define()
check("F7 chr_num3=0 → name_define가 name3를 건드리지 않음", config.name3 == "" and config.nationality3 == "")
set_3p()
config.name3, config.nationality3 = "", ""
character_setup.name_define()
check("F8 chr_num3=1 → name3 생성 및 국적 japanese",
      bool(config.name3) and config.nationality3 == "japanese", f"name3={config.name3}")
config.sex3 = "남자"
config.name3, config.nationality3 = "", ""
character_setup.name_define()
check("F9 sex3=남자 → male 이름 풀 사용 (non-empty)", bool(config.name3), f"name3={config.name3}")

# ── G. story_gen / full_episode_gen ──────────────────────────────────────────
section("G. story_gen / full_episode_gen")
set_3p()
config.chr_num3 = 1
out = story_gen._replace_names("NAME1, NAME2, NAME3가 만났다")
check("G1 _replace_names가 NAME3를 [NAME3]→name3로 치환", "서빈" in out and "NAME3" not in out, repr(out))
config.chr_num3 = 0
out2 = story_gen._replace_names("NAME1과 NAME2가 NAME3 만났다")
check("G2 chr_num3=0면 NAME3는 원문 그대로 (미변환) & NAME2만 치환",
      "NAME3" in out2 and "민준" in out2 and "[NAME" not in out2, repr(out2))
check("G2b 이름 단독 출현은 정상 치환", story_gen._replace_names("NAME1 등장") == "유나 등장",
      repr(story_gen._replace_names("NAME1 등장")))
# [D1 수정 완료] name_chg 의 조사 직속 분기가 이름을 버리던 결함(타깃 동일)을 고쳤다.
#            이제 '이름 + 교정된 조사'가 남아야 한다 (받침 없는 '유나' → 가).
r_d1 = story_gen._replace_names("NAME1이 간다")
check("G2c [D1 수정] 조사 직속 [NAME]은 이름+교정 조사로 남는다",
      r_d1 == "유나가 간다", repr(r_d1))

config.chr_num3 = 1
r_d1b = story_gen._replace_names("NAME3을 보고 NAME1은 웃었다")
check("G2d [D1 수정] 3인 모드에서 서브 목적격/주인공 주제격도 이름+조사로 치환",
      r_d1b == "서빈을 보고 유나는 웃었다", repr(r_d1b))
povs = {full_episode_gen._get_random_gyeol_pov("유나", "민준", "서빈") for _ in range(120)}
check("G3 _get_random_gyeol_pov가 3화자 모두 출력", len(povs) == 3, f"{len(povs)}종")
check("G4 서브 화자에 name3 및 시점 스위칭 지시",
      any("서빈" in p and "시점 스위칭" in p for p in povs))
src_feg = inspect.getsource(full_episode_gen)
check("G5 chr_num3=0이면 기존 _get_pov_template 경로 유지",
      '_get_random_gyeol_pov' in src_feg and "chr_num3', 0) == 1" in src_feg)

# ── H. 정적 배선 검증 (LLM 호출부까지 이어졌는가) ─────────────────────────────
section("H. 파이프라인 배선 (소스 정적 검증)")
s1 = inspect.getsource(theme_gen_auto.theme_gen_auto_step1)
check("H1 step1에 Step 3-1-1 배선", "3-1-1" in s1 and "_derive_sub_gender_age" in s1 and "sub_character_appearance" in s1)
check("H2 step1에서 job3 펨보이화/job_sync 처리",
      "job_sync" in s1 and "sub_femboy" in s1 and "펨보이화" in s1)
s2 = inspect.getsource(theme_gen_auto.theme_gen_auto_step2)
check("H3 step2 가이드 파싱 3축(section_order)", "section_order" in s2 and '"sub"' in s2)
check("H4 step2에서 sub_corruption_guides 대입 + EP 그룹 보정",
      "config.sub_corruption_guides" in s2 and "sub_guides = _adjust_guides_by_group" in s2)
check("H5 step2 리뷰/수정 프롬프트에 서브 블록 전달",
      "_build_sub_review_block" in s2 and "_build_sub_guide_block" in s2)
check("H6 step2 단계별 프롬프트에 서브 블록/개수 전달",
      s2.count("_build_sub_character_block()") >= 3 and s2.count("_build_sub_count_text(") >= 3)
spg = inspect.getsource(plot_gen.plot_gen_extended)
check("H7 plot_gen: episode_sub_sheets 초기화 + name2 병기",
      "episode_sub_sheets = [sub_sheet]" in spg and 'name2 = f"{name2},{name3}"' in spg)
check("H8 plot_gen: ep_corruption_guides_map 3축 + sub 가이드 루프",
      '"sub": []' in spg and 'ep_corruption_guides_map[ep_assign]["sub"].append(guide)' in spg)
check("H9 plot_gen: EP 가이드 문구에 서브캐릭터 라인", spg.count("서브캐릭터 가이드") >= 2)
check("H10 plot_gen: master_setup에 sub_sheet_block 전달",
      "sub_sheet_block=" in spg)
ssg = inspect.getsource(story_gen.generate_plot)
check("H11 story_gen.generate_plot에 서브 캐릭터 문장", "chr_num3" in ssg and "sub_relationship" in ssg)
check("H12 full_episode_gen: EP별 서브 시트 선택 + part1_ki 주입",
      "episode_sub_sheets" in src_feg and "sub_sheet_block=" in src_feg)

# pov_gyeol_sub / part1_ki 템플릿
ev = __import__("json").load(open(os.path.join(BASE, "episode", "variables.json"), encoding="utf-8"))
check("H13 episode/variables.json pov_gyeol_sub 존재 & name3 플레이스홀더",
      "pov_gyeol_sub" in ev and "{name3}" in ev["pov_gyeol_sub"])
ep = sections_of(os.path.join(BASE, "episode", "prompts.txt"))
check("H14 episode/prompts.txt part1_ki에 {sub_sheet_block}", "{sub_sheet_block}" in ep["part1_ki"])
tpp = sections_of(os.path.join(BASE, "theme", "prompts.txt"))
check("H15 theme/prompts.txt 4단계(intro/crisis/ending/review) 주입",
      all("{sub_character_block}" in tpp[k] for k in ("introduction_prompt", "crisis_guides_prompt", "ending_guides_prompt"))
      and "{sub_review_block}" in tpp["review_prompt"])

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
