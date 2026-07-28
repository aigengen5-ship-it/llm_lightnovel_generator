"""
ANIMA용 시각 태그 생성기
rp.py의 get_visual_tags, get_body_anatomy_tags, get_random_expression만 추출.
클래스 없이 순수 함수로 재구성.

3D 페르소나 생성기 통합:
  Loveness = a, Lewdness = l, Corruption = m 매핑
  face_generate(): 애정 x 천박 x 타락 3D 페르소나 기반 face/expression 문장 생성
"""

import logging
import random
import config

# face_generate 전용 logger
_face_logger = logging.getLogger("face_generate")
_face_logger.setLevel(logging.DEBUG)
if not _face_logger.handlers:
    _fh = logging.FileHandler("face_generate.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    _face_logger.addHandler(_fh)


# ====================================================================
# 3D Persona Face Generator (애정 x 천박 x 타락)
# ====================================================================

def face_generate(m, l, a, o, i, s, d, gender=0, style=0):
    """
    3D 페르소나 기반 face/expression 태그 생성.
    Loveness=a, Lewdness=l, Corruption=m 매핑.

    Args:
        m, l, a, o, i, s, d: 도덕성, 음란도, 호감도, 복종도, 지성, 수치심, 주도권 (0-5)
        gender: 0=female, 1=male
        style: 0=LN, 1=WAN

    Returns:
        face/expression 문장 (영문)
    """
    # --- 상태별 emotion/makeup 풀 (3D 페르소나: hate/pure/lewd/corrupted/corrupted_lewd) ---
    # 기존 makeup 태그 통합:
    #   female: no_makeup, pale_lips, lipgloss, light_cheek, pink_lips, mascara,
    #           dark_lips, heavy_eye_makeup, red_lips, dark_contour,
    #           black_lips, dark_eyeshadow
    #   male: clean_face, light_blush, eyeliner, rosy_cheeks, heavy_makeup,
    #         pink_lips, heavy_contour, red_lips, black_lips, dark_eyeshadow
    #   corruption: eyeshadow, red_lips, eyeliner, dark_eyeshadow, facial_mark,
    #               glowing_tattoo_on_face, heavy_eyeliner, black_lips
    #   조건부: light_sweat, oily_skin_texture, sweat_drops
    pools = {
        # 1. 혐오/무관심 (Loveness < 3)
        "hate": {
            "emotion": ["glaring", "disgust", "scowl", "cold stare", "angry", "annoyed", "frown", "crying", "teary eyes"],
            "makeup": [
                "natural makeup", "minimal makeup", "no makeup", "pale lips",
                "clean face", "light blush", "rosy cheeks", ""
            ]
        },
        # 2. 순애 (Loveness >= 3 / Lewd < 3 / Corr < 3)
        "pure": {
            "emotion": ["gentle smile", "happy", "pure blush", "loving look", "cheerful", "soft expression", "teary smile", "crying with joy"],
            "makeup": [
                "light makeup", "subtle lip gloss", "clear skin", "no makeup",
                "pale lips", "lipgloss", "light cheek", "pink lips", "mascara",
                ""
            ]
        },
        # 3. 천박/음탕 (Loveness >= 3 / Lewd >= 3 / Corr < 3)
        "lewd": {
            "emotion": ["ahegao", "torogao", "heavy blush", "lustful", "dazed", "bimbo aura", "gyaru vibe", "crying with pleasure", "tearing up"],
            "makeup": [
                "gyaru makeup", "heavy makeup", "glossy pink lips", "thick mascara",
                "fake lashes", "messy makeup", "pink lips", "mascara",
                "dark lips", "heavy eye makeup", "red lips", "dark contour",
                "eyeliner", "heavy contour", "light blush", "rosy cheeks"
            ]
        },
        # 4. 악의 타락 (Loveness >= 3 / Lewd < 3 / Corr >= 3)
        "corrupted": {
            "emotion": ["sadistic smile", "dark persona", "evil smile", "arrogant smirk", "seductive", "dominant look", "crying silently", "teary gaze"],
            "makeup": [
                "evil female executive makeup", "dark makeup", "dark lipstick",
                "purple eyeshadow", "sharp winged eyeliner", "eyeshadow",
                "red lips", "eyeliner", "dark eyeshadow", "facial mark",
                "glowing tattoo on face", "heavy eyeliner", "black lips",
                "dark lips", "heavy eye makeup", "dark contour"
            ]
        },
        # 5. 타락한 천박함 (Loveness >= 3 / Lewd >= 3 / Corr >= 3)
        "corrupted_lewd": {
            "emotion": ["twisted ahegao", "corrupted lust", "crazed smile", "mind break", "insane love", "crying with ecstasy", "tearful ahegao"],
            "makeup": [
                "smudged dark lipstick", "ruined dark makeup", "heavy dark eyeshadow",
                "glossy dark lips", "black lips", "dark eyeshadow",
                "glowing tattoo on face", "heavy eyeliner", "dark lips",
                "heavy eye makeup", "red lips", "dark contour",
                "messy makeup", "facial mark"
            ]
        }
    }

    # --- 조건부 makeup 추가 (style, 수치심 기반) ---
    conditional_makeup = []
    if s >= 4 and l < 3:
        conditional_makeup.append("light sweat")
    if style == 1:
        conditional_makeup.extend(["oily skin texture", "sweat drops"])
    if conditional_makeup:
        for state_key in pools:
            pools[state_key]["makeup"].extend(conditional_makeup)

    # --- 눈 상태 풀 (anima_express.py 통합: L 기반 open/half/closed) ---
    eyes_pool = {
        "low": {
            "open": ["clear eyes", "staring eyes", "wide eyes", "sharp eyes", "lifeless eyes",
                      "narrowed eyes", "disdainful eyes"],
            "half": ["half-closed eyes", "calm eyes", "resting eyes"],
            "closed": ["eyes closed", "peaceful eyes closed", "wincing"]
        },
        "mid": {
            "open": ["sparkling eyes", "upturned eyes", "wet eyes", "looking up",
                      "seductive eyes", "sharp predatory gaze", "piercing eyes"],
            "half": ["bedroom eyes", "seductive stare", "heavy eyelids", "half-closed eyes",
                     "glazed eyes"],
            "closed": ["eyes closed tight", "trembling eyelids", "winking"]
        },
        "high": {
            "open": ["rolling eyes", "heart-shaped pupils", "crossed eyes", "crazed eyes",
                      "dilated pupils", "unfocused eyes", "tearing up",
                      "heart-shaped pupils mixed with a dark glare", "predatory yet unfocused eyes"],
            "half": ["white eyes", "glazed eyes", "rolling eyes", "heart-shaped pupils",
                     "half-closed eyes"],
            "closed": ["eyes closed tight", "squeezed eyes", "crying with eyes closed"]
        }
    }

    # --- 입 상태 풀 (anima_express.py 통합: H 기반 closed/open) ---
    mouth_closed = {
        "low": ["clenched teeth", "a frown", "a biting lip", "tight lips", "a pout"],
        "mid": ["a closed mouth", "parted lips slightly", "a neutral face", "a smirk"],
        "high": ["a smile", "a smirk", "a cat smile", "a dark smile", "a confident grin",
                 "a panting dark smile", "a gentle smile", "a bright smile"]
    }
    mouth_open = {
        "low": ["shouting", "screaming", "crying with open mouth", "gasping",
                "an open mouth", "heavy breathing"],
        "mid": ["a sigh", "parted lips", "a slightly open mouth", "gasping"],
        "high": ["laughing", "smiling with open mouth", "visible teeth",
                 "an open mouth", "heavy breathing", "gasping", "parted lips",
                 "an open mouth with a smirk"]
    }

    # --- 혀/침 상태 풀 (anima_express.py 통합: L 기반) ---
    tongue_tags = {
        "low": [""],
        "mid": ["licking lips", "sticking out tongue", "a teasing tongue"],
        "high": ["drooling", "messy saliva", "a saliva trail", "tongue out", "thick saliva",
                 "drooling from a smirk", "licking lips hungrily"]
    }

    # --- 노이즈 적용 ---
    def _add_random_noise(score):
        offset = random.choices([-1, 0, 1], weights=[15, 70, 15], k=1)[0]
        return max(0, min(5, score + offset))

    l_score = _add_random_noise(a)          # loveness = a
    lewd_score = _add_random_noise(l)       # lewdness = l
    corr_score = _add_random_noise(5 - m)   # corruption = 5 - m (도덕성 낮을수록 타락)

    _face_logger.debug(f"[INPUT] m={m}, l={l}, a={a}, o={o}, i={i}, s={s}, d={d}, gender={gender}, style={style}")
    _face_logger.debug(f"[SCORES] l_score(loveness)={l_score}, lewd_score={lewd_score}, corr_score={corr_score}")

    # --- 상태 결정 (emotion/makeup용: 3D 페르소나) ---
    def _determine_state(loveness, lewdness, corruption):
        if loveness < 3:
            return "hate"
        if lewdness >= 3 and corruption >= 3:
            return "corrupted_lewd"
        elif lewdness >= 3:
            return "lewd"
        elif corruption >= 3:
            return "corrupted"
        else:
            return "pure"

    state = _determine_state(l_score, lewd_score, corr_score)
    _face_logger.debug(f"[STATE] state={state}")

    # --- 카테고리 결정 (눈/입/혀용: 0~1=low, 2~3=mid, 4~5=high) ---
    def _get_category(score):
        if score <= 1:
            return "low"
        elif score <= 3:
            return "mid"
        else:
            return "high"

    l_cat = _get_category(lewd_score)   # 눈/혀는 Lewdness 기반
    h_cat = _get_category(l_score)      # 입은 Loveness(Happiness) 기반
    _face_logger.debug(f"[CATEGORIES] l_cat={l_cat}, h_cat={h_cat}")

    # --- 성별 대명사 ---
    sbj = "She" if gender == 0 else "He"
    pos = "Her" if gender == 0 else "His"

    # --- emotion 태그 추출 (state 기반: 3D 페르소나) ---
    pool = pools[state]
    num_emotions = random.randint(2, 3)
    emo_tags = random.sample(pool["emotion"], num_emotions)

    # --- 호감도(a) 기반 emotion 보정 (기존 로직 통합) ---
    if a >= 4:
        emo_tags.extend(["warm expression", "gentle smile"])
    elif a <= 1:
        emo_tags.append("indifferent expression")

    emo_str = ", ".join(emo_tags)
    _face_logger.debug(f"[EMOTION] emo_tags={emo_tags}, emo_str={emo_str}")

    # --- makeup 태그 추출 (state 기반) ---
    makeup_tag = random.choice(pool["makeup"])
    _face_logger.debug(f"[MAKEUP] makeup_tag={makeup_tag}")

    # --- 눈 상태 추출 (anima_express.py 방식: L 기반 + 가중치) ---
    # 60% 뜸, 30% 반뜸, 10% 감음
    eye_state = random.choices(["open", "half", "closed"], weights=[60, 30, 10], k=1)[0]

    # Add eye shape
    eye_tag = config.eye_shape + "," + random.choice(eyes_pool[l_cat][eye_state])
    _face_logger.debug(f"[EYES] eye_state={eye_state}, eye_tag={eye_tag}")

    # --- 지성(i) 기반 eye 보정 (기존 로직 통합) ---
    conditional_eye_tags = []
    if i >= 3:
        conditional_eye_tags.extend(["gentle eyes", "affectionate gaze"])
    elif i <= 1:
        conditional_eye_tags.append("vacant stare")
        if lewd_score >= 3 and "empty eyes" not in eye_tag:
            conditional_eye_tags.append("empty eyes")

    # --- 수치심(s) 기반 eye 보정 (기존 로직 통합) ---
    if s >= 4:
        conditional_eye_tags.extend(["shy gaze", "teary eyes"])
    elif s <= 1 and lewd_score >= 3:
        conditional_eye_tags.append("bold gaze")

    # --- 눈 상태별 충돌 태그 제거 ---
    # 감은 눈(closed)과 충돌하는 태그
    closed_conflicts = ["staring", "sparkling", "wide", "sharp", "clear", "lifeless",
                        "narrowed", "disdainful", "upturned", "wet", "rolling",
                        "crossed", "crazed", "dilated", "unfocused", "tearing",
                        "heart-shaped", "white", "glazed", "seductive", "piercing",
                        "gentle", "affectionate", "vacant", "empty", "shy", "teary", "bold"]
    # 반쯤 감은 눈(half)과 충돌하는 태그
    half_conflicts = ["wide", "clear", "sparkling"]

    def _resolve_eye_conflicts(eye_tags, state):
        """눈 상태에 따라 충돌하는 태그 제거."""
        if state == "closed":
            return [t for t in eye_tags if not any(kw in t.lower() for kw in closed_conflicts)]
        elif state == "half":
            return [t for t in eye_tags if not any(kw in t.lower() for kw in half_conflicts)]
        return eye_tags

    # 기본 eye_tag도 충돌 체크
    if eye_state == "closed":
        eye_tag = eye_tag if not any(kw in eye_tag.lower() for kw in closed_conflicts) else "soft eyes"
    elif eye_state == "half":
        eye_tag = eye_tag if not any(kw in eye_tag.lower() for kw in half_conflicts) else "calm eyes"

    # 조건부 eye 태그도 충돌 체크
    conditional_eye_tags = _resolve_eye_conflicts(conditional_eye_tags, eye_state)

    # --- 최종 eye 태그 조합 ---
    all_eye_tags = [eye_tag] + conditional_eye_tags
    _face_logger.debug(f"[EYES_FINAL] all_eye_tags={all_eye_tags}, conditional_eye_tags={conditional_eye_tags}")

    # 눈 동사/명사 처리
    is_eye_verb = eye_tag in ["tearing up", "staring", "looking up", "wincing",
                               "crying with eyes closed", "looking away"]
    eye_sentence = f"{sbj} is {eye_tag}" if is_eye_verb else f"{sbj} has {', '.join(all_eye_tags)}"

    # --- 입 상태 추출 (anima_express.py 방식: H 기반 + 50% 확률로 벌림) ---
    is_mouth_open = random.choice([True, False])
    if is_mouth_open:
        mouth_tag = random.choice(mouth_open[h_cat])
    else:
        mouth_tag = random.choice(mouth_closed[h_cat])
    _face_logger.debug(f"[MOUTH] is_mouth_open={is_mouth_open}, mouth_tag={mouth_tag}")

    # 입이 벌려져 있고 L이 높을 경우 호흡 추가
    if is_mouth_open and l_cat == "high":
        mouth_tag += " while heavy breathing"

    # --- 혀/침 상태 추출 (anima_express.py 방식: L 기반 + 확률) ---
    tongue_tag = ""
    # L_low: 0%, L_mid: 40%, L_high: 80%
    tongue_chance = 0 if l_cat == "low" else (40 if l_cat == "mid" else 80)
    if is_mouth_open and random.randint(1, 100) <= tongue_chance:
        tongue_tag = random.choice(tongue_tags[l_cat])
    _face_logger.debug(f"[TONGUE] tongue_chance={tongue_chance}, tongue_tag={tongue_tag}")

    # --- 화장 태그 처리 ---
    makeup_sentence = f" and wears {makeup_tag}" if makeup_tag else ""

    # --- 영어 문장 조합 ---
    sentence = (f"{sbj} is showing a {emo_str} expression. "
                f"{eye_sentence}{makeup_sentence}, "
                f"and {pos.lower()} lower face features {mouth_tag}.")

    if tongue_tag:
        if tongue_tag.startswith("licking") or tongue_tag.startswith("drooling") or tongue_tag.startswith("sticking"):
            sentence += f" Additionally, {sbj.lower()} is {tongue_tag}."
        else:
            sentence += f" {sbj} has {tongue_tag}."

    _face_logger.debug(f"[SENTENCE] {sentence}")
    _face_logger.debug("-" * 60)
    return sentence


# ====================================================================
# Public API
# ====================================================================

def get_visual_tags(m, l, a, o, i, s, d, gender=0, style=0,
                    feminization_enable=False, breasts_size=0, num=1):
    """
    stats 기반 face/makeup/exposure/body/marks/background 태그 생성.

    Args:
        m, l, a, o, i, s, d: 도덕성, 음란도, 호감도, 복종도, 지성, 수치심, 주도권 (0-5)
        gender: 0=female, 1=male
        style: 0=LN, 1=WAN
        feminization_enable: 남성 여성화 여부
        breasts_size: 가슴 크기 (0-5)
        num: 생성할 결과 개수 (face_generate를 num번 호출)

    Returns:
        list of dict with keys: face, exposure, parts_exposure,
                                bodystyle, marks, background
    """
    eff_breast = min(breasts_size + max(0, l - 2), 5)
    l_level = min(l, 5)

    # --- TAG_PRIORITY_MAP: body만 ---
    TAG_PRIORITY_MAP = {
        "body": {
            "fully_clothed": ["naked", "lingerie_only", "messy_clothes"],
            "proper_posture": ["body_shaking", "dominant_stance",
                               "leaning_on_shoulder"]
        }
    }

    # --- 여성 body 데이터 ---
    female_data = {
        0: {"body": ["completely covered", "modest_clothing", "fully_clothed"]},
        1: {"body": ["collarbone", "unbuttoned_collar", "adjusting_clothes"]},
        2: {"body": ["cleavage_visible", "shirt_pulled_open"]},
        3: {"body": ["bare stomach", "underboob", "thigh-highs"]},
        4: {"body": ["implied nudity", "partially undressed",
                     "falling clothes", "torn_clothes", "cameltoe"]},
        5: {"body": ["naked", "nude", "covered_in_fluids"]}
    }

    # --- 남성 body 데이터 ---
    male_data = {
        0: {"body": ["completely covered", "male_focus", "flat_chest"]},
        1: {"body": ["androgynous_body"]},
        2: {"body": ["crossdressing", "thighhighs"]},
        3: {"body": ["crossdressing", "thighhighs"]},
        4: {"body": ["implied nudity", "partially undressed", "femboy_anatomy"]},
        5: {"body": ["naked", "nude", "covered_in_fluids"]}
    }

    # --- 도덕성 타락 marks 데이터 (acc만) ---
    morality_corruption_data = {
        3: {"acc": ["choker", "ear_piercing"]},
        2: {"acc": ["spiked_choker", "multiple_piercings"]},
        1: {"acc": ["chain_collar", "body_piercing"]},
        0: {"acc": ["shackles", "heavy_chains"]}
    }

    data_set = female_data if gender == 0 else male_data

    # --- 태그 충돌 해결 (body만) ---
    def resolve_conflicts(pool_name, pool_list):
        priority_map = TAG_PRIORITY_MAP.get(pool_name, {})
        if not priority_map:
            return pool_list
        resolved = []
        for tag in pool_list:
            is_weak = False
            for weak, strongs in priority_map.items():
                if tag.lower() == weak:
                    if any(s_tag in pool_list for s_tag in strongs):
                        is_weak = True
                        break
            if not is_weak:
                resolved.append(tag)
        return resolved

    # --- 중복 제거 ---
    def unique_list(lst):
        seen = set()
        res = []
        for item in lst:
            if item.lower() not in seen:
                seen.add(item.lower())
                res.append(item)
        return res

    # --- num번 반복 ---
    results = []
    for _ in range(num):
        # face_generate 호출 (face/expression 문장)
        face = face_generate(m, l, a, o, i, s, d, gender, style)

        exposure_pool = []
        parts_exposure_pool = []
        body_pool = []
        mark_pool = []
        background_pool = []

        # --- body 태그 로드 ---
        for tag in data_set[l_level]["body"]:
            if any(kw in tag.lower()
                   for kw in ["clothing", "clothes", "uniform", "skirt",
                               "shirt", "lingerie"]):
                exposure_pool.append(tag)
            else:
                body_pool.append(tag)

        # --- 도덕성 타락 marks ---
        if m <= 3:
            level = min(m, 3)
            cor_data = morality_corruption_data[level]
            mark_pool.extend(cor_data["acc"])

        # --- 수치심 기반 body ---
        if s >= 4:
            body_pool.append("body_shaking")

        # --- 음란도 기반 parts_exposure ---
        if l_level >= 2:
            parts_exposure_pool.append("see_through_clothes")
            if gender == 0 or (gender == 1 and feminization_enable):
                parts_exposure_pool.extend(["covered_nipples", "puffy_nipples"])

        if l_level >= 3:
            if gender == 0:
                parts_exposure_pool.append("cameltoe")
            if (gender == 0 and eff_breast is not None
                    and s <= 3):
                parts_exposure_pool.append("visible_nipples")
            parts_exposure_pool.append("navel_visible")

        # --- 추가 조건 ---
        if m <= 1 and l_level >= 2:
            exposure_pool.extend(["messy_clothes"])
        if l_level >= 4:
            parts_exposure_pool.append("thigh_gap_visible")

        if l_level >= 2 and a >= 4:
            background_pool.extend(["floating_hearts"])
        if l_level >= 4 and s <= 2:
            background_pool.extend(["heavy_breathing", "floating_hearts"])

        if d >= 4 and o <= 1:
            body_pool.extend(["dominant_stance", "looming_over"])

        # --- marks ---
        marks_raw = []
        if l_level == 5:
            marks_raw.append("dog_collar")
        if o == 5:
            if l_level >= 3:
                marks_raw.extend(["leash_attached", "property_tattoo"])
            else:
                marks_raw.append("choker")

        if style == 1:
            if l_level >= 3:
                marks_raw.append("bruises_on_body")

        mark_pool.extend(marks_raw)

        # --- body 충돌 해결 ---
        body_pool = resolve_conflicts("body", body_pool)

        results.append({
            "face":           face,
            "exposure":       ", ".join(unique_list(exposure_pool)),
            "parts_exposure": ", ".join(unique_list(parts_exposure_pool)),
            "bodystyle":      ", ".join(unique_list(body_pool)),
            "marks":          ", ".join(unique_list(mark_pool)),
            "background":     ", ".join(unique_list(background_pool)),
        })

    return results


def get_body_anatomy_tags(m, l, a, o, i, s, d, gender=0, style=0,
                          plump_enable=False, feminization_enable=False,
                          breasts_size=0, hip_size=0, muscle_enb=False,
                          vulgarity_enb=True):
    """
    stats 기반 신체 해부학 태그 생성.

    Returns:
        쉼표로 연결된 태그 문자열
    """
    tags_list = []

    # --- 타락 데이터 풀 ---
    vulgarity_data = {
        0: ['normal_nipples', 'pink_areolae', 'pristine_skin', 'clean_body',
            'flat_stomach', 'hairless_pubic_region', 'modest_panties',
            'closed_pussy', 'pink_pussy'],
        1: ['perky_breasts', 'perky_nipples', 'slight_sweat', 'pubic_stubble',
            'slightly_parted_labia', 'moist_pussy', 'blush',
            'slightly_open_mouth', 'cameltoe'],
        2: ['swollen_nipples', 'puffy_areolae', 'red_areolae', 'bite_marks',
            'wet_panties', 'puffy_labia', 'red_pussy', 'pubic_hair',
            'heavy_breathing'],
        3: ['dark_areolae', 'protruding_nipples', 'breast_veins', 'womb_tattoo',
            'dripping_pussy', 'heavy_sweat', 'shiny_skin', 'bushy_pubic_hair',
            'ahegao'],
        4: ['dark_areolae', 'huge_areolae', 'inverted_nipples', 'body_writing',
            'magic_crest', 'leaking_fluids', 'messy_crotch', 'gaping_pussy',
            'mind_break', 'cum_on_face'],
        5: ['extreme dark_areolae', 'huge_puffy_areolae', 'lactating',
            'heavily_tattooed', 'succubus_tattoos', 'dripping', 'hyper_pussy',
            'extreme_sweat', 'total_mind_break', 'eyes_rolled_back',
            'excessive_cum']
    }

    bimbo_data = {
        0: ['light_makeup', 'lipgloss', 'neat_hair', 'clear_skin',
            'normal_pupils', 'modest_smile'],
        1: ['pink_lips', 'mascara', 'painted_nails', 'dyed_hair',
            'slightly_parted_lips', 'hoop_earrings', 'slight_blush'],
        2: ['heavy_makeup', 'thick_lips', 'glossy_lips', 'fake_nails',
            'blonde_hair', 'fake_tan', 'cleavage', 'dumb_smile',
            'navel_piercing'],
        3: ['bimbo', 'fake_tan', 'gyaru', 'heavy_lipstick', 'long_fake_nails',
            'tramp_stamp', 'heart_eyes', 'drooling', 'micro_bikini',
            'underboob', 'tongue_out'],
        4: ['extreme_fake_tan', 'huge_fake_nails', 'hyper_cleavage',
            'bimbo_lobotomy', 'brain_empty', 'ahegao', 'heavy_sweat',
            'happy_sex'],
        5: ['extreme_fake_tan', 'plastic_look', 'bimbofication',
            'hyper_thick_lips', 'extreme_bimbo', 'permanent_ahegao',
            'excessive_fluids', 'slut_stamp', 'euphoric']
    }

    innocent_obscenity_data = {
        0: ['pure', 'innocent_expression', 'pristine_clothes', 'modest',
            'closed_mouth', 'clean_body'],
        1: ['shy', 'embarrassed', 'slight_blush', 'fidgeting',
            'cameltoe_through_panties', 'nervous_sweat', 'watery_eyes'],
        2: ['heavy_blush', 'tearing_up', 'wet_panties', 'covering_face',
            'erect_nipples_through_clothes', 'trembling', 'muffled_moan',
            'crossed_legs'],
        3: ['crying_with_pleasure', 'leaking_fluids', 'messy_clothes',
            'wet_clothes', 'tears', 'pleading', 'panting',
            'corrupted_innocence'],
        4: ['tearful_ahegao', 'holy_aura', 'praying_pose', 'dripping_pussy',
            'ruined_clothes', 'crying', 'mind_break_tears',
            'shameful_pleasure'],
        5: ['ruined_saint', 'holy_prostitute', 'mind_break_from_pleasure',
            'excessive_fluids_on_pure_clothes', 'crying_ahegao', 'spasms',
            'stained_clothes']
    }

    current_vulgar_level = min(5, max(0, int(l)))

    if i <= 2:
        selected_data_pool = bimbo_data
    elif a >= 4 or s >= 3:
        selected_data_pool = innocent_obscenity_data
    else:
        selected_data_pool = vulgarity_data

    vulgar_tags_pool = selected_data_pool.get(current_vulgar_level, [])

    if vulgarity_enb:
        for tag in vulgar_tags_pool:
            if any(sz in tag for sz in ['huge_breasts', 'large_breasts',
                                         'hyper_breasts', 'massive_breasts']):
                continue
            is_female = any(kw in tag.lower()
                            for kw in ['pussy', 'labia', 'vulva'])
            can_fem = (gender == 0) or feminization_enable
            if is_female and not can_fem:
                continue
            tags_list.append(tag)

    # --- plump ---
    current_plump = 2
    if plump_enable:
        stat_score = l + (5 - m)
        current_plump = min(5, max(0, 2 + (stat_score // 4)))

    # --- feminization ---
    fem_level = 0
    if feminization_enable and gender == 1:
        fem_level = min(5, l + (a // 3))

    eff_breast = min(breasts_size + max(0, l - 2), 5)
    eff_hip = min(hip_size + max(0, l - 3), 5)

    plump_tags_map = {
        0: [""], 1: [""], 2: [""], 3: ["curvy"],
        4: ["plump", "chubby"], 5: ["very_plump", "fat_gain"]
    }
    tags_list.extend(plump_tags_map.get(current_plump, plump_tags_map[2]))

    # --- 남성 여성화 ---
    if gender == 1 and fem_level > 0:
        if fem_level >= 3:
            tags_list.extend(["narrow_shoulders", "slender_waist"])
        if fem_level <= 1 and current_plump < 3 and muscle_enb:
            tags_list.append("muscular")
        elif fem_level >= 3:
            tags_list.extend(["pretty_boy", "feminine_boys"])

    # --- 가슴 크기 ---
    breast_map = {0: "tiny_breasts", 1: "small_breasts", 2: "medium_breasts",
                  3: "large_breasts", 4: "huge_breasts", 5: "massive_breasts"}

    if gender == 1:
        final_b = min(eff_breast + max(0, current_plump - 2)
                      + (1 if fem_level >= 3 else 0), 5)
        if fem_level <= 2 or (final_b <= 1 and breasts_size <= 1
                              and current_plump < 2):
            tags_list.append("flat_chest")
        else:
            tags_list.append(breast_map.get(final_b, "small_breasts"))
    else:
        tags_list.append(breast_map.get(eff_breast, "medium_breasts"))

    # --- 힙 ---
    if eff_hip >= 4 or current_plump >= 4:
        tags_list.append("wide_hips")
        if gender == 0 and current_plump >= 3:
            tags_list.append("curvy_body")
    elif eff_hip <= 1 and current_plump <= 1 and gender == 0:
        tags_list.append("slim_hips")

    # --- 음란도 >= 2: 젖꼭지/유두 ---
    if l >= 2:
        color_idx = min(3, (l + max(0, 5 - m)) // 2)
        nipple_colors = ["pale_nipples", "pink_nipples",
                         "darker_nipples", "dark_nipples"]
        tags_list.append(nipple_colors[color_idx])

        areola_map = {0: "small_areolae", 1: "medium_areolae",
                      2: "large_areolae", 3: "huge_areolae",
                      4: "huge_areolae", 5: "huge_areolae"}
        tags_list.append(areola_map.get(l // 2, "medium_areolae"))

        prolapse_map = {0: "flat_nipples", 1: "small_nipples",
                        2: "medium_nipples", 3: "large_nipples",
                        4: "huge_nipples"}
        tags_list.append(prolapse_map[min(l, 4)])

    # --- 음란도 >= 3 ---
    if l >= 3:
        if s >= 4 or (gender == 1 and fem_level >= 3):
            tags_list.append("no_pubic_hair")
        else:
            tags_list.append("bushy_pubic_hair" if l >= 4
                             else "trimmed_pubic_hair")

        if gender == 0:
            tags_list.append("pussy_juice")
        elif a >= 4:
            tags_list.append("pre_come")

        if gender == 0:
            if m >= 3:
                tags_list.append("light_pink_vagina")
            elif m >= 1:
                tags_list.append("pink_vagina")
            else:
                tags_list.append("dark_vagina, puffy_pussy")
            tags_list.append("light_anus" if m >= 3
                             else ("normal_anus" if m >= 1 else "dark_anus"))
        else:
            glans_colors = ["light_glans", "pink_glans",
                            "dark_glans", "very_dark_glans"]
            tags_list.append(glans_colors[min(color_idx + 1, 3)])
            tags_list.append("dark_anus" if m < 1 else "normal_anus")
            if l >= 4:
                tags_list.extend(["futanari", "penis", "cum_on_penis"])

    # --- 노출 레벨 ---
    exposure_level = _calculate_exposure_level(l, s, style)
    if exposure_level >= 5:
        tags_list.extend(["naked", "no_clothes"])
    elif exposure_level >= 4:
        tags_list.extend(["lingerie", "thong"] if gender == 0 else ["briefs"])
    elif exposure_level >= 3:
        tags_list.extend(["top_lifted", "bare_shoulders", "cleavage"]
                         if gender == 0 else ["bare_legs", "shirt_open"])
    elif exposure_level >= 2:
        tags_list.extend(["midriff_bared", "navel_visible", "short_skirt"]
                         if gender == 0 else ["unbuttoned_shirt"])
    elif exposure_level >= 1:
        tags_list.extend(["fully_clothed", "high_collared_shirt"]
                         if gender == 0 else ["uniform"])
    else:
        tags_list.extend(["modest_outfit", "fully_clothed"]
                         if gender == 0 else ["clothed"])

    # --- 수치심/음란도 보정 ---
    if s >= 5 and exposure_level < 4:
        tags_list.extend(["holding_clothes", "adjusting_uniform"])
    elif l >= 4 and s <= 1:
        tags_list.extend(["skirt_lifted", "pants_down"]
                         if gender == 0 else ["shirt_off_shoulder"])

    if (eff_hip >= 2 or current_plump >= 3) and gender == 0:
        tags_list.append("cameltoe")

    final_b_check = eff_breast + max(0, current_plump - 2)
    if final_b_check >= 3 or (gender == 1 and final_b_check >= 2):
        tags_list.append("cleavage")
        if l >= 4 and s <= 2:
            tags_list.append("underboob")

    if current_plump >= 3 or style == 1 or l >= 4:
        tags_list.append("oily_skin")

    if s <= 1 and l >= 3:
        tags_list.append("body_mark")

    return ", ".join(tags_list)


def get_random_expression(m, l, a, o, i, s, d):
    """
    stats 기반 랜덤 표정 태그 생성.

    Returns:
        쉼표로 연결된 표정 태그 문자열
    """
    happy_pool = ["smile", "blush", "closed_eyes", "grinning",
                  "heart_shaped_pupils", "giggling"]
    shame_pool = ["shy", "embarrassed", "looking_away", "blush",
                  "biting_lip", "sweating", "nervous_smile"]
    mindless_pool = ["vacant_eyes", "empty_eyes", "drooling", "open_mouth",
                     "half-closed_eyes", "unfocused_eyes"]
    lewd_pool = ["ahegao", "tongue_out", "saliva", "rolling_eyes",
                 "blush", "heavy_breathing", "lustrous_eyes"]
    dominant_pool = ["smirk", "staring", "contemptuous", "serious_expression",
                     "glare", "arrogant_smile"]

    weights = {
        "happy": max(1, a),
        "shame": max(1, s),
        "mindless": max(1, (5 - i) + l),
        "lewd": max(1, l - s),
        "dominant": max(1, d)
    }

    category = random.choices(list(weights.keys()),
                              weights=list(weights.values()))[0]

    pool_map = {
        "happy": happy_pool, "shame": shame_pool,
        "mindless": mindless_pool, "lewd": lewd_pool,
        "dominant": dominant_pool
    }
    pool = pool_map[category]

    num_tags = random.randint(1, 3)
    selected = random.sample(pool, num_tags)
    return ", ".join(selected)


# ====================================================================
# Private helpers
# ====================================================================

def _calculate_exposure_level(l, s, style):
    """음란도(L)와 수치심(S), 스타일을 기반으로 의상 노출 레벨 계산."""
    effective_l = l if s <= 2 else max(0, l - 1)
    style_bonus = 1 if style == 1 else 0
    return effective_l + style_bonus
