#!/usr/bin/env python3
"""
[20260914] theme_templates.yaml id=2 '삼각관계' 개편 검증기

theme_gen_auto.py 의 실제 선택 로직(random.choice / random.sample 2~3개)을 그대로 흉내내서,
id=2 템플릿이 '삼각관계'를 항상 유지할 수 있는지 검사한다.

실행:
  /usr/bin/python3 util/test_theme_id2_triangle.py                 # 실파일 검증
  /usr/bin/python3 util/test_theme_id2_triangle.py order/20260914_theme_id2_triangle_candidate.yaml
"""
import os
import re
import sys
import random
import collections

import yaml

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TARGET = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "theme", "theme_templates.yaml")

# 삼각관계 어휘 — 모든 항목에 최소 1개는 들어 있어야 "1개 골라도 삼각관계"가 성립한다.
RIVAL_KW = ["서브 주인공", "연적", "경쟁", "질투", "열폭", "제3자", "다른 여자",
            "진슈가이", "예절 교양원", "두 여자", " rival", "라이벌"]

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))


def main():
    print(f"[TARGET] {TARGET}")
    data = yaml.safe_load(open(TARGET, encoding="utf-8"))
    tpls = data if isinstance(data, list) else data["jinshugai_templates"]
    t2 = next((t for t in tpls if t.get("id") == 2), None)
    check("01 id=2 템플릿 존재", t2 is not None)
    if t2 is None:
        report()
        return

    t1 = next((t for t in tpls if t.get("id") == 1), {})

    # ---- 1) id=1 복붙 잔재 검사 -------------------------------------------------
    NARRATIVE = ("first_event", "second_event", "first_triggers", "second_triggers",
                 "intermediate_phase", "daily_corruption_changes", "corruption_reasons",
                 "resistance_reasons", "endings")
    dup = []
    for k, v in t2.items():
        if k in NARRATIVE and isinstance(v, list) and isinstance(t1.get(k), list):
            if set(v) & set(t1[k]):
                dup.append(f"{k}({len(set(v) & set(t1[k]))}개)")
    check("02 id=1 과 중복된 항목 없음", not dup, " / ".join(dup))

    # ---- 2) 요구사항 커버리지 --------------------------------------------------
    concept = t2.get("concept", "") + t2.get("import_point", "")
    check("03 요구사항1 삼각관계/경쟁(concept)", "경쟁" in concept and "삼각관계" in concept)
    check("04 요구사항2 하렘물 남주(concept)", "하렘" in concept)
    check("05 요구사항3 서브캐 천박/음탕/진슈가이(concept)",
          all(w in concept for w in ("천박", "음탕", "진슈가이")),
          concept[:60])
    check("06 요구사항4 주인공 빔보화(concept)", "빔보" in concept)
    check("07 요구사항5 결말 2개(하렘/단애)",
          len(t2.get("endings", [])) >= 2
          and any("하렘" in e for e in t2["endings"])
          and any(("단애" in e or "완승" in e or "백기" in e) for e in t2["endings"]),
          f"endings={len(t2.get('endings', []))}")

    # ---- 3) '1개만 선택되는' 필드: 전 항목이 삼각관계여야 함 ---------------------
    for key in ("first_event", "second_event", "first_triggers", "second_triggers"):
        items = t2.get(key, [])
        miss = [i[:30] for i in items if not any(w in i for w in RIVAL_KW)]
        check(f"08 {key} 전 항목이 삼각관계 ({len(items)}개)", items and not miss,
              "누락: " + ", ".join(miss) if miss else "")

    # ---- 4) '2~3개 샘플' 필드: 항목이 독립적이어야 함(상호참조 금지) -------------
    for key in ("intermediate_phase", "daily_corruption_changes"):
        items = t2.get(key, [])
        check(f"09 {key} 3개 이상", len(items) >= 3, f"{len(items)}개")
        ref = [i[:30] for i in items if re.search(r"위 |앞 |항목|마찬가지|같은 양식", i)]
        check(f"10 {key} 상호참조 없음", not ref, ", ".join(ref))
        miss = [i[:30] for i in items if not any(w in i for w in RIVAL_KW)]
        check(f"11 {key} 전 항목 삼각관계", not miss, "누락: " + ", ".join(miss))

    # ---- 5) 저항#타락 페어 정합성 ---------------------------------------------
    res = t2.get("resistance_reasons", [])
    paired = [r for r in res if "#" in r]
    check("12 resistance_reasons 존재", bool(res), f"{len(res)}개")
    for r in paired:
        a, b = r.split("#", 1)
        check("13 저항#타락 양쪽 모두 내용", a.strip() and b.strip(), r[:40])

    # ---- 6) 코드 배선 점검 ----------------------------------------------------
    check("14 require_sub_character: true (chr_num3 강제)",
          t2.get("require_sub_character") is True)
    check("15 name 이 id=1 과 구분됨", t2.get("name") != t1.get("name"), t2.get("name", ""))

    # 중괄호 → str.format 프롬프트 주입 안전성
    braces = [f"{k}:{i[:20]}" for k, v in t2.items() if isinstance(v, list)
              for i in v if "{" in i or "}" in i]
    check("16 항목 텍스트에 중괄호 없음(format 안전)", not braces, ", ".join(braces))

    # 1000회 랜덤 드로우 (theme_gen_auto 선택 로직 재현)
    try:
        for _ in range(1000):
            random.choice(t2["first_event"])
            random.choice(t2["second_event"])
            random.choice(t2["first_triggers"])
            random.choice(t2["second_triggers"])
            random.choice(t2["endings"])
            random.sample(t2["intermediate_phase"],
                          min(random.randint(2, 3), len(t2["intermediate_phase"])))
            random.sample(t2["daily_corruption_changes"],
                          min(random.randint(2, 3), len(t2["daily_corruption_changes"])))
        check("17 1000회 랜덤 선택 시뮬레이션", True)
    except Exception as e:
        check("17 1000회 랜덤 선택 시뮬레이션", False, repr(e))

    # ---- 7) 관련 파일 배선 ----------------------------------------------------
    sub = yaml.safe_load(open(os.path.join(BASE, "theme", "sub_character.yaml"), encoding="utf-8"))
    def _rtext(r):
        return f"{r.get('name', '')}: {r.get('desc', '')}"
    roles = [r for r in sub.get("sub_corruption_roles", []) if 2 in r.get("jinshugai_ids", [])]
    light = [_rtext(r)[:24] for r in roles
             if any(w in _rtext(r) for w in ("연적", "경쟁", "라이벌"))]
    check("18 sub_character.yaml 에 id=2 전용(연적/경쟁) 역할 있음", bool(light),
          f"id2 매칭 {len(roles)}개 / 경합형 {len(light)}개")

    act = yaml.safe_load(open(os.path.join(BASE, "theme", "actions.yaml"), encoding="utf-8"))
    ph = act.get(2, {}) or {}
    check("19 actions.yaml id=2 Phase1~3 있음", all(p in ph for p in (1, 2, 3)),
          f"phase={ {p: len(v) for p, v in ph.items()} }" if ph else "id=2 없음")

    src = open(os.path.join(BASE, "full_episode_gen.py"), encoding="utf-8").read()
    check("20 full_episode_gen pov 분기가 id=2 도 러브코미디 시점 사용",
          "jinshugai_id in (1, 2)" in src or "jinshugai_id == 2" in src)

    report()


def report():
    fail = 0
    print("\n" + "=" * 78)
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   [{detail}]" if detail else ""))
        fail += 0 if ok else 1
    print("=" * 78)
    print(f"  {len(results) - fail}/{len(results)} PASS, {fail} FAIL")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
