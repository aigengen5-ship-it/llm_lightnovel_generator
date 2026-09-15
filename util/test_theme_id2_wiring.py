#!/usr/bin/env python3
"""
[20260914] theme_templates id=2(삼각관계) 코드 배선 기능 검증

LLM 호출이 필요한 theme_gen_auto_step1() 은 쓰지 않고,
step1/step3-1-1 에서 실제로 호출되는 함수만 짚어서 확인한다.
  1) _select_sub_corruption_role(roles, jinshugai_id=2) → '삼각관계 연적' 역할이 나오는가
  2) 템플릿 require_sub_character / sub_relationship_labels / sub_character_hint 배선 소스 확인
  3) _build_sub_character_block() 이 hint 를 반영한 역할 텍스트를 프롬프트에 넣는가
  4) full_episode_gen 시점 분기가 id=2 를 러브코미디(상대방 1인칭)으로 보는가

실행: (프로젝트 루트에서) source ./select_python.sh && $PYTHON_BIN util/test_theme_id2_wiring.py
"""
import os
import sys

import yaml

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE)

import config                      # noqa: E402
import theme_gen_auto              # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))


tpl_yaml = yaml.safe_load(open(os.path.join(BASE, "theme", "theme_templates.yaml"), encoding="utf-8"))
TPL2 = next(t for t in tpl_yaml["jinshugai_templates"] if t.get("id") == 2)

# ---------------------------------------------------------------- 1) 역할 매칭
sub_data = theme_gen_auto._load_sub_character()
role2 = theme_gen_auto._select_sub_corruption_role(sub_data["sub_corruption_roles"], 2)
check("01 id=2 → '삼각관계 연적' 역할 선택", "삼각관계 연적" in role2, role2[:48])
check("02 id=2 역할에 결말 구속문(endings) 포함", "endings" in role2)
dark = [w for w in ("조교", "인질", "고기방패", "세뇌") if w in role2]
check("03 id=2 에서 다크(NTR/조교) 역할이 나오지 않음", not dark, ", ".join(dark))

# id=1 / 다른 id 는 기존 역할 풀을 그대로 쓰는가 (회귀 방지)
r1 = theme_gen_auto._select_sub_corruption_role(sub_data["sub_corruption_roles"], 1)
check("04 id=1 은 기존 역할 유지(회귀 없음)", "삼각관계 연적" not in r1, r1[:32])
for i in (3, 4, 5, 6, 7, 8, 9, 10, 11):
    theme_gen_auto._select_sub_corruption_role(sub_data["sub_corruption_roles"], i)
check("05 다른 jinshugai id 역할 선택 정상 동작", True)

# ------------------------------------------------- 2) 관계 라벨 필터(연적 우선)
labels = TPL2.get("sub_relationship_labels", [])
rels = sub_data["sub_relationships"]
wanted = [r["label"] for r in rels if any(w in r["label"] for w in labels)]
check("06 sub_relationship_labels 가 실제 관계 라벨과 매칭", bool(wanted), f"{len(wanted)}개: {wanted}")
check("07 연적 관계는 여자 고정(하렘 결말 정합성)",
      any(r["label"].startswith("연적") and r["gender"] == "여자" for r in rels))
sex3, age3 = theme_gen_auto._derive_sub_gender_age(
    next(r for r in rels if r["label"].startswith("연적")), 24)
check("08 연적 관계에서 성별/나이 파생", sex3 == "여자" and 18 <= age3 <= 60, f"{sex3}/{age3}세")

# -------------------------------------------------------- 3) 3인자 블록 주입
config.chr_num3 = 1
config.name3, config.job3, config.sex3, config.age3 = "아야세 루나", "카페 아르바이트생", "여자", 22
config.sub_relationship = "연적 (진슈가이 소속 애정공세형)"
config.sub_corruption_role = role2 + f" (템플릿 지정 성향: {TPL2.get('sub_character_hint', '')})"
config.hair_color3 = "messy black hair"; config.hair_style3 = "short hair"; config.eye_color3 = "dark red eyes"
config.skin_color3 = "pale skin"; config.face_style3 = "tired eyes"; config.acc3 = "gaming headset"
config.breasts_size3 = 0; config.hip_size3 = 0; config.body_size3 = 0
config.outfit3 = "캐주얼"; config.talking_style3 = "천박하게 말함"; config.personality3 = "착함"
config.name, config.name2 = "유이나", "켄"
blk = theme_gen_auto._build_sub_character_block()
check("09 _build_sub_character_block 이 3인자 블록 생성", "서브 캐릭터 (3인자)" in blk)
check("10 블록에 연적 관계가 표기", "연적" in blk)
check("11 블록에 템플릿 hint(천박/음탕/진슈가이) 가 포함",
      all(w in blk for w in ("천박", "음탕", "진슈가이")))
check("12 말투에 천박이 들어가 있음", "천박" in blk)

# ------------------------------------------- 4) 소스 배선 (step1/3-1-1/pov)
src = open(os.path.join(BASE, "theme_gen_auto.py"), encoding="utf-8").read()
check("13 step1 에 require_sub_character → chr_num3 강제 배선",
      'template_setting.get("require_sub_character")' in src and "config.chr_num3 = 1" in src)
check("14 step3-1-1 에 sub_relationship_labels 필터 배선",
      'template_setting.get("sub_relationship_labels", [])' in src)
check("15 step3-1-1 에 sub_character_hint append 배선",
      'template_setting.get("sub_character_hint", "")' in src
      and "템플릿 지정 성향" in src)
fep = open(os.path.join(BASE, "full_episode_gen.py"), encoding="utf-8").read()
check("16 pov 분기 id=2 포함", "jinshugai_id in (1, 2)" in fep)

# actions.yaml id=2
act = yaml.safe_load(open(os.path.join(BASE, "theme", "actions.yaml"), encoding="utf-8"))
ph = act.get(2, {})
check("17 actions.yaml id=2 Phase1~3", all(p in ph and ph[p] for p in (1, 2, 3)),
      str({p: len(v) for p, v in ph.items()}))
sel = theme_gen_auto._select_actions_for_phase(act, 2, 1, 5)
check("18 _select_actions_for_phase(id=2, Phase1, 5) 동작", len(sel) == 5, f"{len(sel)}개")
for p, n in ((2, 3), (3, 2)):
    check(f"19 Phase{p} 선택 동작", len(theme_gen_auto._select_actions_for_phase(act, 2, p, n)) == n)

fail = 0
print("=" * 78)
for name, ok, detail in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   [{detail}]" if detail else ""))
    fail += 0 if ok else 1
print("=" * 78)
print(f"  {len(results) - fail}/{len(results)} PASS, {fail} FAIL")
sys.exit(1 if fail else 0)
