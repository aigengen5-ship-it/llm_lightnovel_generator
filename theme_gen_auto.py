import os
import sys
import io
import json
import yaml
import re
import random
import logging
import config
import character_setup
from persona import BREEDS_DATA, generate_ultimate_heroine_progression, get_stage_description
from openAPI_control import call_openai_for_client, call_openai_for_plot

# 로거 설정 (theme_gen_auto.log)
_logger = logging.getLogger("theme_gen_auto")
_logger.setLevel(logging.INFO)
_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
os.makedirs(_log_dir, exist_ok=True)
_log_handler = logging.FileHandler(os.path.join(_log_dir, "theme_gen_auto.log"), encoding="utf-8")
_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
_logger.addHandler(_log_handler)

# =====================================================================
# 데이터 로드 헬퍼 (theme/ 디렉토리 YAML 파일들)
# =====================================================================
_THEME_DIR = os.path.join(os.path.dirname(__file__), "theme")


def _load_theme_yaml(filename):
    """theme/ 디렉토리에서 YAML 파일 로드"""
    filepath = os.path.join(_THEME_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_elements():
    """theme/elements.yaml 로드 (corruption_types, body_changes 등)"""
    return _load_theme_yaml("elements.yaml")


def _load_triggers():
    """theme/triggers.yaml 로드 (first_triggers, relationships 등)"""
    return _load_theme_yaml("triggers.yaml")


def _load_prompts():
    """theme/prompts.txt 로드 (======key====== 형식 평문 파싱)"""
    filepath = os.path.join(_THEME_DIR, "prompts.txt")
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    parsed = {}
    # ======key====== 형식으로 구분된 섹션 파싱
    parts = re.split(r"======([^=]+)======", content)
    # parts: ['', key1, content1, key2, content2, ...]
    for i in range(1, len(parts), 2):
        key = parts[i].strip()
        value = parts[i + 1].rstrip("\n")
        parsed[key] = value
    return parsed


def _load_theme_templates():
    """theme/theme_templates.yaml 로드 (11개 ID별 상세 세팅 포함)"""
    data = _load_theme_yaml("theme_templates.yaml")
    return data["jinshugai_templates"]


def _resolve_template(template_text, name, name2):
    """템플릿 문자열에서 {name}, {name2} 플레이스홀더 치환"""
    return template_text.replace("{name}", name).replace("{name2}", name2)


def _build_prompt(template: str, **kwargs) -> str:
    """prompt 템플릿에 변수를 치환하여 완성된 prompt 반환"""
    return template.format(**kwargs)


def theme_gen_auto(story_info: str, num_episodes: int = 10, log_fn=None) -> dict:
    """
    자동 테마 생성 파이프라인

    Args:
        story_info: 스토리 정보
        num_episodes: 에피소드 수 (기본 10)
        log_fn: 추가 로깅 함수 (선택사항, GUI 통합용)

    Returns:
        dict
    """

    def _log(msg):
        _logger.info(msg)
        if log_fn:
            log_fn(msg)

    # =====================================================================
    # 1. JINSHUGAI_TEMPLATES 중 하나 선택 (data/theme_templates.json)
    # =====================================================================
    JINSHUGAI_TEMPLATES = _load_theme_templates()

    # 테스트용: id=1 고정 (모든 ID를 순회 테스트할 때 주석 해제)
    # config.selected_jinshugai_id가 지정되었으면 사용, 없으면 랜덤
    selected_jinshugai_id = getattr(config, 'selected_jinshugai_id', None)
    if selected_jinshugai_id is None:
        selected_jinshugai_id = random.randint(1, 11)

    selected_jinshugai = [t for t in JINSHUGAI_TEMPLATES if t["id"] == selected_jinshugai_id]
    if not selected_jinshugai:
        selected_jinshugai = [JINSHUGAI_TEMPLATES[0]]

    # 선택된 템플릿의 ID별 세팅 추출
    template_setting = selected_jinshugai[0]
    id_target_relationships = template_setting.get("target_relationships", [])
    id_protagonist_job_keywords = template_setting.get("protagonist_job_keywords", [])
    id_opponent_job_keywords = template_setting.get("opponent_job_keywords", [])
    id_first_triggers = template_setting.get("first_triggers", [])
    id_second_triggers = template_setting.get("second_triggers", [])
    id_protagonist_hidden_jobs = template_setting.get("protagonist_hidden_jobs", [])
    id_daily_corruption_changes = template_setting.get("daily_corruption_changes", [])

    # import_point 읽기 (중요포인트)
    id_import_point = template_setting.get("import_point", "")
    config.import_point = id_import_point

    # 첫 이벤트, 가장 중요!!!!
    id_first_event = template_setting.get("first_event", [])
    id_second_event = template_setting.get("second_event", [])
    first_event = random.choice(id_first_event)
    second_event = random.choice(id_second_event)

    # intermediate_phase가 있으면 2-3개 선택
    id_intermediate_phase = template_setting.get("intermediate_phase", [])
    if id_intermediate_phase:
        id_intermediate_phase = random.sample(id_intermediate_phase, min(random.randint(2, 3), len(id_intermediate_phase)))
    else:
        id_intermediate_phase = []

    # endings 중 1개 선택
    id_endings = template_setting.get("endings", [])
    if id_endings:
        id_selected_ending = random.choice(id_endings)
    else:
        id_selected_ending = ""

    # daily_corruption_changes도 2-3개만 선택
    if id_daily_corruption_changes:
        id_daily_corruption_changes = random.sample(id_daily_corruption_changes, min(random.randint(2, 3), len(id_daily_corruption_changes)))

    # =====================================================================
    # resistance_reasons / corruption_reasons 처리
    # 1) resistance를 랜덤하게 고름
    # 2) 만일 #가 있으면 corruption은 # split한 다음 문장
    # 3) 아니라면 corruption_reasons를 랜덤하게 고름
    # =====================================================================
    id_resistance_reasons = template_setting.get("resistance_reasons", [])
    id_corruption_reasons = template_setting.get("corruption_reasons", [])

    # 1) resistance 랜덤 선택
    selected_resistance = random.choice(id_resistance_reasons) if id_resistance_reasons else ""

    # 2) #가 있으면 split, 3) 없으면 corruption 랜덤 선택
    if selected_resistance and "#" in selected_resistance:
        # # split: 전부는 resistance, 후부는 corruption
        parts = selected_resistance.split("#", 1)
        selected_resistance = parts[0].strip()
        selected_corruption_reason = parts[1].strip()
    else:
        selected_corruption_reason = random.choice(id_corruption_reasons) if id_corruption_reasons else ""

    config.resistance_reason = selected_resistance
    config.corruption_reason = selected_corruption_reason
    config.first_event = first_event
    config.second_event = second_event

    # =====================================================================
    # 3. 직업 및 나이 설정 (theme_raw/job.txt, theme_raw/job2.txt)
    # =====================================================================
    def _parse_job_file(filepath):
        """job 파일 읽어서 (직업, 성별, min_age, max_age) 튜플 리스트 반환"""
        jobs = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 4:
                    try:
                        job = {
                            'name': parts[0],
                            'gender': parts[1],
                            'age_min': int(parts[2]),
                            'age_max': int(parts[3])
                        }
                        jobs.append(job)
                    except ValueError:
                        continue
        return jobs

    job_file = os.path.join(os.path.dirname(__file__), "data", "job.txt")
    job2_file = os.path.join(os.path.dirname(__file__), "data", "job2.txt")

    # inc_flag=1: 혈연관계 설정 (성별, 직업, 나이 모두 설정)
    if getattr(config, 'inc_flag', 0) == 1:
        character_setup.set_inc_relationship()
    else:
        # 기본 성별 설정: 주인공=여성, 상대방=남성
        config.sex = "여자"
        config.sex2 = "남자"

    def _filter_jobs_by_gender(jobs, gender):
        """성별에 맞는 직업 필터링 (남/여 또는 남/여 모두 포함)"""
        filtered = []
        for job in jobs:
            if job['gender'] in (gender, "남/여"):
                filtered.append(job)
        # 필터링 결과가 없으면 전체 사용
        return filtered if filtered else jobs

    def _filter_jobs_by_keywords(jobs, keywords):
        """키워드 목록에 매칭되는 직업 필터링 (키워드 중 하나라도 포함되면 통과)"""
        if not keywords:
            return jobs
        filtered = []
        for job in jobs:
            for keyword in keywords:
                if keyword in job['name']:
                    filtered.append(job)
                    break
        return filtered if filtered else jobs

    # 주인공 직업/나이 설정
    if not (getattr(config, 'inc_flag', 0) == 1):
        # cmd_job이 설정되어 있으면 랜덤 설정 건너뜀
        if getattr(config, 'cmd_job', None) is None:
            job_list = _parse_job_file(job_file)
            if job_list:
                job_list_filtered = _filter_jobs_by_gender(job_list, config.sex)
                # ID별 직업 키워드 필터 적용
                if id_protagonist_job_keywords:
                    job_list_filtered = _filter_jobs_by_keywords(job_list_filtered, id_protagonist_job_keywords)
                selected_job = random.choice(job_list_filtered)
                config.job = selected_job['name']
                # protagonist_job_keywords에 해당하면 그대로, 아니면 protagonist_hidden_jobs 추가
                if id_protagonist_hidden_jobs:
                    job_has_keyword = any(kw in config.job for kw in id_protagonist_job_keywords) if id_protagonist_job_keywords else False
                    if not job_has_keyword:
                        available_hidden = [hj for hj in id_protagonist_hidden_jobs if hj not in id_protagonist_job_keywords]
                        if available_hidden:
                            hidden_job = random.choice(available_hidden)
                            config.job = f"{config.job}({hidden_job})"
                config.age = random.randint(selected_job['age_min'], selected_job['age_max'])
            else:
                config.job = "평범한 직업"
                config.age = 25

    # 상대방 직업/나이 설정
    if not (getattr(config, 'inc_flag', 0) == 1):
        # cmd_job2가 설정되어 있으면 랜덤 설정 건너뜀
        if getattr(config, 'cmd_job2', None) is None:
            job2_list = _parse_job_file(job2_file)
            if job2_list:
                job2_list_filtered = _filter_jobs_by_gender(job2_list, config.sex2)
                # ID별 직업 키워드 필터 적용
                if id_opponent_job_keywords:
                    job2_list_filtered = _filter_jobs_by_keywords(job2_list_filtered, id_opponent_job_keywords)
                selected_job2 = random.choice(job2_list_filtered)
                config.job2 = selected_job2['name']
                config.age2 = random.randint(selected_job2['age_min'], selected_job2['age_max'])
            else:
                config.job2 = "평범한 직업"
                config.age2 = 25

    # =====================================================================
    # 3-0. body_dic 초기화 (archetype_setup 호출 전 필수)
    # =====================================================================
    character_setup.character_init(config.sex, config.json_value)

    # =====================================================================
    # 3-0-1. 아키타입 적용 (config.job 기반)
    # =====================================================================
    character_setup.archetype_setup(config.json_value)

    # =====================================================================
    # 3-1. 상대방 외모 설정
    # =====================================================================
    # 1) 체형
    config.appearance2 = ""
    body_types = ["뚱뚱함", "보통", "마름"]
    selected_body_type = random.choice(body_types)
    config.appearance2 = selected_body_type

    # 2) 수염
    has_beard = random.choice(["수염있음", "수염없음"])
    config.appearance2 += ", " + has_beard

    # 3) 머리색 (기본 검정, 또는 대머리)
    hair_colors = ["검정", "갈색", "회색", "흰색", "금발", "밤색"]
    if random.random() < 0.1:  # 10% 확률로 대머리
        selected_hair = "대머리"
    else:
        selected_hair = random.choice(hair_colors)
    config.appearance2 += ", " + selected_hair

    # 4) 생김새
    look = random.choice(["추남", "평범", "잘생김"])
    config.appearance2 += ", " + look

    # 5) 말투
    talking_style2 = random.choice(["평범하게 말함", "천박하게 말함", "정중하게 말함"])
    config.talking_style2 = talking_style2

    # 6) 성격
    personality2 = random.choice(["착함"])
    config.personality2 = personality2

    # 4) 복장 (직업에 맞게) - theme/elements.yaml
    elements = _load_elements()
    outfit_by_job = elements["outfit_by_job"]
    default_outfit = elements.get("default_outfit", "캐주얼")

    # 직업명에 포함된 키워드로 복장 매칭
    selected_outfit = default_outfit
    job2_name = config.job2
    for keyword, outfit in outfit_by_job.items():
        if keyword in job2_name:
            selected_outfit = outfit
            break

    config.outfit2 = selected_outfit

    # =====================================================================
    # 3-2. 이름 설정
    # =====================================================================
    character_setup.name_define()
    config.nationality = "japanese"
    config.nationality2 = "japanese"


    # =====================================================================
    # 4. 관계 설정 (ID별 target_relationships 우선, 없으면 범용)
    # =====================================================================
    triggers = _load_triggers()
    RELATIONSHIPS = triggers["relationships"]

    if id_target_relationships:
        candidates = id_target_relationships
        if getattr(config, 'inc_flag', 0) == 1:
            candidates = [r for r in candidates if r != "모르는 사이"]
        selected_relationship = random.choice(candidates) if candidates else random.choice(RELATIONSHIPS)
    elif getattr(config, 'inc_flag', 0) == 1:
        # inc_flag=1: 가족애 모드 → 친밀한 관계 우선, 모르는 사이 제외
        family_relationships = [r for r in RELATIONSHIPS if r in ("친밀한 관계", "보통인 관계")]
        selected_relationship = random.choice(family_relationships) if family_relationships else random.choice(RELATIONSHIPS)
    else:
        selected_relationship = random.choice(RELATIONSHIPS)
    config.relationship = selected_relationship

    # =====================================================================
    # 4. 여주인공 Progression 생성 (persona.py)
    # =====================================================================
    old_stdout = sys.stdout
    sys.stdout = captured_persona = io.StringIO()
    try:
        if random.randint(0,1) == 0:
            persona_result = generate_ultimate_heroine_progression(
                num_episodes=num_episodes, relationship=selected_relationship)
        else:
            persona_result = generate_ultimate_heroine_progression(
                num_episodes=num_episodes, fixed_breeds="yes", relationship=selected_relationship)
    except Exception as e:
        _log(f"[persona] 오류 발생: {e}")
        sys.stdout = old_stdout
        raise
    finally:
        sys.stdout = old_stdout

    persona_text = captured_persona.getvalue().strip()
    config.persona_text = persona_text
    config.persona_result = persona_result

    # =====================================================================
    # 5. 첫 만남 트리거 (ID별 우선, 없으면 범용 폴백)
    # =====================================================================
    FIRST_TRIGGERS = triggers["first_triggers"]

    # ID별 트리거가 있으면 사용, 없으면 범용 트리거 사용
    if id_first_triggers:
        available_first_triggers = id_first_triggers
    else:
        available_first_triggers = [_resolve_template(t, config.name, config.name2) for t in FIRST_TRIGGERS]

    selected_trigger = random.choice(available_first_triggers)
    config.first_trigger = selected_trigger

    # 두 번째 트리거 (ID별 우선, 없으면 범용 폴백)
    SECOND_TRIGGERS = triggers["second_triggers"]

    if id_second_triggers:
        available_second_triggers = id_second_triggers
    else:
        available_second_triggers = SECOND_TRIGGERS

    selected_trigger = random.choice(available_second_triggers)
    config.second_trigger = selected_trigger

    # =====================================================================
    # 6. 관계 발전 (첫 트리거 이후 관계성 변화)
    # =====================================================================
    RELATIONSHIP_DEVELOPMENTS = triggers["relationship_developments"]

    selected_developments = random.sample(RELATIONSHIP_DEVELOPMENTS, 2)
    config.relationship_development = selected_developments

    # =====================================================================
    # 7. 변화 요소 및 신체 변화 선택 (위기 전 징조용)
    # =====================================================================
    CORRUPTION_TYPES = elements["corruption_types"]

    # desc_template의 {name2} 플레이스홀더 치환
    CORRUPTION_TYPES_RESOLVED = []
    for ct in CORRUPTION_TYPES:
        CORRUPTION_TYPES_RESOLVED.append({
            "name": ct["name"],
            "desc": _resolve_template(ct["desc_template"], config.name, config.name2)
        })

    BODY_CHANGES = elements["body_changes"]

    # 변화 요소 1개 선택 (음란화와 빗치화는 상호 배타적)
    selected_corruption = [random.choice(CORRUPTION_TYPES_RESOLVED)]

    # 신체 변화 1개 선택
    selected_body_change = random.choice(BODY_CHANGES)

    config.corruption_elements = selected_corruption
    config.body_change = selected_body_change

    corruption_text = " + ".join([c["name"] for c in selected_corruption])
    body_text = selected_body_change["name"]

    # =====================================================================
    # 7-1. 신체 변화의 징조 (관계 발전 후, 위기 전)
    # =====================================================================
    BODY_CHANGE_SIGNS = elements["body_change_signs"]

    body_signs = BODY_CHANGE_SIGNS.get(selected_body_change["name"], ["미묘한 신체 변화의 징조"])
    selected_sign = random.choice(body_signs)
    config.body_change_sign = selected_sign

    # =====================================================================
    # 7-1-1. 변화 인지 방식 랜덤 결정 (무의식적 vs 이성적 파악)
    # =====================================================================
    change_awareness_options = elements["change_awareness_options"]
    selected_awareness_raw = random.choice(change_awareness_options)
    config.change_awareness = _resolve_template(selected_awareness_raw, config.name, config.name2)

    # =====================================================================
    # 7-1-2. 쾌락에 따른 변화 Flow 랜덤 선택 (기승전결, guide 제작에 사용)
    # =====================================================================
    corruption_flows_raw = elements["corruption_flows"]
    corruption_flows = []
    for cf in corruption_flows_raw:
        corruption_flows.append({
            "name": cf["name"],
            "desc": cf["desc"],
            "flow": _resolve_template(cf["flow_template"], config.name, config.name2)
        })
    selected_corruption_flow = random.choice(corruption_flows)
    config.corruption_flow = selected_corruption_flow

    # =====================================================================
    # 7-2. 변화 가이드 랜덤 요소 (다양성 확보)
    # =====================================================================
    CORRUPTION_TONES = elements["corruption_tones"]
    INTERACTION_STYLES = elements["interaction_styles"]
    SENSORY_EMPHASIS = elements["sensory_emphasis"]
    INTERNAL_CONFLICTS = elements["internal_conflicts"]
    LOCATION_MOODS = elements["location_moods"]

    selected_tone = random.choice(CORRUPTION_TONES)
    selected_interaction = random.choice(INTERACTION_STYLES)
    selected_sensory = random.choice(SENSORY_EMPHASIS)
    selected_conflict = random.choice(INTERNAL_CONFLICTS)
    selected_location = random.choice(LOCATION_MOODS)

    # =====================================================================
    # 8. 두 번째 트리거 (위기 상황) - 해결은 항상 상대방
    # =====================================================================
    CRISIS_TRIGGERS = triggers["crisis_triggers"]

    selected_crisis = random.choice(CRISIS_TRIGGERS)
    config.crisis_trigger = selected_crisis

    # =====================================================================
    # 9. 진행도 사건 생성 (persona_result의 breeds 사용)
    # =====================================================================
    breed1_name = persona_result["breed_A"]
    breed1_data = BREEDS_DATA[breed1_name]
    breed2_name = persona_result["breed_B"]
    breed2_data = BREEDS_DATA[breed2_name]

    config.theme_breeds = [
        (breed1_name, breed1_data),
        (breed2_name, breed2_data)
    ]

    # persona_result의 episodes를 events로 재활용
    # matrix_desc, dynamic_ending_text 포함
    events = []
    for i, ep in enumerate(persona_result["episodes"]):
        jinshugai_template = selected_jinshugai[i % len(selected_jinshugai)]
        jinshugai_event = f"{jinshugai_template['name']} ({jinshugai_template['concept']})"

        event = {
            "index": ep["index"],
            "breed": ep["active_breed"],
            "trope": persona_result["trope_A" if ep["active_breed"] == persona_result["breed_A"] else "trope_B"],
            "stage": ep["animal_desc"],
            "matrix_desc": ep["matrix_desc"],
            "stage_name": ep["stage_name"],
            "breed_tag": ep["breed_tag"],
            "jinshugai": jinshugai_event,
            "progress": ep["t"],
        }
        # 마지막 이벤트에 결말 텍스트 추가
        if i == len(persona_result["episodes"]) - 1:
            event["ending_text"] = persona_result["dynamic_ending_text"]
        events.append(event)

    config.theme_events = events

    # =====================================================================
    # 10. abnormal_trigger.txt에서 비정상 트리거 선택
    # =====================================================================
    trigger_path = os.path.join(os.path.dirname(__file__), "data", "abnormal_trigger.txt")
    try:
        with open(trigger_path, "r", encoding="utf-8") as f:
            trigger_lines = [line.strip() for line in f if line.strip()]
        random_trigger = random.choice(trigger_lines)
        config.abnormal_trigger = random_trigger
    except (FileNotFoundError, Exception) as e:
        _log(f"[abnormal_trigger] 파일 오류: {e}. 기본값 '애정' 사용")
        random_trigger = "애정"
        config.abnormal_trigger = random_trigger

    # =====================================================================
    # 10-1. bimbo_costume.txt에서 복장 2개 랜덤 선택
    # =====================================================================
    costume_path = os.path.join(os.path.dirname(__file__), "data", "bimbo_costume.txt")
    try:
        with open(costume_path, "r", encoding="utf-8") as f:
            costume_lines = []
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # #으로 분리: 앞이 복장명, 뒤가 설명 (설명 미사용)
                if "#" in line:
                    costume_name = line.split("#", 1)[0].strip()
                else:
                    costume_name = line
                costume_lines.append(costume_name)
        selected_costumes = random.sample(costume_lines, min(2, len(costume_lines)))
        config.bimbo_clothes1 = selected_costumes[0]
        config.bimbo_clothes2 = selected_costumes[1] if len(selected_costumes) > 1 else selected_costumes[0]
    except (FileNotFoundError, Exception) as e:
        config.bimbo_clothes1 = "복장1"
        config.bimbo_clothes2 = "복장2"

    # =====================================================================
    # 12. 기-승-전-결 테마 생성 (LLM 호출)
    # =====================================================================
    prompts = _load_prompts()
    jinshugai_text = "\n".join([f"  - {t['id']}. {t['name']}: {t['concept']}" for t in selected_jinshugai])

    # =====================================================================
    # 12-1. 에피소드 분할 범위 계산 (기-승-전-결, +1/-1 랜덤 변동)
    # =====================================================================
    # 기본 비율: 기-승 40%, 전 40%, 결 20% (4:4:2)
    base_intro = int(num_episodes * 0.4)
    base_crisis = int(num_episodes * 0.4)
    base_ending = num_episodes - base_intro - base_crisis

    # 각 범위에 +1/-1 랜덤 변동 적용 (최소 1 보장)
    intro_episodes = max(1, base_intro + random.choice([-1, 0, 1]))
    crisis_episodes = max(1, base_crisis + random.choice([-1, 0, 1]))
    ending_episodes = num_episodes - intro_episodes - crisis_episodes
    ending_episodes = max(1, ending_episodes)

    # 범위 계산
    intro_start_ep = 1
    intro_end_ep = intro_episodes
    crisis_start_ep = intro_end_ep + 1
    crisis_end_ep = crisis_start_ep + crisis_episodes - 1
    ending_start_ep = crisis_end_ep + 1
    ending_end_ep = num_episodes

    _log(f"[EPISODE_SPLIT] 기-승: EP {intro_start_ep}~{intro_end_ep} ({intro_episodes}개)")
    _log(f"[EPISODE_SPLIT] 전: EP {crisis_start_ep}~{crisis_end_ep} ({crisis_episodes}개)")
    _log(f"[EPISODE_SPLIT] 결: EP {ending_start_ep}~{ending_end_ep} ({ending_episodes}개)")

    # config 전역변수에 에피소드 분할 범위 저장 (plot_gen.py, full_episode_gen.py에서 활용)
    config.intro_end_ep = intro_end_ep
    config.crisis_start_ep = crisis_start_ep
    config.crisis_end_ep = crisis_end_ep
    config.ending_start_ep = ending_start_ep
    config.ending_end_ep = ending_end_ep

    # 가이드 개수 계산
    guide_num = config.guide_num
    intro_guide_count = intro_episodes * guide_num
    crisis_guide_count = crisis_episodes * guide_num
    ending_guide_count = ending_episodes * guide_num

    events_text_parts = []
    events_text1_parts = []  # 기-승
    events_text2_parts = []  # 전
    events_text3_parts = []  # 결

    epi_num = 1
    for i, e in enumerate(events):
        line = (f"  EPISODE {e['index']}: {e['breed']} ({e['trope']})\n     현재 감정 상태: {e['stage_name']}\n"
                f"     행동 패턴 요약: {e['stage']}\n"
                f"     자세한 심리 상태: {e['matrix_desc']}")
        if "ending_text" in e:
            line += f"\n최종 결말의 {config.name}의 모습: {e['ending_text']}"

        if epi_num <= intro_end_ep:
            events_text1_parts.append(line)
        elif epi_num <= crisis_end_ep:
            events_text2_parts.append(line)
        else:
            events_text3_parts.append(line)

        events_text_parts.append(line)
        epi_num += 1

    events_text = "\n".join(events_text_parts)
    events_text1 = "\n".join(events_text1_parts)
    events_text2 = "\n".join(events_text2_parts)
    events_text3 = "\n".join(events_text3_parts)

    # 주인공 외모 정보 추출
    _body_dic = getattr(config, 'body_dic', None)
    theme_prompt = _build_prompt(prompts["theme_prompt"],
        story_info=story_info,
        name=config.name, job=config.job, sex=config.sex, age=config.age,
        name2=config.name2, job2=config.job2, sex2=config.sex2, age2=config.age2,
        hair_color=getattr(config, 'hair_color', '미설정'),
        hair_style=getattr(config, 'hair_style', '미설정'),
        eye_color=getattr(config, 'eye_color', '미설정'),
        skin_color=getattr(config, 'skin_color', '미설정'),
        face_style=getattr(config, 'face_style', '미설정'),
        acc=getattr(config, 'acc', '미설정'),
        breasts_size=_body_dic.get('breasts_size', ['미설정'])[config.breasts_size] if _body_dic and hasattr(config, 'breasts_size') else '미설정',
        hip_size=_body_dic.get('hip_size', ['미설정'])[config.hip_size] if _body_dic and hasattr(config, 'hip_size') else '미설정',
        body_size=_body_dic.get('body_size', ['미설정'])[config.body_size] if _body_dic and hasattr(config, 'body_size') else '미설정',
        appearance2=config.appearance2, outfit2=config.outfit2,
        talking_style2=config.talking_style2, personality2=config.personality2,
        selected_relationship=selected_relationship,
        first_event=first_event,
        second_event=second_event,
        first_trigger=config.first_trigger, second_trigger=config.second_trigger,
        relationship_development=', '.join(selected_developments),
        body_change_sign=selected_sign, crisis_trigger=selected_crisis,
        intermediate_phase_block=(f'\n## 중간 단계 변화 (기/승 단계에 배치하여 점진적 변화 묘사)\n' + '\n'.join([f"* {i+1}. {change}" for i, change in enumerate(id_intermediate_phase)])) if id_intermediate_phase else '',
        daily_corruption_changes_block=('\n'.join([f"* {i+1}. {change}" for i, change in enumerate(id_daily_corruption_changes)])) if id_daily_corruption_changes else '* (미설정)',
        resistance_reason=selected_resistance, corruption_reason=selected_corruption_reason,
        selected_ending=id_selected_ending,
        corruption_text=corruption_text,
        corruption_desc_text=' + '.join([c['desc'] for c in selected_corruption]),
        body_text=body_text, body_change_desc=selected_body_change['desc'],
        change_awareness=config.change_awareness,
        corruption_flow_name=config.corruption_flow['name'],
        corruption_flow_desc=config.corruption_flow['desc'],
        corruption_flow_flow=config.corruption_flow['flow'],
        jinshugai_text=jinshugai_text, events_text=events_text,
        genre_text=prompts.get("inc_flag_genre_text", prompts.get("genre_text", "")) if getattr(config, 'inc_flag', 0) == 1 else prompts.get("genre_text", ""),
        rel1_update=f"{config.name}은(는) {config.name2}의 {getattr(config, 'rel1', '')}입니다." if getattr(config, 'inc_flag', 0) == 1 and getattr(config, 'rel1', '') else "",
        import_point=config.import_point
    )
    rel1_update=f"{config.name}은(는) {config.name2}의 {getattr(config, 'rel1', '')}입니다." if getattr(config, 'inc_flag', 0) == 1 and getattr(config, 'rel1', '') else ""
    config.rel1_update = rel1_update

    # 1. 테마 생성 (대화 이력 시작)
    plot_messages = [
        {"role": "system", "content": config.system_prompt}
    ]
    theme_result = call_openai_for_plot(theme_prompt, messages=plot_messages, log_fn=_log)

    # =====================================================================
    # 13. 가이드 생성 (LLM 호출: 기-승-전-결 단계별 생성)
    # =====================================================================
    guides_count = num_episodes * config.guide_num
    corruption_desc_text = " + ".join([c["desc"] for c in selected_corruption])
    genre_text_val = prompts.get("inc_flag_genre_text", prompts.get("genre_text", "")) if getattr(config, 'inc_flag', 0) == 1 else prompts.get("genre_text", "")
    rel1_update_val = f"{config.name}은(는) {config.name2}의 {getattr(config, 'rel1', '')}입니다." if getattr(config, 'inc_flag', 0) == 1 and getattr(config, 'rel1', '') else ""
    config.rel1_update = rel1_update_val
    intermediate_block = (f'\n## 중간 단계 변화 (기/승 단계에 배치하여 점진적 변화 묘사)\n' + '\n'.join([f"* {i+1}. {change}" for i, change in enumerate(id_intermediate_phase)])) if id_intermediate_phase else ''
    daily_block = ('\n'.join([f"* {i+1}. {change}" for i, change in enumerate(id_daily_corruption_changes)])) if id_daily_corruption_changes else '* (미설정)'

    # 13-1. [기-승] Introduction (EP 1~intro_end_ep)
    _log(f"[GUIDES] [기-승] EP {intro_start_ep}~{intro_end_ep} 가이드 생성 시작...")
    introduction_prompt = _build_prompt(prompts["introduction_prompt"],
        story_info=story_info,
        name=config.name, job=config.job, sex=config.sex, age=config.age,
        name2=config.name2, job2=config.job2, sex2=config.sex2, age2=config.age2,
        hair_color=getattr(config, 'hair_color', '미설정'),
        hair_style=getattr(config, 'hair_style', '미설정'),
        eye_color=getattr(config, 'eye_color', '미설정'),
        skin_color=getattr(config, 'skin_color', '미설정'),
        face_style=getattr(config, 'face_style', '미설정'),
        acc=getattr(config, 'acc', '미설정'),
        breasts_size=_body_dic.get('breasts_size', ['미설정'])[config.breasts_size] if _body_dic and hasattr(config, 'breasts_size') else '미설정',
        hip_size=_body_dic.get('hip_size', ['미설정'])[config.hip_size] if _body_dic and hasattr(config, 'hip_size') else '미설정',
        body_size=_body_dic.get('body_size', ['미설정'])[config.body_size] if _body_dic and hasattr(config, 'body_size') else '미설정',
        appearance2=config.appearance2, outfit2=config.outfit2,
        talking_style2=config.talking_style2, personality2=config.personality2,
        selected_relationship=selected_relationship,
        first_event=first_event,
        second_event=second_event,
        first_trigger=config.first_trigger, second_trigger=config.second_trigger,
        relationship_development=', '.join(selected_developments),
        body_change_sign=selected_sign, crisis_trigger=selected_crisis,
        intermediate_phase_block=intermediate_block,
        daily_corruption_changes_block=daily_block,
        resistance_reason=selected_resistance, corruption_reason=selected_corruption_reason,
        selected_ending=id_selected_ending,
        corruption_text=corruption_text,
        corruption_desc_text=' + '.join([c['desc'] for c in selected_corruption]),
        body_text=body_text, body_change_desc=selected_body_change['desc'],
        change_awareness=config.change_awareness,
        corruption_flow_name=config.corruption_flow['name'],
        corruption_flow_desc=config.corruption_flow['desc'],
        corruption_flow_flow=config.corruption_flow['flow'],
        jinshugai_text=jinshugai_text, events_text=events_text1,
        genre_text=genre_text_val,
        rel1_update=rel1_update_val,
        import_point=config.import_point,
        intro_end_ep=intro_end_ep,
        intro_episode_count=intro_episodes,
        intro_guide_count=intro_guide_count,
        guide_num=guide_num
    )
    introduction_result = call_openai_for_plot(introduction_prompt, messages=plot_messages, log_fn=_log)
    plot_messages.append({"role": "assistant", "content": introduction_result})

    # 13-2. [전] Crisis (EP crisis_start_ep~crisis_end_ep)
    _log(f"[GUIDES] [전] EP {crisis_start_ep}~{crisis_end_ep} 가이드 생성 시작...")
    crisis_prompt = _build_prompt(prompts["crisis_guides_prompt"],
        story_info=story_info,
        name=config.name, job=config.job, sex=config.sex, age=config.age,
        name2=config.name2, job2=config.job2, sex2=config.sex2, age2=config.age2,
        appearance2=config.appearance2, outfit2=config.outfit2,
        talking_style2=config.talking_style2,
        selected_relationship=selected_relationship,
        first_event=first_event,
        second_event=second_event,
        first_trigger=config.first_trigger, second_trigger=config.second_trigger,
        relationship_development=', '.join(selected_developments),
        body_change_sign=selected_sign, crisis_trigger=selected_crisis,
        body_text=body_text, body_change_desc=selected_body_change['desc'],
        change_awareness=config.change_awareness,
        corruption_flow_name=config.corruption_flow['name'],
        corruption_flow_desc=config.corruption_flow['desc'],
        corruption_flow_flow=config.corruption_flow['flow'],
        events_text=events_text2,
        selected_tone=selected_tone, selected_interaction=selected_interaction,
        selected_sensory=selected_sensory, selected_conflict=selected_conflict,
        selected_location=selected_location,
        bimbo_clothes1=config.bimbo_clothes1,
        import_point=config.import_point,
        resistance_reason=selected_resistance,
        genre_text=genre_text_val,
        crisis_start_ep=crisis_start_ep,
        crisis_end_ep=crisis_end_ep,
        crisis_episode_count=crisis_episodes,
        crisis_guide_count=crisis_guide_count,
        guide_num=guide_num
    )
    crisis_result = call_openai_for_plot(crisis_prompt, messages=plot_messages, log_fn=_log)
    plot_messages.append({"role": "assistant", "content": crisis_result})

    # 13-3. [결] Ending (EP ending_start_ep~ending_end_ep)
    _log(f"[GUIDES] [결] EP {ending_start_ep}~{ending_end_ep} 가이드 생성 시작...")
    ending_prompt = _build_prompt(prompts["ending_guides_prompt"],
        story_info=story_info,
        name=config.name, job=config.job, sex=config.sex, age=config.age,
        name2=config.name2, job2=config.job2, sex2=config.sex2, age2=config.age2,
        corruption_text=corruption_text,
        corruption_desc_text=' + '.join([c['desc'] for c in selected_corruption]),
        daily_corruption_changes_block=daily_block,
        selected_ending=id_selected_ending,
        events_text=events_text3,
        random_trigger=random_trigger,
        selected_tone=selected_tone, selected_interaction=selected_interaction,
        selected_sensory=selected_sensory, selected_conflict=selected_conflict,
        selected_location=selected_location,
        bimbo_clothes2=config.bimbo_clothes2,
        import_point=config.import_point,
        genre_text=genre_text_val,
        ending_start_ep=ending_start_ep,
        ending_end_ep=ending_end_ep,
        ending_episode_count=ending_episodes,
        ending_guide_count=ending_guide_count,
        guide_num=guide_num
    )
    ending_result = call_openai_for_plot(ending_prompt, messages=plot_messages, log_fn=_log)

    # 모든 가이드를 하나로 합침 (리뷰용)
    guides_result = introduction_result + "\n\n" + crisis_result + "\n\n" + ending_result

    # 가이드 생성 후 메시지 상태 백업 (재시도 시 복구용)
    guides_messages_backup = list(plot_messages)

    # =====================================================================
    # 13-1. Agent Review: 생성된 가이드를 에이전트가 검토하고 재출력
    # =====================================================================
    _log("[GUIDES] Agent Review 시작...")
    review_prompt = _build_prompt(prompts["review_prompt"],
        guides_count=guides_count, num_episodes=num_episodes,
        job=config.job, job2=config.job2,
        corruption_text=corruption_text, body_text=body_text,
        random_trigger=random_trigger,
        first_event=first_event,
        second_event=second_event,
        selected_tone=selected_tone, selected_interaction=selected_interaction,
        selected_sensory=selected_sensory, selected_conflict=selected_conflict,
        selected_location=selected_location,
        corruption_flow=selected_corruption_flow,
        guides_result=guides_result,
        crisis_start_ep=crisis_start_ep,
        ending_start_ep=ending_start_ep,
        import_point=config.import_point
    )
    #agent_feedback = call_openai_for_client(prompt_text=review_prompt, log_fn=_log, agent="meromero")
    agent_feedback = call_openai_for_client(prompt_text=review_prompt, log_fn=_log, agent="gemma")
    #agent_feedback = call_openai_for_plot(corruption_guides_prompt, messages=plot_messages, log_fn=_log)
    _log(f"[GUIDES] Agent Review 완료")

    corruption_guides_prompt = _build_prompt(prompts["revision_prompt"],
        guides_count=guides_count, num_episodes=num_episodes, agent_feedback=agent_feedback, guides_result=guides_result, name=config.name, name2=config.name2,
        import_point=config.import_point
    )
    # 결과 파싱 후 개수 검증, 부족하면 재호출 (최대 3회)
    max_review_retry = 3
    for retry in range(max_review_retry):
        # 4. 재출력 (기억한 메시지 사용, 실패 시 2번 메시지 복구)
        if retry > 0:
            plot_messages = list(guides_messages_backup)
        guides_result = call_openai_for_plot(corruption_guides_prompt, messages=plot_messages, log_fn=_log)

        # 결과 파싱: [이름 가이드] 헤더로 주인공/상대방 분리 후 GUIDE N: 추출
        # EPISODE N 헤더도 추적하여 가이드 텍스트에 에피소드 정보 포함
        protagonist_guides = []
        partner_guides = []
        lines = guides_result.split("\n")
        current_section = None  # 'protagonist' or 'partner'
        current_episode = None  # 현재 EPISODE 번호
        for line in lines:
            stripped = line.strip()
            # [이름 가이드] 헤더 감지 (예: [주인공 가이드: 다카하시 유이], [상대방 가이드: 슌])
            header_match = re.match(r"\[(.+?) 가이드", stripped)
            if header_match:
                if current_section is None:
                    current_section = "protagonist"
                else:
                    current_section = "partner"
                continue
            # EPISODE N 헤더 감지 (대소문자 무관)
            episode_match = re.match(r"EPISODE\s*(\d+)", stripped, re.IGNORECASE)
            if episode_match:
                current_episode = int(episode_match.group(1))
                continue
            # GUIDE N: ... 형식 추출
            guide_match = re.match(r"GUIDE\s*\d+[:：]\s*(.*)", stripped)
            if guide_match and current_section is not None:
                guide_text = guide_match.group(1).strip()
                if guide_text:
                    # 에피소드 정보 포함 (파싱용 마커)
                    if current_episode is not None:
                        guide_text = f"EPISODE {current_episode}: {guide_text}"
                    if current_section == "protagonist":
                        protagonist_guides.append(guide_text)
                    else:
                        partner_guides.append(guide_text)

        if len(protagonist_guides) >= guides_count and len(partner_guides) >= guides_count:
            _log(f"[GUIDES] Agent Review 재출력 개수 확인 성공 (주인공={len(protagonist_guides)}, 상대방={len(partner_guides)})")
            break
        else:
            _log(f"[GUIDES] 개수 불일치 (주인공={len(protagonist_guides)}/{guides_count}, 상대방={len(partner_guides)}/{guides_count}). 재시도 ({retry+2}/{max_review_retry})")
            corruption_guides_prompt = _build_prompt(prompts["revision_retry_prompt"],
                guides_count=guides_count, num_episodes=num_episodes, agent_feedback=agent_feedback, guides_result=guides_result, name=config.name, name2=config.name2,
                import_point=config.import_point
            )
    else:
        _log(f"[GUIDES] {max_review_retry}회 재시도 후에도 개수 불일치. 현재 결과 사용.")

    # =====================================================================
    # 개수 조정: G1, G2, ... G{num_episodes} 그룹별로 개수 맞추기
    # - 초과: 마지막 줄을 전 줄과 합침
    # - 부족: 마지막 줄을 복사하여 채움
    # =====================================================================
    def _adjust_guides_by_group(guides, guides_count, num_episodes, guide_num_per_group, prefix_char):
        """episode 1, episode 2, ... 그룹별로 guide_num_per_group 개수 이상으로 맞추는 함수"""
        # 가이드를 그룹별로 분리
        groups = {}  # {1: [line1, line2, ...], 2: [...], ...}
        current_group = None
        for guide in guides:
            # EPISODE N: prefix 제거 (대소문자 무관)
            clean_guide = re.sub(r"^episode\s*\d+:\s*", "", guide, count=1, flags=re.IGNORECASE)
            # EPISODE N: 형식 검사 (대소문자 무관)
            match = re.match(r"episode\s*(\d+):", guide, re.IGNORECASE)
            if match:
                group_num = int(match.group(1))
                current_group = group_num
                if group_num not in groups:
                    groups[group_num] = []
                groups[group_num].append(clean_guide)
            elif current_group is not None:
                groups[current_group].append(clean_guide)
            else:
                # EP 라벨 없이 시작하는 경우 마지막 그룹에 추가
                if groups:
                    groups[current_group].append(clean_guide)
                else:
                    # 첫 번째 그룹으로 처리
                    current_group = 1
                    groups[1] = [clean_guide]

        _log(f"[{prefix_char}] 그룹 분포: {', '.join(f'EP{k}={len(v)}개' for k, v in sorted(groups.items()))}")

        # 각 그룹의 개수를 guide_num_per_group로 조정
        adjusted_guides = []
        for group_num in range(1, num_episodes + 1):
            if group_num in groups:
                group_lines = groups[group_num]
                if len(group_lines) > guide_num_per_group:
                    # 초과: 마지막 줄을 전 줄과 합침
                    while len(group_lines) > guide_num_per_group:
                        if len(group_lines) >= 2:
                            group_lines[-2] = group_lines[-2] + " " + group_lines[-1]
                            group_lines.pop()
                        else:
                            break
                    _log(f"[{prefix_char}] EP{group_num}: {len(groups[group_num])}개 -> {len(group_lines)}개 (합침)")
                elif len(group_lines) < guide_num_per_group:
                    # 부족: 마지막 줄을 복사하여 채움
                    while len(group_lines) < guide_num_per_group:
                        group_lines.append(group_lines[-1])
                    _log(f"[{prefix_char}] EP{group_num}: {len(groups[group_num])}개 -> {len(group_lines)}개 (복사)")
                adjusted_guides.extend(group_lines[:guide_num_per_group])
            else:
                # 그룹이 없는 경우 빈 문자열로 채움
                adjusted_guides.extend([""] * guide_num_per_group)
                _log(f"[{prefix_char}] EP{group_num}: 없음 -> {guide_num_per_group}개 (빈 문자열)")

        return adjusted_guides

    protagonist_guides = _adjust_guides_by_group(protagonist_guides, guides_count, num_episodes, config.guide_num, "#")
    partner_guides = _adjust_guides_by_group(partner_guides, guides_count, num_episodes, config.guide_num, "@")

    # 최종 개수 확인
    _log(f"[GUIDES] 최종 개수 (주인공={len(protagonist_guides)}, 상대방={len(partner_guides)})")

    # =====================================================================
    # first_event, second_event가 배치된 EPISODE 번호 추출
    # =====================================================================
    def _find_event_episode(event_text, guides_list):
        """가이드 리스트에서 event_text가 언급된 EPISODE 번호 반환 (없으면 -1)"""
        if not event_text:
            return -1
        for guide in guides_list:
            if event_text in guide:
                match = re.match(r"episode\s*(\d+)", guide, re.IGNORECASE)
                if match:
                    return int(match.group(1))
        return -1

    first_ep = _find_event_episode(first_event, protagonist_guides + partner_guides)
    second_ep = _find_event_episode(second_event, protagonist_guides + partner_guides)
    config.first_event_ep = first_ep
    config.second_event_ep = second_ep
    _log(f"[EVENT_EP] first_event EP={first_ep}, second_event EP={second_ep}")

    config.corruption_guides = protagonist_guides[:guides_count]
    config.partner_corruption_guides = partner_guides[:guides_count]

    # =====================================================================
    # 14. config 변수 저장 정리
    # =====================================================================
    config.theme_body_change = selected_body_change
    config.theme_corruption_elements = selected_corruption
    config.theme_jinshugai = selected_jinshugai

    # =====================================================================
    # 14-1. config.progression_array (persona_result.episodes 직접 사용)
    # =====================================================================
    progression_array = []
    for ep in persona_result["episodes"]:
        desc = f"{ep['animal_desc']} ({ep['matrix_desc']})"
        progression_array.append(desc)

    config.progression_array = progression_array

    # =====================================================================
    # 14-2. story_gen 호환 변수들
    # =====================================================================
    config.theme_job1 = config.job
    config.theme_job2 = config.job2
    config.theme_age_diff_max = abs(config.age - config.age2)
    config.theme_age_diff_min = 0
    config.temp_theme = []

    # =====================================================================
    # 15. config.plot_result (최종 표시용 텍스트)
    # =====================================================================
    plot_text = f"--- 생성된 플롯 ---\n(엔터를 치면 랜덤하게 다시 생성됩니다)\n\n"
    plot_text += f"주인공({config.name}, {config.age}세)과 상대방({config.name2}, {config.age2}세)의 이야기입니다.\n"
    plot_text += f"관계 설정 및 직업({config.job} / {config.job2})을 바탕으로 스토리가 전개됩니다."
    plot_text += f"\n\n[업데이트된 테마]\n{config.corruption_flow['name']}"
    config.plot_result = plot_text

    return {
        "jinshugai": selected_jinshugai,
        "opponent_appearance": {
            "body_type": selected_body_type,
            "has_beard": has_beard,
            "hair_color": selected_hair,
            "outfit": selected_outfit
        },
        "job": config.job,
        "age": config.age,
        "job2": config.job2,
        "age2": config.age2,
        "relationship": selected_relationship,
        "persona_text": persona_text,
        "first_trigger": selected_trigger,
        "relationship_development": selected_developments,
        "body_change_sign": selected_sign,
        "crisis_trigger": selected_crisis,
        "corruption_elements": [{"name": c["name"], "desc": c["desc"]} for c in selected_corruption],
        "body_change": {"name": selected_body_change["name"], "desc": selected_body_change["desc"]},
        "events": events,
        "abnormal_trigger": random_trigger,
        "theme": theme_result,
        "corruption_guides": protagonist_guides[:guides_count],
        "partner_corruption_guides": partner_guides[:guides_count]
    }


# =====================================================================
# 2단계 실행용 함수 (GUI용)
# =====================================================================

def theme_gen_auto_step1(story_info: str, num_episodes: int = 10, log_fn=None) -> dict:
    """
    theme_gen_auto 1단계: line 695까지 실행 (테마 생성 LLM 호출까지)

    Args:
        story_info: 스토리 정보
        num_episodes: 에피소드 수
        log_fn: 추가 로깅 함수

    Returns:
        dict (중간 결과)
    """
    def _log(msg):
        _logger.info(msg)
        if log_fn:
            log_fn(msg)

    # 1. JINSHUGAI_TEMPLATES 중 하나 선택
    JINSHUGAI_TEMPLATES = _load_theme_templates()
    selected_jinshugai_id = getattr(config, 'selected_jinshugai_id', None)
    if selected_jinshugai_id is None:
        selected_jinshugai_id = random.randint(1, 11)
    selected_jinshugai = [t for t in JINSHUGAI_TEMPLATES if t["id"] == selected_jinshugai_id]
    if not selected_jinshugai:
        selected_jinshugai = [JINSHUGAI_TEMPLATES[0]]
    template_setting = selected_jinshugai[0]
    id_target_relationships = template_setting.get("target_relationships", [])
    id_protagonist_job_keywords = template_setting.get("protagonist_job_keywords", [])
    id_opponent_job_keywords = template_setting.get("opponent_job_keywords", [])
    id_first_triggers = template_setting.get("first_triggers", [])
    id_second_triggers = template_setting.get("second_triggers", [])
    id_protagonist_hidden_jobs = template_setting.get("protagonist_hidden_jobs", [])
    id_daily_corruption_changes = template_setting.get("daily_corruption_changes", [])
    id_import_point = template_setting.get("import_point", "")
    config.import_point = id_import_point
    id_first_event = template_setting.get("first_event", [])
    id_second_event = template_setting.get("second_event", [])
    first_event = random.choice(id_first_event)
    second_event = random.choice(id_second_event)
    id_intermediate_phase = template_setting.get("intermediate_phase", [])
    if id_intermediate_phase:
        id_intermediate_phase = random.sample(id_intermediate_phase, min(random.randint(2, 3), len(id_intermediate_phase)))
    else:
        id_intermediate_phase = []
    id_endings = template_setting.get("endings", [])
    id_selected_ending = random.choice(id_endings) if id_endings else ""
    if id_daily_corruption_changes:
        id_daily_corruption_changes = random.sample(id_daily_corruption_changes, min(random.randint(2, 3), len(id_daily_corruption_changes)))
    id_resistance_reasons = template_setting.get("resistance_reasons", [])
    id_corruption_reasons = template_setting.get("corruption_reasons", [])
    selected_resistance = random.choice(id_resistance_reasons) if id_resistance_reasons else ""
    if selected_resistance and "#" in selected_resistance:
        parts = selected_resistance.split("#", 1)
        selected_resistance = parts[0].strip()
        selected_corruption_reason = parts[1].strip()
    else:
        selected_corruption_reason = random.choice(id_corruption_reasons) if id_corruption_reasons else ""
    config.resistance_reason = selected_resistance
    config.corruption_reason = selected_corruption_reason
    config.first_event = first_event
    config.second_event = second_event

    # 직업 및 나이 설정
    def _parse_job_file(filepath):
        jobs = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 4:
                    try:
                        job = {'name': parts[0], 'gender': parts[1], 'age_min': int(parts[2]), 'age_max': int(parts[3])}
                        jobs.append(job)
                    except ValueError:
                        continue
        return jobs

    job_file = os.path.join(os.path.dirname(__file__), "data", "job.txt")
    job2_file = os.path.join(os.path.dirname(__file__), "data", "job2.txt")
    if getattr(config, 'inc_flag', 0) == 1:
        character_setup.set_inc_relationship()
    else:
        config.sex = "여자"
        config.sex2 = "남자"

    def _filter_jobs_by_gender(jobs, gender):
        filtered = [job for job in jobs if job['gender'] in (gender, "남/여")]
        return filtered if filtered else jobs

    def _filter_jobs_by_keywords(jobs, keywords):
        if not keywords:
            return jobs
        filtered = []
        for job in jobs:
            for keyword in keywords:
                if keyword in job['name']:
                    filtered.append(job)
                    break
        return filtered if filtered else jobs

    if not (getattr(config, 'inc_flag', 0) == 1):
        if getattr(config, 'cmd_job', None) is None:
            job_list = _parse_job_file(job_file)
            if job_list:
                job_list_filtered = _filter_jobs_by_gender(job_list, config.sex)
                if id_protagonist_job_keywords:
                    job_list_filtered = _filter_jobs_by_keywords(job_list_filtered, id_protagonist_job_keywords)
                selected_job = random.choice(job_list_filtered)
                config.job = selected_job['name']
                if id_protagonist_hidden_jobs:
                    job_has_keyword = any(kw in config.job for kw in id_protagonist_job_keywords) if id_protagonist_job_keywords else False
                    if not job_has_keyword:
                        available_hidden = [hj for hj in id_protagonist_hidden_jobs if hj not in id_protagonist_job_keywords]
                        if available_hidden:
                            hidden_job = random.choice(available_hidden)
                            config.job = f"{config.job}({hidden_job})"
                config.age = random.randint(selected_job['age_min'], selected_job['age_max'])
            else:
                config.job = "평범한 직업"
                config.age = 25
    if not (getattr(config, 'inc_flag', 0) == 1):
        if getattr(config, 'cmd_job2', None) is None:
            job2_list = _parse_job_file(job2_file)
            if job2_list:
                job2_list_filtered = _filter_jobs_by_gender(job2_list, config.sex2)
                if id_opponent_job_keywords:
                    job2_list_filtered = _filter_jobs_by_keywords(job2_list_filtered, id_opponent_job_keywords)
                selected_job2 = random.choice(job2_list_filtered)
                config.job2 = selected_job2['name']
                config.age2 = random.randint(selected_job2['age_min'], selected_job2['age_max'])
            else:
                config.job2 = "평범한 직업"
                config.age2 = 25

    character_setup.character_init(config.sex, config.json_value)
    character_setup.archetype_setup(config.json_value)

    config.appearance2 = ""
    body_types = ["뚱뚱함", "보통", "마름"]
    selected_body_type = random.choice(body_types)
    config.appearance2 = selected_body_type
    has_beard = random.choice(["수염있음", "수염없음"])
    config.appearance2 += ", " + has_beard
    hair_colors = ["검정", "갈색", "회색", "흰색", "금발", "밤색"]
    selected_hair = "대머리" if random.random() < 0.1 else random.choice(hair_colors)
    config.appearance2 += ", " + selected_hair
    look = random.choice(["추남", "평범", "잘생김"])
    config.appearance2 += ", " + look
    talking_style2 = random.choice(["평범하게 말함", "천박하게 말함", "정중하게 말함"])
    config.talking_style2 = talking_style2
    personality2 = random.choice(["착함"])
    config.personality2 = personality2
    elements = _load_elements()
    outfit_by_job = elements["outfit_by_job"]
    default_outfit = elements.get("default_outfit", "캐주얼")
    selected_outfit = default_outfit
    job2_name = config.job2
    for keyword, outfit in outfit_by_job.items():
        if keyword in job2_name:
            selected_outfit = outfit
            break
    config.outfit2 = selected_outfit
    character_setup.name_define()
    config.nationality = "japanese"
    config.nationality2 = "japanese"

    triggers = _load_triggers()
    RELATIONSHIPS = triggers["relationships"]
    if id_target_relationships:
        candidates = id_target_relationships
        if getattr(config, 'inc_flag', 0) == 1:
            candidates = [r for r in candidates if r != "모르는 사이"]
        selected_relationship = random.choice(candidates) if candidates else random.choice(RELATIONSHIPS)
    elif getattr(config, 'inc_flag', 0) == 1:
        family_relationships = [r for r in RELATIONSHIPS if r in ("친밀한 관계", "보통인 관계")]
        selected_relationship = random.choice(family_relationships) if family_relationships else random.choice(RELATIONSHIPS)
    else:
        selected_relationship = random.choice(RELATIONSHIPS)
    config.relationship = selected_relationship

    old_stdout = sys.stdout
    sys.stdout = captured_persona = io.StringIO()
    try:
        if random.randint(0,1) == 0:
            persona_result = generate_ultimate_heroine_progression(num_episodes=num_episodes, relationship=selected_relationship)
        else:
            persona_result = generate_ultimate_heroine_progression(num_episodes=num_episodes, fixed_breeds="yes", relationship=selected_relationship)
    except Exception as e:
        _log(f"[persona] 오류 발생: {e}")
        sys.stdout = old_stdout
        raise
    finally:
        sys.stdout = old_stdout
    persona_text = captured_persona.getvalue().strip()
    config.persona_text = persona_text
    config.persona_result = persona_result

    FIRST_TRIGGERS = triggers["first_triggers"]
    if id_first_triggers:
        available_first_triggers = id_first_triggers
    else:
        available_first_triggers = [_resolve_template(t, config.name, config.name2) for t in FIRST_TRIGGERS]
    selected_trigger = random.choice(available_first_triggers)
    config.first_trigger = selected_trigger
    SECOND_TRIGGERS = triggers["second_triggers"]
    if id_second_triggers:
        available_second_triggers = id_second_triggers
    else:
        available_second_triggers = SECOND_TRIGGERS
    selected_trigger = random.choice(available_second_triggers)
    config.second_trigger = selected_trigger

    RELATIONSHIP_DEVELOPMENTS = triggers["relationship_developments"]
    selected_developments = random.sample(RELATIONSHIP_DEVELOPMENTS, 2)
    config.relationship_development = selected_developments

    CORRUPTION_TYPES = elements["corruption_types"]
    CORRUPTION_TYPES_RESOLVED = []
    for ct in CORRUPTION_TYPES:
        CORRUPTION_TYPES_RESOLVED.append({"name": ct["name"], "desc": _resolve_template(ct["desc_template"], config.name, config.name2)})
    BODY_CHANGES = elements["body_changes"]
    selected_corruption = [random.choice(CORRUPTION_TYPES_RESOLVED)]
    selected_body_change = random.choice(BODY_CHANGES)
    config.corruption_elements = selected_corruption
    config.body_change = selected_body_change
    corruption_text = " + ".join([c["name"] for c in selected_corruption])
    body_text = selected_body_change["name"]

    BODY_CHANGE_SIGNS = elements["body_change_signs"]
    body_signs = BODY_CHANGE_SIGNS.get(selected_body_change["name"], ["미묘한 신체 변화의 징조"])
    selected_sign = random.choice(body_signs)
    config.body_change_sign = selected_sign
    change_awareness_options = elements["change_awareness_options"]
    selected_awareness_raw = random.choice(change_awareness_options)
    config.change_awareness = _resolve_template(selected_awareness_raw, config.name, config.name2)
    corruption_flows_raw = elements["corruption_flows"]
    corruption_flows = []
    for cf in corruption_flows_raw:
        corruption_flows.append({"name": cf["name"], "desc": cf["desc"], "flow": _resolve_template(cf["flow_template"], config.name, config.name2)})
    selected_corruption_flow = random.choice(corruption_flows)
    config.corruption_flow = selected_corruption_flow
    CORRUPTION_TONES = elements["corruption_tones"]
    INTERACTION_STYLES = elements["interaction_styles"]
    SENSORY_EMPHASIS = elements["sensory_emphasis"]
    INTERNAL_CONFLICTS = elements["internal_conflicts"]
    LOCATION_MOODS = elements["location_moods"]
    selected_tone = random.choice(CORRUPTION_TONES)
    selected_interaction = random.choice(INTERACTION_STYLES)
    selected_sensory = random.choice(SENSORY_EMPHASIS)
    selected_conflict = random.choice(INTERNAL_CONFLICTS)
    selected_location = random.choice(LOCATION_MOODS)
    CRISIS_TRIGGERS = triggers["crisis_triggers"]
    selected_crisis = random.choice(CRISIS_TRIGGERS)
    config.crisis_trigger = selected_crisis

    breed1_name = persona_result["breed_A"]
    breed1_data = BREEDS_DATA[breed1_name]
    breed2_name = persona_result["breed_B"]
    breed2_data = BREEDS_DATA[breed2_name]
    config.theme_breeds = [(breed1_name, breed1_data), (breed2_name, breed2_data)]
    events = []
    for i, ep in enumerate(persona_result["episodes"]):
        jinshugai_template = selected_jinshugai[i % len(selected_jinshugai)]
        jinshugai_event = f"{jinshugai_template['name']} ({jinshugai_template['concept']})"
        event = {
            "index": ep["index"], "breed": ep["active_breed"],
            "trope": persona_result["trope_A" if ep["active_breed"] == persona_result["breed_A"] else "trope_B"],
            "stage": ep["animal_desc"], "matrix_desc": ep["matrix_desc"], "stage_name": ep["stage_name"],
            "breed_tag": ep["breed_tag"], "jinshugai": jinshugai_event, "progress": ep["t"],
        }
        if i == len(persona_result["episodes"]) - 1:
            event["ending_text"] = persona_result["dynamic_ending_text"]
        events.append(event)
    config.theme_events = events

    trigger_path = os.path.join(os.path.dirname(__file__), "data", "abnormal_trigger.txt")
    try:
        with open(trigger_path, "r", encoding="utf-8") as f:
            trigger_lines = [line.strip() for line in f if line.strip()]
        random_trigger = random.choice(trigger_lines)
        config.abnormal_trigger = random_trigger
    except (FileNotFoundError, Exception) as e:
        _log(f"[abnormal_trigger] 파일 오류: {e}. 기본값 '애정' 사용")
        random_trigger = "애정"
        config.abnormal_trigger = random_trigger
    costume_path = os.path.join(os.path.dirname(__file__), "data", "bimbo_costume.txt")
    try:
        with open(costume_path, "r", encoding="utf-8") as f:
            costume_lines = []
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if "#" in line:
                    costume_name = line.split("#", 1)[0].strip()
                else:
                    costume_name = line
                costume_lines.append(costume_name)
        selected_costumes = random.sample(costume_lines, min(2, len(costume_lines)))
        config.bimbo_clothes1 = selected_costumes[0]
        config.bimbo_clothes2 = selected_costumes[1] if len(selected_costumes) > 1 else selected_costumes[0]
    except (FileNotFoundError, Exception) as e:
        config.bimbo_clothes1 = "복장1"
        config.bimbo_clothes2 = "복장2"

    # 12. 기-승-전-결 테마 생성 (LLM 호출)
    prompts = _load_prompts()
    jinshugai_text = "\n".join([f"  - {t['id']}. {t['name']}: {t['concept']}" for t in selected_jinshugai])

    # 에피소드 분할 범위 계산
    base_intro = int(num_episodes * 0.4)
    base_crisis = int(num_episodes * 0.4)
    base_ending = num_episodes - base_intro - base_crisis
    intro_episodes = max(1, base_intro + random.choice([-1, 0, 1]))
    crisis_episodes = max(1, base_crisis + random.choice([-1, 0, 1]))
    ending_episodes = num_episodes - intro_episodes - crisis_episodes
    ending_episodes = max(1, ending_episodes)
    intro_start_ep = 1
    intro_end_ep = intro_episodes
    crisis_start_ep = intro_end_ep + 1
    crisis_end_ep = crisis_start_ep + crisis_episodes - 1
    ending_start_ep = crisis_end_ep + 1
    ending_end_ep = num_episodes
    _log(f"[EPISODE_SPLIT] 기-승: EP {intro_start_ep}~{intro_end_ep} ({intro_episodes}개)")
    _log(f"[EPISODE_SPLIT] 전: EP {crisis_start_ep}~{crisis_end_ep} ({crisis_episodes}개)")
    _log(f"[EPISODE_SPLIT] 결: EP {ending_start_ep}~{ending_end_ep} ({ending_episodes}개)")
    config.intro_end_ep = intro_end_ep
    config.crisis_start_ep = crisis_start_ep
    config.crisis_end_ep = crisis_end_ep
    config.ending_start_ep = ending_start_ep
    config.ending_end_ep = ending_end_ep
    guide_num = config.guide_num
    intro_guide_count = intro_episodes * guide_num
    crisis_guide_count = crisis_episodes * guide_num
    ending_guide_count = ending_episodes * guide_num
    events_text_parts = []
    events_text1_parts = []
    events_text2_parts = []
    events_text3_parts = []
    epi_num = 1
    for i, e in enumerate(events):
        line = (f"  EPISODE {e['index']}: {e['breed']} ({e['trope']})\n     현재 감정 상태: {e['stage_name']}\n"
                f"     행동 패턴 요약: {e['stage']}\n     자세한 심리 상태: {e['matrix_desc']}")
        if "ending_text" in e:
            line += f"\n최종 결말의 {config.name}의 모습: {e['ending_text']}"
        if epi_num <= intro_end_ep:
            events_text1_parts.append(line)
        elif epi_num <= crisis_end_ep:
            events_text2_parts.append(line)
        else:
            events_text3_parts.append(line)
        events_text_parts.append(line)
        epi_num += 1
    events_text = "\n".join(events_text_parts)
    events_text1 = "\n".join(events_text1_parts)
    events_text2 = "\n".join(events_text2_parts)
    events_text3 = "\n".join(events_text3_parts)

    _body_dic = getattr(config, 'body_dic', None)
    theme_prompt = _build_prompt(prompts["theme_prompt"],
        story_info=story_info,
        name=config.name, job=config.job, sex=config.sex, age=config.age,
        name2=config.name2, job2=config.job2, sex2=config.sex2, age2=config.age2,
        hair_color=getattr(config, 'hair_color', '미설정'),
        hair_style=getattr(config, 'hair_style', '미설정'),
        eye_color=getattr(config, 'eye_color', '미설정'),
        skin_color=getattr(config, 'skin_color', '미설정'),
        face_style=getattr(config, 'face_style', '미설정'),
        acc=getattr(config, 'acc', '미설정'),
        breasts_size=_body_dic.get('breasts_size', ['미설정'])[config.breasts_size] if _body_dic and hasattr(config, 'breasts_size') else '미설정',
        hip_size=_body_dic.get('hip_size', ['미설정'])[config.hip_size] if _body_dic and hasattr(config, 'hip_size') else '미설정',
        body_size=_body_dic.get('body_size', ['미설정'])[config.body_size] if _body_dic and hasattr(config, 'body_size') else '미설정',
        appearance2=config.appearance2, outfit2=config.outfit2,
        talking_style2=config.talking_style2, personality2=config.personality2,
        selected_relationship=selected_relationship,
        first_event=first_event, second_event=second_event,
        first_trigger=config.first_trigger, second_trigger=config.second_trigger,
        relationship_development=', '.join(selected_developments),
        body_change_sign=selected_sign, crisis_trigger=selected_crisis,
        intermediate_phase_block=(f'\n## 중간 단계 변화 (기/승 단계에 배치하여 점진적 변화 묘사)\n' + '\n'.join([f"* {i+1}. {change}" for i, change in enumerate(id_intermediate_phase)])) if id_intermediate_phase else '',
        daily_corruption_changes_block=('\n'.join([f"* {i+1}. {change}" for i, change in enumerate(id_daily_corruption_changes)])) if id_daily_corruption_changes else '* (미설정)',
        resistance_reason=selected_resistance, corruption_reason=selected_corruption_reason,
        selected_ending=id_selected_ending,
        corruption_text=corruption_text,
        corruption_desc_text=' + '.join([c['desc'] for c in selected_corruption]),
        body_text=body_text, body_change_desc=selected_body_change['desc'],
        change_awareness=config.change_awareness,
        corruption_flow_name=config.corruption_flow['name'],
        corruption_flow_desc=config.corruption_flow['desc'],
        corruption_flow_flow=config.corruption_flow['flow'],
        jinshugai_text=jinshugai_text, events_text=events_text,
        genre_text=prompts.get("inc_flag_genre_text", prompts.get("genre_text", "")) if getattr(config, 'inc_flag', 0) == 1 else prompts.get("genre_text", ""),
        rel1_update=f"{config.name}은(는) {config.name2}의 {getattr(config, 'rel1', '')}입니다." if getattr(config, 'inc_flag', 0) == 1 and getattr(config, 'rel1', '') else "",
        import_point=config.import_point
    )
    rel1_update=f"{config.name}은(는) {config.name2}의 {getattr(config, 'rel1', '')}입니다." if getattr(config, 'inc_flag', 0) == 1 and getattr(config, 'rel1', '') else ""
    config.rel1_update = rel1_update

    # 테마 생성 LLM 호출은 Step2로 이동 (Step1은 랜덤 생성만 수행)
    plot_messages = [{"role": "system", "content": config.system_prompt}]

    # 중간 결과 반환
    return {
        "selected_jinshugai": selected_jinshugai,
        "template_setting": template_setting,
        "id_target_relationships": id_target_relationships,
        "id_protagonist_job_keywords": id_protagonist_job_keywords,
        "id_opponent_job_keywords": id_opponent_job_keywords,
        "id_first_triggers": id_first_triggers,
        "id_second_triggers": id_second_triggers,
        "id_protagonist_hidden_jobs": id_protagonist_hidden_jobs,
        "id_daily_corruption_changes": id_daily_corruption_changes,
        "id_import_point": id_import_point,
        "first_event": first_event,
        "second_event": second_event,
        "id_intermediate_phase": id_intermediate_phase,
        "id_selected_ending": id_selected_ending,
        "selected_resistance": selected_resistance,
        "selected_corruption_reason": selected_corruption_reason,
        "selected_relationship": selected_relationship,
        "persona_result": persona_result,
        "persona_text": persona_text,
        "selected_developments": selected_developments,
        "selected_corruption": selected_corruption,
        "selected_body_change": selected_body_change,
        "corruption_text": corruption_text,
        "body_text": body_text,
        "selected_sign": selected_sign,
        "selected_corruption_flow": selected_corruption_flow,
        "selected_tone": selected_tone,
        "selected_interaction": selected_interaction,
        "selected_sensory": selected_sensory,
        "selected_conflict": selected_conflict,
        "selected_location": selected_location,
        "selected_crisis": selected_crisis,
        "events": events,
        "random_trigger": random_trigger,
        "prompts": prompts,
        "jinshugai_text": jinshugai_text,
        "events_text": events_text,
        "events_text1": events_text1,
        "events_text2": events_text2,
        "events_text3": events_text3,
        "intro_start_ep": intro_start_ep,
        "intro_end_ep": intro_end_ep,
        "crisis_start_ep": crisis_start_ep,
        "crisis_end_ep": crisis_end_ep,
        "ending_start_ep": ending_start_ep,
        "ending_end_ep": ending_end_ep,
        "intro_episodes": intro_episodes,
        "crisis_episodes": crisis_episodes,
        "ending_episodes": ending_episodes,
        "intro_guide_count": intro_guide_count,
        "crisis_guide_count": crisis_guide_count,
        "ending_guide_count": ending_guide_count,
        "guide_num": guide_num,
        "plot_messages": plot_messages,
        "theme_prompt": theme_prompt,
        "_body_dic": _body_dic,
        "elements": elements,
        "triggers": triggers,
    }


def theme_gen_auto_step2(story_info: str, step1_result: dict, num_episodes: int = 10, log_fn=None) -> dict:
    """
    theme_gen_auto 2단계: line 695 이후 실행 (가이드 생성 + Agent Review + 최종 정리)

    Args:
        story_info: 스토리 정보
        step1_result: theme_gen_auto_step1의 반환값
        num_episodes: 에피소드 수
        log_fn: 추가 로깅 함수

    Returns:
        dict (최종 결과)
    """
    def _log(msg):
        _logger.info(msg)
        if log_fn:
            log_fn(msg)

    # step1 결과에서 변수 복원
    selected_jinshugai = step1_result["selected_jinshugai"]
    first_event = step1_result["first_event"]
    second_event = step1_result["second_event"]
    id_intermediate_phase = step1_result["id_intermediate_phase"]
    id_daily_corruption_changes = step1_result["id_daily_corruption_changes"]
    id_selected_ending = step1_result["id_selected_ending"]
    selected_resistance = step1_result["selected_resistance"]
    selected_corruption_reason = step1_result["selected_corruption_reason"]
    selected_relationship = step1_result["selected_relationship"]
    selected_developments = step1_result["selected_developments"]
    selected_corruption = step1_result["selected_corruption"]
    selected_body_change = step1_result["selected_body_change"]
    corruption_text = step1_result["corruption_text"]
    body_text = step1_result["body_text"]
    selected_sign = step1_result["selected_sign"]
    selected_corruption_flow = step1_result["selected_corruption_flow"]
    selected_tone = step1_result["selected_tone"]
    selected_interaction = step1_result["selected_interaction"]
    selected_sensory = step1_result["selected_sensory"]
    selected_conflict = step1_result["selected_conflict"]
    selected_location = step1_result["selected_location"]
    selected_crisis = step1_result["selected_crisis"]
    events = step1_result["events"]
    random_trigger = step1_result["random_trigger"]
    prompts = step1_result["prompts"]
    jinshugai_text = step1_result["jinshugai_text"]
    events_text = step1_result["events_text"]
    events_text1 = step1_result["events_text1"]
    events_text2 = step1_result["events_text2"]
    events_text3 = step1_result["events_text3"]
    intro_start_ep = step1_result["intro_start_ep"]
    intro_end_ep = step1_result["intro_end_ep"]
    crisis_start_ep = step1_result["crisis_start_ep"]
    crisis_end_ep = step1_result["crisis_end_ep"]
    ending_start_ep = step1_result["ending_start_ep"]
    ending_end_ep = step1_result["ending_end_ep"]
    intro_episodes = step1_result["intro_episodes"]
    crisis_episodes = step1_result["crisis_episodes"]
    ending_episodes = step1_result["ending_episodes"]
    intro_guide_count = step1_result["intro_guide_count"]
    crisis_guide_count = step1_result["crisis_guide_count"]
    ending_guide_count = step1_result["ending_guide_count"]
    guide_num = step1_result["guide_num"]
    plot_messages = step1_result["plot_messages"]
    theme_prompt = step1_result["theme_prompt"]
    _body_dic = step1_result["_body_dic"]

    # 1. 테마 생성 (LLM 호출)
    _log("[THEME] 테마 생성 LLM 호출 시작...")
    theme_result = call_openai_for_plot(theme_prompt, messages=plot_messages, log_fn=_log)
    plot_messages.append({"role": "assistant", "content": theme_result})
    config.plot_result = theme_result

    # 13. 가이드 생성 (LLM 호출: 기-승-전-결 단계별 생성)
    guides_count = num_episodes * config.guide_num
    corruption_desc_text = " + ".join([c["desc"] for c in selected_corruption])
    genre_text_val = prompts.get("inc_flag_genre_text", prompts.get("genre_text", "")) if getattr(config, 'inc_flag', 0) == 1 else prompts.get("genre_text", "")
    rel1_update_val = f"{config.name}은(는) {config.name2}의 {getattr(config, 'rel1', '')}입니다." if getattr(config, 'inc_flag', 0) == 1 and getattr(config, 'rel1', '') else ""
    config.rel1_update = rel1_update_val
    intermediate_block = (f'\n## 중간 단계 변화 (기/승 단계에 배치하여 점진적 변화 묘사)\n' + '\n'.join([f"* {i+1}. {change}" for i, change in enumerate(id_intermediate_phase)])) if id_intermediate_phase else ''
    daily_block = ('\n'.join([f"* {i+1}. {change}" for i, change in enumerate(id_daily_corruption_changes)])) if id_daily_corruption_changes else '* (미설정)'

    # 13-1. [기-승] Introduction
    _log(f"[GUIDES] [기-승] EP {intro_start_ep}~{intro_end_ep} 가이드 생성 시작...")
    introduction_prompt = _build_prompt(prompts["introduction_prompt"],
        story_info=story_info,
        name=config.name, job=config.job, sex=config.sex, age=config.age,
        name2=config.name2, job2=config.job2, sex2=config.sex2, age2=config.age2,
        hair_color=getattr(config, 'hair_color', '미설정'),
        hair_style=getattr(config, 'hair_style', '미설정'),
        eye_color=getattr(config, 'eye_color', '미설정'),
        skin_color=getattr(config, 'skin_color', '미설정'),
        face_style=getattr(config, 'face_style', '미설정'),
        acc=getattr(config, 'acc', '미설정'),
        breasts_size=_body_dic.get('breasts_size', ['미설정'])[config.breasts_size] if _body_dic and hasattr(config, 'breasts_size') else '미설정',
        hip_size=_body_dic.get('hip_size', ['미설정'])[config.hip_size] if _body_dic and hasattr(config, 'hip_size') else '미설정',
        body_size=_body_dic.get('body_size', ['미설정'])[config.body_size] if _body_dic and hasattr(config, 'body_size') else '미설정',
        appearance2=config.appearance2, outfit2=config.outfit2,
        talking_style2=config.talking_style2, personality2=config.personality2,
        selected_relationship=selected_relationship,
        first_event=first_event, second_event=second_event,
        first_trigger=config.first_trigger, second_trigger=config.second_trigger,
        relationship_development=', '.join(selected_developments),
        body_change_sign=selected_sign, crisis_trigger=selected_crisis,
        intermediate_phase_block=intermediate_block,
        daily_corruption_changes_block=daily_block,
        resistance_reason=selected_resistance, corruption_reason=selected_corruption_reason,
        selected_ending=id_selected_ending,
        corruption_text=corruption_text,
        corruption_desc_text=' + '.join([c['desc'] for c in selected_corruption]),
        body_text=body_text, body_change_desc=selected_body_change['desc'],
        change_awareness=config.change_awareness,
        corruption_flow_name=config.corruption_flow['name'],
        corruption_flow_desc=config.corruption_flow['desc'],
        corruption_flow_flow=config.corruption_flow['flow'],
        jinshugai_text=jinshugai_text, events_text=events_text1,
        genre_text=genre_text_val, rel1_update=rel1_update_val,
        import_point=config.import_point,
        intro_end_ep=intro_end_ep, intro_episode_count=intro_episodes,
        intro_guide_count=intro_guide_count, guide_num=guide_num
    )
    introduction_result = call_openai_for_plot(introduction_prompt, messages=plot_messages, log_fn=_log)
    plot_messages.append({"role": "assistant", "content": introduction_result})

    # 13-2. [전] Crisis
    _log(f"[GUIDES] [전] EP {crisis_start_ep}~{crisis_end_ep} 가이드 생성 시작...")
    crisis_prompt = _build_prompt(prompts["crisis_guides_prompt"],
        story_info=story_info,
        name=config.name, job=config.job, sex=config.sex, age=config.age,
        name2=config.name2, job2=config.job2, sex2=config.sex2, age2=config.age2,
        appearance2=config.appearance2, outfit2=config.outfit2,
        talking_style2=config.talking_style2,
        selected_relationship=selected_relationship,
        first_event=first_event, second_event=second_event,
        first_trigger=config.first_trigger, second_trigger=config.second_trigger,
        relationship_development=', '.join(selected_developments),
        body_change_sign=selected_sign, crisis_trigger=selected_crisis,
        body_text=body_text, body_change_desc=selected_body_change['desc'],
        change_awareness=config.change_awareness,
        corruption_flow_name=config.corruption_flow['name'],
        corruption_flow_desc=config.corruption_flow['desc'],
        corruption_flow_flow=config.corruption_flow['flow'],
        events_text=events_text2,
        selected_tone=selected_tone, selected_interaction=selected_interaction,
        selected_sensory=selected_sensory, selected_conflict=selected_conflict,
        selected_location=selected_location,
        bimbo_clothes1=config.bimbo_clothes1,
        import_point=config.import_point,
        resistance_reason=selected_resistance,
        genre_text=genre_text_val,
        crisis_start_ep=crisis_start_ep, crisis_end_ep=crisis_end_ep,
        crisis_episode_count=crisis_episodes, crisis_guide_count=crisis_guide_count,
        guide_num=guide_num
    )
    crisis_result = call_openai_for_plot(crisis_prompt, messages=plot_messages, log_fn=_log)
    plot_messages.append({"role": "assistant", "content": crisis_result})

    # 13-3. [결] Ending
    _log(f"[GUIDES] [결] EP {ending_start_ep}~{ending_end_ep} 가이드 생성 시작...")
    ending_prompt = _build_prompt(prompts["ending_guides_prompt"],
        story_info=story_info,
        name=config.name, job=config.job, sex=config.sex, age=config.age,
        name2=config.name2, job2=config.job2, sex2=config.sex2, age2=config.age2,
        corruption_text=corruption_text,
        corruption_desc_text=' + '.join([c['desc'] for c in selected_corruption]),
        daily_corruption_changes_block=daily_block,
        selected_ending=id_selected_ending,
        events_text=events_text3,
        random_trigger=random_trigger,
        selected_tone=selected_tone, selected_interaction=selected_interaction,
        selected_sensory=selected_sensory, selected_conflict=selected_conflict,
        selected_location=selected_location,
        bimbo_clothes2=config.bimbo_clothes2,
        import_point=config.import_point,
        genre_text=genre_text_val,
        ending_start_ep=ending_start_ep, ending_end_ep=ending_end_ep,
        ending_episode_count=ending_episodes, ending_guide_count=ending_guide_count,
        guide_num=guide_num
    )
    ending_result = call_openai_for_plot(ending_prompt, messages=plot_messages, log_fn=_log)
    guides_result = introduction_result + "\n\n" + crisis_result + "\n\n" + ending_result
    guides_messages_backup = list(plot_messages)

    # 13-1. Agent Review
    _log("[GUIDES] Agent Review 시작...")
    review_prompt = _build_prompt(prompts["review_prompt"],
        guides_count=guides_count, num_episodes=num_episodes,
        job=config.job, job2=config.job2,
        corruption_text=corruption_text, body_text=body_text,
        random_trigger=random_trigger,
        first_event=first_event, second_event=second_event,
        selected_tone=selected_tone, selected_interaction=selected_interaction,
        selected_sensory=selected_sensory, selected_conflict=selected_conflict,
        selected_location=selected_location,
        corruption_flow=selected_corruption_flow,
        guides_result=guides_result,
        crisis_start_ep=crisis_start_ep, ending_start_ep=ending_start_ep,
        import_point=config.import_point
    )
    agent_feedback = call_openai_for_client(prompt_text=review_prompt, log_fn=_log, agent="gemma")
    _log(f"[GUIDES] Agent Review 완료")

    corruption_guides_prompt = _build_prompt(prompts["revision_prompt"],
        guides_count=guides_count, num_episodes=num_episodes, agent_feedback=agent_feedback,
        guides_result=guides_result, name=config.name, name2=config.name2,
        import_point=config.import_point
    )
    max_review_retry = 3
    for retry in range(max_review_retry):
        if retry > 0:
            plot_messages = list(guides_messages_backup)
        guides_result = call_openai_for_plot(corruption_guides_prompt, messages=plot_messages, log_fn=_log)
        protagonist_guides = []
        partner_guides = []
        lines = guides_result.split("\n")
        current_section = None
        current_episode = None
        for line in lines:
            stripped = line.strip()
            header_match = re.match(r"\[(.+?) 가이드", stripped)
            if header_match:
                current_section = "protagonist" if current_section is None else "partner"
                continue
            episode_match = re.match(r"EPISODE\s*(\d+)", stripped, re.IGNORECASE)
            if episode_match:
                current_episode = int(episode_match.group(1))
                continue
            guide_match = re.match(r"GUIDE\s*\d+[:：]\s*(.*)", stripped)
            if guide_match and current_section is not None:
                guide_text = guide_match.group(1).strip()
                if guide_text:
                    if current_episode is not None:
                        guide_text = f"EPISODE {current_episode}: {guide_text}"
                    if current_section == "protagonist":
                        protagonist_guides.append(guide_text)
                    else:
                        partner_guides.append(guide_text)
        if len(protagonist_guides) >= guides_count and len(partner_guides) >= guides_count:
            _log(f"[GUIDES] Agent Review 재출력 개수 확인 성공 (주인공={len(protagonist_guides)}, 상대방={len(partner_guides)})")
            break
        else:
            _log(f"[GUIDES] 개수 불일치 (주인공={len(protagonist_guides)}/{guides_count}, 상대방={len(partner_guides)}/{guides_count}). 재시도 ({retry+2}/{max_review_retry})")
            corruption_guides_prompt = _build_prompt(prompts["revision_retry_prompt"],
                guides_count=guides_count, num_episodes=num_episodes, agent_feedback=agent_feedback,
                guides_result=guides_result, name=config.name, name2=config.name2,
                import_point=config.import_point
            )
    else:
        _log(f"[GUIDES] {max_review_retry}회 재시도 후에도 개수 불일치. 현재 결과 사용.")

    def _adjust_guides_by_group(guides, guides_count, num_episodes, guide_num_per_group, prefix_char):
        groups = {}
        current_group = None
        for guide in guides:
            clean_guide = re.sub(r"^episode\s*\d+:\s*", "", guide, count=1, flags=re.IGNORECASE)
            match = re.match(r"episode\s*(\d+):", guide, re.IGNORECASE)
            if match:
                group_num = int(match.group(1))
                current_group = group_num
                if group_num not in groups:
                    groups[group_num] = []
                groups[group_num].append(clean_guide)
            elif current_group is not None:
                groups[current_group].append(clean_guide)
            else:
                if groups:
                    groups[current_group].append(clean_guide)
                else:
                    current_group = 1
                    groups[1] = [clean_guide]
        _log(f"[{prefix_char}] 그룹 분포: {', '.join(f'EP{k}={len(v)}개' for k, v in sorted(groups.items()))}")
        adjusted_guides = []
        for group_num in range(1, num_episodes + 1):
            if group_num in groups:
                group_lines = groups[group_num]
                if len(group_lines) > guide_num_per_group:
                    while len(group_lines) > guide_num_per_group:
                        if len(group_lines) >= 2:
                            group_lines[-2] = group_lines[-2] + " " + group_lines[-1]
                            group_lines.pop()
                        else:
                            break
                    _log(f"[{prefix_char}] EP{group_num}: {len(groups[group_num])}개 -> {len(group_lines)}개 (합침)")
                elif len(group_lines) < guide_num_per_group:
                    while len(group_lines) < guide_num_per_group:
                        group_lines.append(group_lines[-1])
                    _log(f"[{prefix_char}] EP{group_num}: {len(groups[group_num])}개 -> {len(group_lines)}개 (복사)")
                adjusted_guides.extend(group_lines[:guide_num_per_group])
            else:
                adjusted_guides.extend([""] * guide_num_per_group)
                _log(f"[{prefix_char}] EP{group_num}: 없음 -> {guide_num_per_group}개 (빈 문자열)")
        return adjusted_guides

    protagonist_guides = _adjust_guides_by_group(protagonist_guides, guides_count, num_episodes, config.guide_num, "#")
    partner_guides = _adjust_guides_by_group(partner_guides, guides_count, num_episodes, config.guide_num, "@")
    _log(f"[GUIDES] 최종 개수 (주인공={len(protagonist_guides)}, 상대방={len(partner_guides)})")

    def _find_event_episode(event_text, guides_list):
        if not event_text:
            return -1
        for guide in guides_list:
            if event_text in guide:
                match = re.match(r"episode\s*(\d+)", guide, re.IGNORECASE)
                if match:
                    return int(match.group(1))
        return -1

    first_ep = _find_event_episode(first_event, protagonist_guides + partner_guides)
    second_ep = _find_event_episode(second_event, protagonist_guides + partner_guides)
    config.first_event_ep = first_ep
    config.second_event_ep = second_ep
    _log(f"[EVENT_EP] first_event EP={first_ep}, second_event EP={second_ep}")

    config.corruption_guides = protagonist_guides[:guides_count]
    config.partner_corruption_guides = partner_guides[:guides_count]

    # 14. config 변수 저장 정리
    config.theme_body_change = selected_body_change
    config.theme_corruption_elements = selected_corruption
    config.theme_jinshugai = selected_jinshugai

    # 14-1. progression_array
    persona_result = step1_result["persona_result"]
    progression_array = []
    for ep in persona_result["episodes"]:
        desc = f"{ep['animal_desc']} ({ep['matrix_desc']})"
        progression_array.append(desc)
    config.progression_array = progression_array

    # 14-2. story_gen 호환 변수들
    config.theme_job1 = config.job
    config.theme_job2 = config.job2
    config.theme_age_diff_max = abs(config.age - config.age2)
    config.theme_age_diff_min = 0
    config.temp_theme = []

    # 15. config.plot_result
    plot_text = f"--- 생성된 플롯 ---\n(엔터를 치면 랜덤하게 다시 생성됩니다)\n\n"
    plot_text += f"주인공({config.name}, {config.age}세)과 상대방({config.name2}, {config.age2}세)의 이야기입니다.\n"
    plot_text += f"관계 설정 및 직업({config.job} / {config.job2})을 바탕으로 스토리가 전개됩니다."
    plot_text += f"\n\n[업데이트된 테마]\n{config.corruption_flow['name']}"
    config.plot_result = plot_text

    return {
        "jinshugai": selected_jinshugai,
        "opponent_appearance": {
            "body_type": config.appearance2,
            "talking_style": config.talking_style2,
            "personality": config.personality2,
            "outfit": config.outfit2,
        },
        "relationship": selected_relationship,
        "events": events,
        "corruption_guides": protagonist_guides[:guides_count],
        "partner_corruption_guides": partner_guides[:guides_count],
    }


if __name__ == "__main__":
    import json

    story_info = "테스트 스토리 정보"
    num_episodes = 10

    def log_fn(msg):
        print(msg)

    result = theme_gen_auto(story_info, num_episodes, log_fn=log_fn)
    print("\n=== 결과 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
