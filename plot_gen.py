import json
import random as rand
import config
import character_setup
import io
import llm_novel_gui_func
import os
import persona
import re
import story_gen
import sys
import time
from openai import APITimeoutError
from openAPI_control import (
    get_openai_client, call_openai_for_plot, call_openai_for_client
)

# =============================================================================
# plot/ 디렉토리에서 데이터 로드 (prompts.txt, variables.json)
# =============================================================================

_PLOT_DIR = os.path.join(os.path.dirname(__file__), "plot")

def _load_plot_file(filename):
    """plot/ 디렉토리에서 파일 로드"""
    filepath = os.path.join(_PLOT_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        if filename.endswith(".json"):
            return json.load(f)
        return f.read()

def _load_variables():
    return _load_plot_file("variables.json")

def _load_prompts():
    """plot/prompts.txt 로드 (======key====== 형식 평문 파싱)"""
    raw = _load_plot_file("prompts.txt")
    parsed = {}
    parts = re.split(r"======([^=]+)======", raw)
    for i in range(1, len(parts), 2):
        key = parts[i].strip()
        value = parts[i + 1].rstrip("\n")
        parsed[key] = value
    return parsed

def _build_prompt(template, **kwargs):
    return template.format(**kwargs)

# =============================================================================
# 데이터 로드 (data_extended.json)
# =============================================================================

def load_extended_data():
    data_path = os.path.join(os.path.dirname(__file__), "plot", "data_extended.json")
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    templates = {int(k): v for k, v in data["templates"].items()}
    tag_words = {int(k): v for k, v in data["tag_words"].items()}
    universal_tags = data["universal_tags"]
    universal_tags_soft = data.get("universal_tags_soft", {})
    return templates, tag_words, universal_tags, universal_tags_soft

TEMPLATES, TAG_WORDS, UNIVERSAL_TAGS, UNIVERSAL_TAGS_SOFT = load_extended_data()
VARS = _load_variables()

# =============================================================================
# 헬퍼: 태그 강도별 분류
# =============================================================================

def _classify_tags_by_difficulty(universal_tags):
    tag_cfg = VARS["tag_classifications"]
    all_actions = universal_tags["actions"]
    _actions_easy = [t for t in all_actions if any(k in t for k in tag_cfg["actions"]["easy_keywords"])]
    _actions_mid = [t for t in all_actions if t not in _actions_easy and any(k in t for k in tag_cfg["actions"]["mid_keywords"])]
    _actions_hard = [t for t in all_actions if t not in _actions_easy and t not in _actions_mid]
    all_sensations = universal_tags["sensations"]
    _sensations_easy = [t for t in all_sensations if any(k in t for k in tag_cfg["sensations"]["easy_keywords"])]
    _sensations_mid = [t for t in all_sensations if t not in _sensations_easy and any(k in t for k in tag_cfg["sensations"]["mid_keywords"])]
    _sensations_hard = [t for t in all_sensations if t not in _sensations_easy and t not in _sensations_mid]
    all_emotions = list(universal_tags["emotions"])
    _emotions_mid = all_emotions[len(all_emotions)//3:2*len(all_emotions)//3]
    _emotions_hard = [e for e in all_emotions if e not in _emotions_mid]
    _emotions_easy = [e for e in all_emotions if e not in _emotions_mid and e not in _emotions_hard]
    return {
        "actions": {"easy": _actions_easy, "mid": _actions_mid, "hard": _actions_hard},
        "sensations": {"easy": _sensations_easy, "mid": _sensations_mid, "hard": _sensations_hard},
        "emotions": {"easy": _emotions_easy, "mid": _emotions_mid, "hard": _emotions_hard},
    }

def _get_ep_tags(ep_num, total_ep, classified_tags, universal_tags_soft):
    ep_tag_cfg = VARS["ep_tag_sampling"]
    soft_range = ep_tag_cfg["soft_burn"]["ep_range"]
    if soft_range[0] <= ep_num <= soft_range[1] and universal_tags_soft:
        sa = universal_tags_soft.get("actions", [])
        ss = universal_tags_soft.get("sensations", [])
        se = universal_tags_soft.get("emotions", [])
        sp = universal_tags_soft.get("appearance", [])
        sr = universal_tags_soft.get("resistance", [])
        n_act = min(ep_tag_cfg["soft_burn"]["n_actions"], len(sa))
        n_sen = min(ep_tag_cfg["soft_burn"]["n_sensations"], len(ss))
        n_emo = min(ep_tag_cfg["soft_burn"]["n_emotions"], len(se))
        uni_act = rand.sample(sa, n_act) if sa else []
        uni_sen = rand.sample(ss, n_sen) if ss else []
        uni_emo = rand.sample(se, n_emo) if se else []
        if sp: uni_act += rand.sample(sp, min(1, len(sp)))
        if sr: uni_emo += rand.sample(sr, min(1, len(sr)))
        return uni_act, uni_sen, uni_emo
    ratio = ep_num / total_ep
    if ratio <= ep_tag_cfg["early"]["ratio_max"]:
        n_act, n_sen, n_emo = ep_tag_cfg["early"]["n_actions"], ep_tag_cfg["early"]["n_sensations"], ep_tag_cfg["early"]["n_emotions"]
        act_pool, sen_pool, emo_pool = classified_tags["actions"]["easy"], classified_tags["sensations"]["easy"], classified_tags["emotions"]["easy"]
    elif ratio <= ep_tag_cfg["mid"]["ratio_max"]:
        n_act, n_sen, n_emo = ep_tag_cfg["mid"]["n_actions"], ep_tag_cfg["mid"]["n_sensations"], ep_tag_cfg["mid"]["n_emotions"]
        act_pool = classified_tags["actions"]["easy"] + classified_tags["actions"]["mid"]
        sen_pool = classified_tags["sensations"]["easy"] + classified_tags["sensations"]["mid"]
        emo_pool = classified_tags["emotions"]["easy"] + classified_tags["emotions"]["mid"]
    elif ratio <= ep_tag_cfg["late"]["ratio_max"]:
        n_act, n_sen, n_emo = ep_tag_cfg["late"]["n_actions"], ep_tag_cfg["late"]["n_sensations"], ep_tag_cfg["late"]["n_emotions"]
        act_pool = classified_tags["actions"]["easy"] + classified_tags["actions"]["mid"] + classified_tags["actions"]["hard"]
        sen_pool = classified_tags["sensations"]["easy"] + classified_tags["sensations"]["mid"] + classified_tags["sensations"]["hard"]
        emo_pool = classified_tags["emotions"]["easy"] + classified_tags["emotions"]["mid"] + classified_tags["emotions"]["hard"]
    else:
        n_act, n_sen, n_emo = ep_tag_cfg["extreme"]["n_actions"], ep_tag_cfg["extreme"]["n_sensations"], ep_tag_cfg["extreme"]["n_emotions"]
        act_pool = classified_tags["actions"]["easy"] + classified_tags["actions"]["mid"] + classified_tags["actions"]["hard"]
        sen_pool = classified_tags["sensations"]["easy"] + classified_tags["sensations"]["mid"] + classified_tags["sensations"]["hard"]
        emo_pool = classified_tags["emotions"]["easy"] + classified_tags["emotions"]["mid"] + classified_tags["emotions"]["hard"]
    return (rand.sample(act_pool, min(n_act, len(act_pool))),
            rand.sample(sen_pool, min(n_sen, len(sen_pool))),
            rand.sample(emo_pool, min(n_emo, len(emo_pool))))

def _get_level_description(i, total_episodes):
    ld = VARS["level_descriptions"]
    ratio = i / total_episodes
    if i == 2: return ld["ep2"]
    elif ratio <= 0.3: return ld["early"]
    elif ratio <= 0.5:
        if i == int(total_episodes * 0.3) + 1: return ld["mid_start_1"]
        elif i == int(total_episodes * 0.3) + 2: return ld["mid_start_2"]
        return ld["mid_default"]
    elif ratio <= 0.7:
        if i == int(total_episodes * 0.5) + 1: return ld["mid_late_1"]
        elif i == int(total_episodes * 0.5) + 2: return ld["mid_late_2"]
        return ld["mid_late_default"]
    elif ratio <= 0.9:
        if i == int(total_episodes * 0.7) + 1: return ld["late_1"]
        elif i == int(total_episodes * 0.7) + 2: return ld["late_2"]
        return ld["late_default"]
    else: return ld["ending"]

def _compute_resistance_positions(total_episodes):
    rc = VARS["resistance_positions"]
    return {
        max(2, int(total_episodes * rc["seung_end_ratio"])),
        max(3, int(total_episodes * rc["jeon_start_ratio"])),
        max(4, int(total_episodes * rc["jeon_end_ratio"])),
        min(total_episodes - 1, int(total_episodes * rc["kyeol_ratio"]))
    }

# =============================================================================
# _update_character_sheets_via_api
# =============================================================================

def _update_character_sheets_via_api(episode_text, ep_num,
                                      current_protagonist, current_partner,
                                      name1, name2, log_fn=None):
    prompts = _load_prompts()
    api_settings = VARS["api_settings"]
    counter_keys = VARS["counter_keys"]
    fixed_keys = VARS["fixed_keys"]
    hair_color_keywords = VARS["hair_color_keywords"]

    prompt = _build_prompt(
        prompts["character_sheet_update"],
        current_protagonist=current_protagonist, current_partner=current_partner,
        sex_count=config.sex_count, masturbation_count=config.masturbation_count,
        patting_count=config.patting_count, normal_sex_count=config.normal_sex_count,
        reverse_sex_count=config.reverse_sex_count, cowboy_sex_count=config.cowboy_sex_count,
        anal_sex_count=config.anal_sex_count, pose_sex_count=config.pose_sex_count,
        ep_num=ep_num, episode_text=episode_text, name1=name1, name2=name2
    )
    client = get_openai_client()
    messages = [
        {"role": "system", "content": VARS["system_role"]},
        {"role": "user", "content": prompt}
    ]
    temp = api_settings["temperature"]
    max_try = 0
    timeout_check = 0
    while timeout_check == 0:
        try:
            response = client.chat.completions.create(
                model=api_settings["model"], messages=messages, temperature=temp,
                top_p=api_settings["top_p"], stream=api_settings["stream"],
                timeout=api_settings["timeout"],
                extra_body={"repeat_penalty": api_settings["repeat_penalty"], "top_k": api_settings["top_k"]}
            )
            timeout_check = 1
        except APITimeoutError:
            if log_fn:
                log_fn(f"[캐릭터 시트 업데이트] EPISODE {ep_num} - 서버 응답 시간 초과. 재시도 ({max_try + 1}/{api_settings['max_retries']})")
            timeout_check = 0
            max_try += 1
            time.sleep(api_settings["retry_delay"])
            if max_try > api_settings["max_retries"]:
                if log_fn:
                    log_fn(f"[캐릭터 시트 업데이트] EPISODE {ep_num} - 서버 응답 실패. 기존 시트 유지")
                return current_protagonist, current_partner

    result = response.choices[0].message.content.strip()
    import json as json_module
    try:
        result_clean = result.strip()
        if result_clean.startswith("```"):
            result_clean = result_clean.split("\n")[0].strip("` ")
            json_str = "\n".join(result.strip().split("\n")[1:])
            json_str = json_str.rstrip("`").strip()
        else:
            json_str = result_clean
        data = json_module.loads(json_str)
        proto = data.get("protagonist", {})
        partner = data.get("partner", {})

        # 이전 에피소드의 시트에서 baseline 값 추출 (config 변수 수정 없이)
        proto_baseline = _parse_sheet_to_dict(current_protagonist)
        partner_baseline = _parse_sheet_to_dict(current_partner)

        # protagonist 값 업데이트 (config 변수 수정 없이)
        if proto:
            episode_has_hair_change = any(kw in episode_text for kw in hair_color_keywords)
            # fixed_keys: baseline 값을 proto에 먼저 복사 (LLM이 반환하지 않아도 유지)
            for key in fixed_keys:
                if key in proto_baseline and key not in proto:
                    proto[key] = proto_baseline[key]
            for key, val in proto.items():
                if key in fixed_keys: continue
                if key in counter_keys:
                    current_val = proto_baseline.get(key, 0)
                    if val is not None and val > current_val:
                        proto[key] = val
                elif key == "hair_color":
                    current_val = proto_baseline.get(key, "")
                    if current_val and val != current_val and not episode_has_hair_change:
                        proto[key] = current_val
                # else: 이미 proto[key] = val

        # partner 값 업데이트
        if partner:
            map_key = {"name": "name", "age": "age", "sex": "sex", "job": "job",
                       "appearance": "appearance", "personality": "personality",
                       "clothes": "clothes"}
            # partner도 고정값 baseline에서 상속
            partner_fixed_keys = ["name", "age", "sex", "job"]
            for key in partner_fixed_keys:
                if key in partner_baseline and key not in partner:
                    partner[key] = partner_baseline[key]
            for key, val in partner.items():
                partner[map_key.get(key, key)] = val

        # 텍스트 시트로 변환
        new_protagonist = _build_protagonist_sheet_text(proto, name1)
        new_partner = _build_partner_sheet_text(partner)

        # JSON 데이터를 파일로 저장 (progress/character_sheet_ep{N}.json)
        _plot_hash = getattr(config, 'plot_hash', '')
        _save_character_sheet_json(data, ep_num, _plot_hash)

        if log_fn:
            log_fn(f"[캐릭터 시트 업데이트] EPISODE {ep_num} - JSON 파싱 성공, 파일 저장 완료")
        return new_protagonist, new_partner
    except (json_module.JSONDecodeError, KeyError, Exception) as e:
        if log_fn:
            log_fn(f"[캐릭터 시트 업데이트] EPISODE {ep_num} - JSON 파싱 실패: {e}. 기존 시트 유지")
        return current_protagonist, current_partner


def _parse_sheet_to_dict(sheet_text):
    """캐릭터 시트 텍스트를 딕셔너리로 파싱"""
    result = {}
    for line in sheet_text.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()
            # 숫자 값은 int로 변환
            try:
                val = int(val.replace("%", ""))
            except (ValueError, AttributeError):
                pass
            result[key] = val
    return result


def _build_protagonist_sheet_text(proto, name1):
    """protagonist 딕셔너리를 텍스트 시트로 변환"""
    lines = ["## Character Sheet ##"]
    lines.append(f"이름: {proto.get('name', name1)}")
    lines.append(f"나이: {proto.get('age', '?')}")
    lines.append(f"성별: {proto.get('sex', '?')}")
    lines.append(f"직업: {proto.get('job', '?')}")
    lines.append(f"직업 특성: {proto.get('job_attribute', '?')}")
    lines.append(f"목표: {proto.get('objective', '?')}")
    lines.append(f"행복도: {proto.get('happiness', '?')}")
    lines.append(f"머리색: {proto.get('hair_color', '?')}")
    lines.append(f"헤어스타일: {proto.get('hair_style', '?')}")
    lines.append(f"눈 색깔: {proto.get('eye_color', '?')}")
    lines.append(f"피부 색깔: {proto.get('skin_color', '?')}")
    lines.append(f"얼굴 스타일: {proto.get('face_style', '?')}")
    lines.append(f"가슴크기: {proto.get('breasts_size', '?')}")
    lines.append(f"엉덩이 크기: {proto.get('hip_size', '?')}")
    lines.append(f"몸매: {proto.get('body_size', '?')}")
    lines.append(f"복장: {proto.get('clothes', '?')}")
    lines.append(f"액세서리: {proto.get('acc', '?')}")
    lines.append(f"성격 (내면): {proto.get('personality_real', '?')}")
    lines.append(f"성격 (요약): {proto.get('personality_text', '?')}")
    lines.append(f"애정도: {proto.get('love_value', 0)}%")
    # 카운터 값
    return "\n".join(lines)


def _build_partner_sheet_text(partner):
    """partner 딕셔너리를 텍스트 시트로 변환"""
    lines = ["## Partner Sheet ##"]
    lines.append(f"이름: {partner.get('name', '?')}")
    lines.append(f"나이: {partner.get('age', '?')}")
    lines.append(f"성별: {partner.get('sex', '?')}")
    lines.append(f"직업: {partner.get('job', '?')}")
    lines.append(f"외모: {partner.get('appearance', '?')}")
    lines.append(f"성격: {partner.get('personality', '?')}")
    lines.append(f"복장: {partner.get('clothes', '?')}")
    return "\n".join(lines)


def _save_character_sheet_json(data, ep_num, plot_hash):
    """character_sheet JSON 데이터를 파일로 저장"""
    import json as json_module
    progress_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress")
    os.makedirs(progress_dir, exist_ok=True)
    filepath = os.path.join(progress_dir, f"character_sheet_ep{ep_num:02d}_{plot_hash}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json_module.dump(data, f, ensure_ascii=False, indent=2)

# =============================================================================
# plot_gen_extended (메인)
# =============================================================================

def plot_gen_extended(template_id, total_episodes=12, theme_msg=None,
                      breeds_data=None, jinshugai_templates=None,
                      progression_events=None, callback=None):
    if template_id not in TEMPLATES:
        return f"잘못된 템플릿 ID입니다. 1~10 사이의 값을 입력하세요."

    plot_hash = getattr(config, 'plot_hash', '')
    template = TEMPLATES[template_id]
    tags = TAG_WORDS[template_id]
    config.current_episode_index = 0
    for key in VARS["counter_keys"]:
        setattr(config, key, 0)
    config.episode_snapshots = []
    if getattr(config, 'inc_flag', 0) == 1:
        rel1 = getattr(config, 'rel1', '')
        if rel1 in ('엄마', '어머니'):
            config.sex_count = 1

    protagonist_sheet, _ = character_setup.character_sheet(0)
    partner_sheet = character_setup.partner_sheet()
    config.episode_protagonist_sheets = [protagonist_sheet] * total_episodes
    config.episode_partner_sheets = [partner_sheet] * total_episodes

    rel1 = getattr(config, 'rel1', '')
    name1 = getattr(config, 'name', '주인공')
    name2 = getattr(config, 'name2', '상대방')
    job1 = getattr(config, 'job', '직업 미정')
    job2 = getattr(config, 'job2', '직업 미정')
    age1 = getattr(config, 'age', '?')
    age2 = getattr(config, 'age2', '?')

    persona_text = getattr(config, 'persona_text', '')
    if not persona_text:
        old_stdout = sys.stdout
        sys.stdout = captured_persona = io.StringIO()
        try:
            result = persona.generate_ultimate_heroine_progression(num_episodes=total_episodes, fixed_breeds=breeds_data)
        except Exception:
            result = None
        finally:
            sys.stdout = old_stdout
        persona_text = captured_persona.getvalue().strip()
        if result:
            config.persona_result = result

    # Phase별 전환
    phase_names = VARS["phase_names"]
    progression_stages = []
    start_stage = rand.randint(2, 3)
    normal_episodes = total_episodes - 1
    for i in range(total_episodes):
        if i == total_episodes - 1:
            progression_stages.append(6)
        else:
            progress_ratio = i / (normal_episodes - 1) if normal_episodes > 1 else 1
            current_val = start_stage + (5 - start_stage) * progress_ratio
            stage_idx = int(round(current_val))
            if progression_stages and stage_idx < progression_stages[-1]:
                stage_idx = progression_stages[-1]
            progression_stages.append(stage_idx)

    phase_transition_texts = []
    for i in range(total_episodes):
        prev_phase = progression_stages[i - 1] if i > 0 else progression_stages[0]
        curr_phase = progression_stages[i]
        if prev_phase != curr_phase:
            try:
                transition = story_gen._get_phase_transition_content(prev_phase, curr_phase, ep_index=i)
                if transition:
                    phase_transition_texts.append(f"[Ep.{i+1}] {phase_names[curr_phase]} 전환: {transition}")
            except Exception:
                pass
    phase_transition_text = "\n".join(phase_transition_texts) if phase_transition_texts else "(Phase 전환 내용 없음)"

    mutual_corruption_templates = set(VARS["mutual_corruption_templates"])
    relationship_desc = ""
    if rel1:
        relationship_desc = f"{name1}은(는) {name2}의 {rel1}입니다."
    else:
        relationship_desc = f"{name1}과(와) {name2}는 {job1}과(와) {job2}입니다."
    if template_id in mutual_corruption_templates:
        relationship_desc += (f"\n- {name1}, {name2}의 관계는 {config.relationship}입니다.")
    else:
        relationship_desc += (f"\n- {name1}, {name2}의 관계는 {config.relationship}입니다.")

    classified_tags = _classify_tags_by_difficulty(UNIVERSAL_TAGS)
    tag_sel = VARS["tag_selection_counts"]
    selected_items = rand.sample(tags["items"], min(tag_sel["items"], len(tags["items"])))
    selected_actions = rand.sample(tags["actions"], min(tag_sel["actions"], len(tags["actions"])))
    selected_sensations = rand.sample(tags["sensations"], min(tag_sel["sensations"], len(tags["sensations"])))
    selected_resistance = rand.sample(tags["resistance"], min(tag_sel["resistance"], len(tags["resistance"])))
    selected_locations = rand.sample(tags["locations"], min(tag_sel["locations"], len(tags["locations"])))
    uni_actions = rand.sample(UNIVERSAL_TAGS["actions"], min(tag_sel["universal_actions"], len(UNIVERSAL_TAGS["actions"])))
    uni_sensations = rand.sample(UNIVERSAL_TAGS["sensations"], min(tag_sel["universal_sensations"], len(UNIVERSAL_TAGS["sensations"])))
    uni_emotions = rand.sample(UNIVERSAL_TAGS["emotions"], min(tag_sel["universal_emotions"], len(UNIVERSAL_TAGS["emotions"])))
    uni_appearance = rand.sample(UNIVERSAL_TAGS["appearance"], min(tag_sel["universal_appearance"], len(UNIVERSAL_TAGS["appearance"])))

    resistance_positions = _compute_resistance_positions(total_episodes)
    theme_info = f"테마: {theme_msg}" if theme_msg else "(별도 테마 없음)"

    breeds_info = ""
    jinshugai_info = ""
    if breeds_data:
        breeds_text = "\n".join([f"  - {name}: {data['trope']}" for name, data in breeds_data])
        breeds_info = f"\n* 동물 속성: {breeds_text}"
    if jinshugai_templates:
        first_id = jinshugai_templates[0].get('id') if jinshugai_templates else None
        extra_jinshugai = jinshugai_templates[1:] if first_id == template_id else jinshugai_templates
        if extra_jinshugai:
            jinshugai_text = "\n".join([f"  - {t.get('id', '?')}. {t.get('name', 'Unknown')}: {t.get('concept', '')}" for t in extra_jinshugai])
            jinshugai_info = f"\n  추가 진슈가이: {jinshugai_text}"

    inc_emphasis = ""
 
    phase1_end = int(total_episodes * 0.3)
    phase2_start = phase1_end + 1
    phase2_end = int(total_episodes * 0.5)
    phase3_start = phase2_end + 1
    phase3_end = int(total_episodes * 0.7)
    phase4_start = phase3_end + 1

    _log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
    os.makedirs(_log_dir, exist_ok=True)
    log_file = open(os.path.join(_log_dir, "debug_api.log"), "w", encoding="utf-8")
    def log(msg):
        log_file.write(msg + "\n")
        log_file.flush()
    plot_messages = [{"role": "system", "content": config.system_prompt}]

    # RAG Word 로드
    rag_word = "(단어 목록 없음)"
    #rag_word_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "rag_word.txt")
    #try:
    #    with open(rag_word_path, "r", encoding="utf-8") as f:
    #        rag_word = f.read().strip()
    #except FileNotFoundError:
    #    pass
    config.rag_word = rag_word

    # 타락 가이드 매핑
    corruption_guides = getattr(config, 'corruption_guides', [])
    partner_corruption_guides = getattr(config, 'partner_corruption_guides', [])

    def _parse_ep_from_guide(guide, current_ep, guide_num, total_eps):
        match = re.search(r'EPISODE (\d+):', guide)
        return int(match.group(1)) if match else current_ep

    def _extract_dollar_actions(text):
        return 0

    guides_text_lines = []
    partner_guides_text_lines = []
    ep_corruption_guides_map = {}
    config.special_writing_req = {}

    current_ep = 1
    for idx, guide in enumerate(corruption_guides):
        if idx > 0 and idx % config.guide_num == 0:
            current_ep = min(current_ep + 1, total_episodes)
        ep_assign = min(_parse_ep_from_guide(guide, current_ep, config.guide_num, total_episodes), total_episodes)
        guides_text_lines.append(f"  EPISODE {ep_assign}: #{guide}")
        if ep_assign not in ep_corruption_guides_map:
            ep_corruption_guides_map[ep_assign] = {"protagonist": [], "partner": []}
        ep_corruption_guides_map[ep_assign]["protagonist"].append(guide)
        # $가 붙은 행동 keyword 추출하여 config.special_writing_req에 저장
        dollar_actions = _extract_dollar_actions(guide)
        if dollar_actions:
            if ep_assign not in config.special_writing_req:
                config.special_writing_req[ep_assign] = []
            config.special_writing_req[ep_assign].extend(dollar_actions)

    current_ep = 1
    for idx, guide in enumerate(partner_corruption_guides):
        if idx > 0 and idx % config.guide_num == 0:
            current_ep = min(current_ep + 1, total_episodes)
        ep_assign = min(_parse_ep_from_guide(guide, current_ep, config.guide_num, total_episodes), total_episodes)
        partner_guides_text_lines.append(f"  EPISODE {ep_assign}: #{guide}")
        if ep_assign not in ep_corruption_guides_map:
            ep_corruption_guides_map[ep_assign] = {"protagonist": [], "partner": []}
        ep_corruption_guides_map[ep_assign]["partner"].append(guide)
        # $가 붙은 행동 keyword 추출하여 config.special_writing_req에 저장
        dollar_actions = _extract_dollar_actions(guide)
        if dollar_actions:
            if ep_assign not in config.special_writing_req:
                config.special_writing_req[ep_assign] = []
            config.special_writing_req[ep_assign].extend(dollar_actions)

    guides_text = "\n".join(guides_text_lines) if guides_text_lines else "(없음)"
    partner_guides_text = "\n".join(partner_guides_text_lines) if partner_guides_text_lines else "(없음)"
    config.ep_corruption_guides_map = ep_corruption_guides_map

    # -------------------------------------------------------------------------
    # 2. Master Setup Prompt
    # -------------------------------------------------------------------------
    if callback: callback("[1/3] 마스터 세계관 및 작성 가이드 주입 중...", {"total_episodes": total_episodes, "current_episode": 0, "status": "마스터 세계관 주입 중"})
    prompts = _load_prompts()
    master_setup_prompt = _build_prompt(
        prompts["master_setup"],
        theme_info=theme_info, inc_emphasis=inc_emphasis,
        template_name=template['name'], template_concept=template['concept'],
        template_flow=template['flow'], template_turning_point=template['turning_point'],
        template_corruption_style=template['corruption_style'], template_ending=template['ending'],
        jinshugai_info=jinshugai_info, breeds_info=breeds_info,
        protagonist_sheet=protagonist_sheet, partner_sheet=partner_sheet,
        relationship_desc=relationship_desc, name1=name1, persona_text=persona_text,
        phase1_end=phase1_end, phase2_start=phase2_start, phase2_end=phase2_end,
        phase3_start=phase3_start, phase3_end=phase3_end, phase4_start=phase4_start,
        total_episodes=total_episodes, phase_transition_text=phase_transition_text,
        rag_word=rag_word, guides_text=guides_text, partner_guides_text=partner_guides_text,
        first_event=getattr(config, 'first_event', ''),
        second_event=getattr(config, 'second_event', ''),
        import_point=getattr(config, 'import_point', '')
    )
    result = call_openai_for_plot(master_setup_prompt, messages=plot_messages, log_fn=log)

    # -------------------------------------------------------------------------
    # character_sheet log 파일 초기화
    # -------------------------------------------------------------------------
    cs_log_file = open(os.path.join(_log_dir, "debug_character_sheet.log"), "w", encoding="utf-8")

    # episode_content 초기화 (파일 저장을 위해)
    if not hasattr(config, 'episode_content') or config.episode_content is None:
        config.episode_content = [""] * total_episodes

    # -------------------------------------------------------------------------
    # 3. EP1
    # -------------------------------------------------------------------------
    # EP1 작성 전: 초기 character_sheet를 EP1로 저장 (에피소드 1 작성 시 사용)
    if callback: callback(f"[캐릭터 시트] EPISODE 1 초기 시트 저장...", {"total_episodes": total_episodes, "current_episode": 1, "status": "EPISODE 1 시트 저장"})
    config.episode_protagonist_sheets[0] = protagonist_sheet
    config.episode_partner_sheets[0] = partner_sheet
    _save_character_sheet_json({"protagonist": _parse_sheet_to_dict(protagonist_sheet),
                                 "partner": _parse_sheet_to_dict(partner_sheet)}, 1, plot_hash)
    cs_log_file.write(f"{'=' * 60}\n")
    cs_log_file.write(f"[Episode 1] 초기 캐릭터 시트\n")
    cs_log_file.write(f"{'=' * 60}\n")
    cs_log_file.write(f"\n### 주인공 시트 ###\n\n{protagonist_sheet}\n")
    cs_log_file.write(f"\n### 상대방 시트 ###\n\n{partner_sheet}\n")
    cs_log_file.write(f"\n{'-' * 60}\n\n")
    cs_log_file.flush()

    # EP1 작성
    if callback: callback("[2/3] 에피소드 생성 중... (EPISODE 1)", {"total_episodes": total_episodes, "current_episode": 1, "status": "EPISODE 1 생성 중"})
    prompt_ep1 = _build_prompt(prompts["ep1_prompt"], name1=name1, name2=name2)
    result = call_openai_for_plot(prompt_ep1, messages=plot_messages, log_fn=log)
    ep1_text = result.strip()
    all_episodes = ep1_text
    config.episode_content[0] = ep1_text

    # EP1 생성 후 character_sheet 업데이트 → EP2로 저장 (다음 에피소드용)
    if callback: callback(f"[캐릭터 시트] EPISODE 2 시트 생성 (EP1 반영)...", {"total_episodes": total_episodes, "current_episode": 1, "status": "EPISODE 2 시트 생성"})
    new_proto, new_part = _update_character_sheets_via_api(
        ep1_text, 2, protagonist_sheet, partner_sheet, name1, name2, log_fn=log
    )
    config.episode_protagonist_sheets[1] = new_proto
    config.episode_partner_sheets[1] = new_part
    cs_log_file.write(f"{'=' * 60}\n")
    cs_log_file.write(f"[Episode 2] 캐릭터 시트 (EP1 반영)\n")
    cs_log_file.write(f"{'=' * 60}\n")
    cs_log_file.write(f"\n### 주인공 시트 ###\n\n{new_proto}\n")
    cs_log_file.write(f"\n### 상대방 시트 ###\n\n{new_part}\n")
    cs_log_file.write(f"\n### 에피소드 요약 ###\n\n{ep1_text}\n")
    cs_log_file.write(f"\n{'-' * 60}\n\n")
    cs_log_file.flush()
    # EP1 파일 저장
    if plot_hash:
        llm_novel_gui_func.save_episodes_and_sheets_to_progress(plot_hash)

    # -------------------------------------------------------------------------
    # 4. EP2 ~ EP_N
    # -------------------------------------------------------------------------
    ep_events_map = {}
    if progression_events:
        event_to_ep = {int(k): v for k, v in VARS["event_to_ep"].items()}
        for event in progression_events:
            ep_idx = event_to_ep.get(event['index'])
            if ep_idx:
                ep_events_map.setdefault(ep_idx, []).append(event)

    phase_ep_map = {}
    for pt in phase_transition_text.split('\n'):
        pt = pt.strip()
        if pt.startswith('[Ep.') and '전환:' in pt:
            try:
                ep_num = int(pt.split('Ep.')[1].split(']')[0])
                phase_ep_map[ep_num] = pt
            except (ValueError, IndexError):
                pass

    # slow_burn 범위를 config.intro_end_ep에 연동 (theme_gen_auto.py와 같은 조건)
    # intro_end_ep 이전까지는 평범한 러브코메디 톤 (slowburn 프롬프트 사용)
    intro_end = getattr(config, 'intro_end_ep', None)
    if intro_end is not None:
        slow_burn_start = 1
        slow_burn_end = intro_end
    else:
        # fallback: 기존 variables.json 설정 사용
        tone_ranges = VARS["tone_ranges"]
        slow_burn_start = tone_ranges["slow_burn"]["ep_start"]
        slow_burn_end = tone_ranges["slow_burn"]["ep_end"]

    for i in range(2, total_episodes + 1):
        if callback: callback(f"[2/3] 에피소드 {i}/{total_episodes} 생성 중...", {"total_episodes": total_episodes, "current_episode": i, "status": f"에피소드 {i} 생성 중"})
        level_desc = _get_level_description(i, total_episodes)

        guides_desc = ""
        if i in ep_corruption_guides_map:
            ep_guides = ep_corruption_guides_map[i]
            guide_parts = []
            if ep_guides["protagonist"]:
                guide_parts.append(f"  - 주인공 가이드: {', '.join([f'#{g}' for g in ep_guides['protagonist']])}")
            if ep_guides["partner"]:
                guide_parts.append(f"  - 상대방 가이드: {', '.join([f'#{g}' for g in ep_guides['partner']])}")
            guides_desc = f"\n   * [타락 가이드 융합, 가장 중요함!] 아래 키워드를 기승전결 작성에 무조건 반영하세요!:\n" + "\n".join(guide_parts)

        special_desc = ""
        if i in config.special_writing_req and config.special_writing_req[i]:
            special_desc = f"\n   * [특별 묘사 요청] 다음 항목을 반드시 포함하여 에로틱하게 묘사할 것: {', '.join(config.special_writing_req[i])}"

        events_desc = ""
        if i in ep_events_map:
            events_desc = f"\n7. 이 에피소드 포함 사건:\n" + "\n".join([f"   - {e['stage']}" for e in ep_events_map[i]])

        phase_desc = f"\n5. Phase Transition: {phase_ep_map[i]}" if i in phase_ep_map else ""
        resistance_desc = ""
        if i in resistance_positions:
            resistance_desc = f"\n6. 이 에피소드에서는 이성으로는 필사적으로 거부하며 눈물을 흘리지만, 육체는 이미 '그분'의 은총에 길들여져 스스로 쾌락을 갈구하는 모순적인 배덕감을 강렬하게 묘사하세요."
        ending_desc = f"\n7. 마지막 에피소드이므로 템플릿의 결말에 완벽히 도달하여 빔보/펨보이로서의 영원한 타락을 선언해야 합니다." if i == total_episodes else ""

        ep_uni_act, ep_uni_sen, ep_uni_emo = _get_ep_tags(i, total_episodes, classified_tags, UNIVERSAL_TAGS_SOFT)
        ep_atmosphere_tags = selected_actions + ep_uni_act + ep_uni_sen + ep_uni_emo

        # 에피소드 분할 범위에 따른 장르/톤 설정
        # config에서 theme_gen_auto.py가 저장한 에피소드 분할 범위 활용
        crisis_start = getattr(config, 'crisis_start_ep', None)
        crisis_end = getattr(config, 'crisis_end_ep', None)
        ending_start = getattr(config, 'ending_start_ep', None)

        genre_tone = ""
        if intro_end is not None and i <= intro_end:
            genre_tone = "평범한 러브코메디 라이트 노벨"
        elif crisis_start is not None and crisis_end is not None and crisis_start <= i <= crisis_end:
            genre_tone = "살짝 엣찌한 러브코메디 라이트 노벨(청소년향)"
        elif ending_start is not None and i >= ending_start:
            genre_tone = "조건 더 엣찌한 청년향 러브코메디 라이트 노벨"

        if slow_burn_start <= i <= slow_burn_end:
            prompt_tpl = prompts["epi_prompt_slowburn"]
        else:
            prompt_tpl = prompts["epi_prompt_normal"]

        prompt_epi = _build_prompt(
            prompt_tpl, i=i, **{'i-1': i-1}, guides_desc=guides_desc, special_desc=special_desc,
            level_desc=level_desc, name1=name1, name2=name2, genre_tone=genre_tone
        )
        ep_result = call_openai_for_plot(prompt_epi, messages=plot_messages, log_fn=log)
        ep_text = ep_result.strip()
        all_episodes += "\n\n" + ep_text

        # EP{i} 생성 후 character_sheet 업데이트 → EP{i+1}로 저장 (다음 에피소드용)
        if callback: callback(f"[캐릭터 시트] EPISODE {i+1} 시트 생성 (EP{i} 반영)...", {"total_episodes": total_episodes, "current_episode": i, "status": f"EPISODE {i+1} 시트 생성"})
        current_proto = config.episode_protagonist_sheets[i - 2]
        current_part = config.episode_partner_sheets[i - 2]
        new_proto, new_part = _update_character_sheets_via_api(
            ep_text, i + 1, current_proto, current_part, name1, name2, log_fn=log
        )
        config.episode_protagonist_sheets[i - 1] = new_proto
        config.episode_partner_sheets[i - 1] = new_part
        config.episode_content[i - 1] = ep_text
        cs_log_file.write(f"{'=' * 60}\n")
        cs_log_file.write(f"[Episode {i+1}] 캐릭터 시트 (EP{i} 반영)\n")
        cs_log_file.write(f"{'=' * 60}\n")
        cs_log_file.write(f"\n### 주인공 시트 ###\n\n{new_proto}\n")
        cs_log_file.write(f"\n### 상대방 시트 ###\n\n{new_part}\n")
        cs_log_file.write(f"\n### 에피소드 요약 ###\n\n{ep_text}\n")
        cs_log_file.write(f"\n{'-' * 60}\n\n")
        cs_log_file.flush()
        # EP{i} 파일 저장
        plot_hash = getattr(config, 'plot_hash', '')
        if plot_hash:
            llm_novel_gui_func.save_episodes_and_sheets_to_progress(plot_hash)

    # -------------------------------------------------------------------------
    # 5. 에이전트 리뷰 및 수정
    # -------------------------------------------------------------------------
    if callback: callback("[3/3] 악덕 편집자 리뷰 및 수정 중...", {"total_episodes": total_episodes, "current_episode": total_episodes, "status": "에이전트 리뷰 중"})
    review_prompt = _build_prompt(
        prompts["review_prompt"],
        half_episodes=total_episodes // 2, theme_info=theme_info,
        name1=name1, age1=age1, job1=job1, name2=name2, age2=age2, job2=job2,
        corruption_elements=config.corruption_elements, all_episodes=all_episodes
    )
    feedback = call_openai_for_client(prompt_text=review_prompt, log_fn=log)

    def parse_feedback_per_episode(feedback_text, total_ep):
        ep_feedbacks = {}
        lines = feedback_text.split("\n")
        current_ep = None
        current_lines = []
        for line in lines:
            stripped = line.strip()
            match = re.match(r'(?:###\s*|##\s*|\*\*\s*)?EP(?:ISODE)?\s*(\d+)\s*[:\uff1a\s]*(.*)', stripped, re.IGNORECASE)
            if match:
                if current_ep is not None:
                    combined = "\n".join(current_lines).strip()
                    if combined:
                        ep_feedbacks[current_ep] = combined
                current_ep = int(match.group(1))
                current_lines = [match.group(2).strip()] if match.group(2).strip() else []
            elif current_ep is not None and stripped:
                current_lines.append(stripped)
        if current_ep is not None:
            combined = "\n".join(current_lines).strip()
            if combined:
                ep_feedbacks[current_ep] = combined
        for i in range(1, total_ep + 1):
            if i not in ep_feedbacks:
                ep_feedbacks[i] = "(수정사항 없음 - 원문 유지)"
        return ep_feedbacks

    ep_feedbacks = parse_feedback_per_episode(feedback, total_episodes)
    original_episodes = parse_episodes(all_episodes, total_episodes)
    refined_all_episodes = ""

    for i in range(1, total_episodes + 1):
        if callback: callback(f"[수정 반영] 에피소드 {i}/{total_episodes} 수정 중...", {"total_episodes": total_episodes, "current_episode": i, "status": f"에피소드 {i} 수정 중"})
        my_feedback = ep_feedbacks.get(i, "(수정사항 없음)")
        if "수정사항 없음" in my_feedback or "NONE" in my_feedback.upper():
            result = original_episodes[i-1] if i-1 < len(original_episodes) else ""
        else:
            refine_prompt = _build_prompt(
                prompts["refine_prompt"],
                i=i, my_feedback=my_feedback,
                original_episode=original_episodes[i-1] if i-1 < len(original_episodes) else ''
            )
            result = call_openai_for_plot(refine_prompt, messages=plot_messages, log_fn=log)

        headered_result = f"##EPISODE {i}: {result}" if result and not result.strip().startswith(f"##EPISODE {i}") and not result.strip().startswith(f"## EPISODE {i}") else result
        if refined_all_episodes:
            refined_all_episodes += "\n\n" + headered_result.strip()
        else:
            refined_all_episodes = headered_result.strip()

    episodes = parse_episodes(refined_all_episodes, total_episodes)

    if not episodes or len(episodes) < total_episodes:
        retry_prompt = "\n출력 형식을 반드시 지켜주세요. EPISODE 1:, EPISODE 2: 형식으로 정확히 " + str(total_episodes) + "줄을 출력하세요."
        if callback: callback("[추가] 재시도 중 (에피소드 부족)...", {"total_episodes": total_episodes, "current_episode": total_episodes, "status": "재시도 중"})
        result = call_openai_for_plot(retry_prompt, messages=plot_messages, log_fn=log)
        episodes = parse_episodes(result, total_episodes)

    if callback: callback("[완료] 에피소드 후처리 중...", {"total_episodes": total_episodes, "current_episode": total_episodes, "status": "후처리 중"})
    refined_episodes = review_and_refine(episodes, template, resistance_positions, total_episodes)

    cs_log_file.close()
    log_file.close()
    return "\n".join(refined_episodes)


# =============================================================================
# 유틸리티 함수들
# =============================================================================

def parse_episodes(text, total_episodes):
    episodes = {}
    lines = text.split("\n")
    current_ep_num = None
    current_ep_lines = []
    ep_header_pattern = re.compile(r'(?:##\s*)?(?:\*\*)?EP(?:ISODE)?\s*(\d+)(?:\*\*)?\s*[#:]?\s*(.*)', re.IGNORECASE)
    for line in lines:
        stripped = line.strip()
        match = ep_header_pattern.match(stripped)
        if match:
            if current_ep_num is not None and current_ep_lines:
                episodes[current_ep_num] = "\n".join(current_ep_lines).strip()
            current_ep_num = int(match.group(1))
            rest = match.group(2).strip().rstrip('*').rstrip('#').strip()
            current_ep_lines = [rest] if rest else []
        elif current_ep_num is not None and stripped:
            current_ep_lines.append(stripped)
    if current_ep_num is not None and current_ep_lines:
        episodes[current_ep_num] = "\n".join(current_ep_lines).strip()

    episodes_list = []
    for i in range(1, total_episodes + 1):
        if i in episodes:
            episodes_list.append(episodes[i])
        else:
            episodes_list.append("")
    if not any(ep.strip() for ep in episodes_list):
        episodes_list = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith("##") and not line.startswith("//"):
                episodes_list.append(line)
        if len(episodes_list) > total_episodes:
            episodes_list = episodes_list[:total_episodes]
        elif len(episodes_list) < total_episodes:
            episodes_list.extend([""] * (total_episodes - len(episodes_list)))
    return episodes_list


def review_and_refine(episodes, template, resistance_positions, total_episodes):
    refined = []
    for i, ep in enumerate(episodes):
        ep_num = i + 1
        if not ep.strip():
            if ep_num == 1:
                ep = f"{template['flow'].split(' -> ')[0]}로 시작하는 일상"
            elif ep_num == total_episodes:
                ep = f"{template['ending']}에 도달"
            else:
                ep = f"이성이 흐려지고 쾌락에 타락하는 과정 진행"
        if ep_num in resistance_positions:
            if "저항" not in ep and "버티" not in ep and "거부" not in ep and "도망" not in ep:
                ep = f"{ep} (마지막 남은 이성으로 살짝 저항하지만 엣찌해짐)"
        refined.append(f"##EPISODE {ep_num}: {ep}")
    return refined


def get_template_list():
    lines = ["=== 진슈가이 타락 스토리 10대 템플릿 ===\n"]
    for tid, template in TEMPLATES.items():
        lines.append(f"{tid}. {template['name']}")
        lines.append(f"   컨셉: {template['concept']}")
        lines.append("")
    return "\n".join(lines)


def quick_plot_gen(template_id, total_episodes=12, theme_msg=None, callback=None):
    if callback:
        callback(f"템플릿: {TEMPLATES[template_id]['name']}", {"total_episodes": total_episodes, "current_episode": 0, "status": "템플릿 로드 중"})
    result = plot_gen_extended(template_id, total_episodes, theme_msg, callback=callback)
    if callback:
        callback("완료", {"total_episodes": total_episodes, "current_episode": total_episodes, "status": "완료"})
    return result
