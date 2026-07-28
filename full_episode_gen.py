import random as rand
import config
import character_setup
import os
import re
import time
import json
from common_def import get_particles
from openAPI_control import call_openai_for_client, call_openai_api

# =============================================================================
# episode/ 디렉토리에서 데이터 로드 (prompts.txt, variables.json)
# =============================================================================

_EPISODE_DIR = os.path.join(os.path.dirname(__file__), "episode")

def _load_episode_file(filename):
    """episode/ 디렉토리에서 파일 로드"""
    filepath = os.path.join(_EPISODE_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        if filename.endswith(".json"):
            return json.load(f)
        return f.read()

def _load_variables():
    return _load_episode_file("variables.json")

def _load_prompts():
    """episode/prompts.txt 로드 (======key====== 형식 평문 파싱)"""
    raw = _load_episode_file("prompts.txt")
    parsed = {}
    parts = re.split(r"======([^=]+)======", raw)
    for i in range(1, len(parts), 2):
        key = parts[i].strip()
        value = parts[i + 1].rstrip("\n")
        parsed[key] = value
    return parsed

def _build_prompt(template, **kwargs):
    return template.format(**kwargs)

VARS = _load_variables()

# =============================================================================
# 헬퍼 함수들
# =============================================================================

def _extract_phase_from_progression(line):
    """progression_array 라인에서 <상태>를 추출하여 phase index 반환."""
    phase_map = VARS["phase_map"]
    match = re.search(r'<([^>]+)>', line)
    if match:
        phase_name = match.group(1).strip()
        return phase_map.get(phase_name, 0)
    return 0

def _detect_intimacy_level(ep_corruption_guides_map, ep_num):
    """EP별 타락 가이드 맵에서 해당 에피소드의 가이드를 분석해 친밀도 레벨(0~6)을 반환."""
    ep_guides = ep_corruption_guides_map.get(ep_num, {})
    protagonist_guides = ep_guides.get("protagonist", []) if isinstance(ep_guides, dict) else []
    partner_guides = ep_guides.get("partner", []) if isinstance(ep_guides, dict) else []
    all_guides = protagonist_guides + partner_guides
    if not all_guides:
        return 0

    ik = VARS["intimacy_keywords"]
    special_guides = [g for g in all_guides if "$" in g]
    if special_guides:
        special_text = " ".join(special_guides).lower()
        level = 0
        if any(kw in special_text for kw in ik["special"]["level_1"]):
            level = max(level, 1)
        if any(kw in special_text for kw in ik["special"]["level_2"]):
            level = max(level, 2)
        if any(kw in special_text for kw in ik["special"]["level_3"]):
            level = max(level, 3)
        if any(kw in special_text for kw in ik["special"]["level_4"]):
            level = max(level, 4)
        if any(kw in special_text for kw in ik["special"]["level_5"]):
            level = max(level, 5)
        return level if level > 0 else 2

    text = " ".join(all_guides).lower()
    fb = ik["fallback"]
    if any(kw in text for kw in fb["level_5"]): return 5
    if any(kw in text for kw in fb["level_4"]): return 4
    if any(kw in text for kw in fb["level_3"]): return 3
    if any(kw in text for kw in fb["level_2"]): return 2
    if any(kw in text for kw in fb["level_1"]): return 1
    return 0

def _get_pov_template(sec_key, name, name2):
    """시점 템플릿 반환 (selected_jinshugai_id에 따라 분기)"""
    jinshugai_id = getattr(config, 'selected_jinshugai_id', None)
    if jinshugai_id == 1:
        pov_tpl = VARS["pov_templates_jinshugai_1"].get(sec_key, "")
    else:
        pov_tpl = VARS["pov_templates"].get(sec_key, "")
    return pov_tpl.format(name=name, name2=name2)

def _get_progress_mood(progress_ratio):
    """진행도에 따른 주인공 감정선 반환"""
    pm = VARS["progress_moods"]
    if progress_ratio < pm["early_max"]:
        return pm["moods"]["early"]
    elif progress_ratio < pm["mid_early_max"]:
        return pm["moods"]["mid_early"]
    elif progress_ratio < pm["mid_max"]:
        return pm["moods"]["mid"]
    else:
        return pm["moods"]["late"]

def _get_partner_action(name):
    """상대방 랜덤 돌발 행동 반환"""
    action = rand.choice(VARS["partner_aftermath_actions"])
    return action.format(name=name)

def _get_honorific_hint(flag_inc, current_ep, total_episodes, name, name2):
    """에피소드 수위에 따른 호칭 지시사항 반환"""
    ht = VARS["honorific_thresholds"]
    seung_end = int(total_episodes * ht["seung_end_ratio"])
    jeon_mid = int(total_episodes * ht["jeon_mid_ratio"])

    if flag_inc == 1:
        return """
## 호칭 주의사항
* 한국어 존댓말/반말을 상황에 맞게 자연스럽게 사용하세요.
* 캐릭터의 나이, 관계, 성격에 맞는 호칭을 사용하세요.
"""
    else:
        if current_ep <= seung_end:
            return """
## 호칭 주의사항
* 한국어 존댓말/반말을 상황에 맞게 자연스럽게 사용하세요.
* 캐릭터의 나이, 관계, 성격에 맞는 호칭을 사용하세요."""
        elif current_ep <= jeon_mid:
            return """
## 호칭 주의사항
* 한국어 존댓말/반말을 상황에 맞게 자연스럽게 사용하세요.
* 캐릭터의 나이, 관계, 성격에 맞는 호칭을 사용하세요.
* 타락하면서 호칭이 바뀌는 과정을 묘사하세요."""
        else:
            return """
## 호칭 주의사항
* 한국어 존댓말/반말을 상황에 맞게 자연스럽게 사용하세요.
* 캐릭터의 나이, 관계, 성격에 맞는 호칭을 사용하세요.
* 타락하면서 호칭이 바뀌는 과정을 묘사하세요.
* 호칭이 바뀌거나 겹치는 순간을 자연스럽게 묘사하세요."""

def _build_writing_level_hint(current_ep, total_eps):
    wl = VARS["writing_level_thresholds"]
    if total_eps == 0: return ""
    progress_ratio = current_ep / total_eps
    name = config.name
    name2 = config.name2
    p1 = get_particles(name)
    p2 = get_particles(name2)

    if progress_ratio <= wl["early_max"]:
        return f"""
## 작성 수위 지시 (초반: 정숙)
* 정숙하고 자연스러운 분위기로 작성하세요.
* {name2}({name}의 상대방)과 가벼운 스킨십(손잡기, 어깨 두드리기, 머리카락 만지기)까지만 허용.
* 천박한 단어와 과한 신체 묘사는 금지.
* 캐릭터의 말투를 건전하고 일상적으로 유지."""
    elif progress_ratio <= wl["mid_early_max"]:
        return f"""
## 작성 수위 지시
* 정숙하지만 살짝 엣찌한 느낌으로
* {name}{p1['topic']}의 내면 독백으로 수치심과 쾌락을 교차 묘사."""
    elif progress_ratio <= wl["mid_max"]:
        return f"""
## 작성 수위 지시
* 청년 러브코메디 수위에서 중간정도 엣찌한 느낌으로
* {name}{p1['topic']}의 내면 독백으로 바뀌어 가는 느낌 묘사."""
    else:
        return f"""
## 작성 수위 지시
* 청년 러브코메디 수위에서 많이 엣찌한 느낌으로
* {name}{p1['topic']}이(가) 완전히 사랑에 빠진 캐릭터의 모습 묘사
* {name2}{p2['subject']}를 향한 집착과 애정을 과시하듯 표현."""

def _build_body_change_hint(current_ep, total_eps):
    name = config.name
    name2 = config.name2
    p1 = get_particles(name)
    p2 = get_particles(name2)
    body_change = getattr(config, 'theme_body_change', None)
    corruption_elements = getattr(config, 'theme_corruption_elements', [])
    progress_ratio = current_ep / total_eps if total_eps > 0 else 0

    if not body_change:
        body_change = {"name": "서큐버스화", "desc": "서큐버스로 변이"}
    body_name = body_change["name"]
    body_desc = body_change["desc"]
    corruption_text = " + ".join([c["name"] for c in corruption_elements]) if corruption_elements else ""

    bc = VARS["body_change_thresholds"]
    if progress_ratio < bc["initial_start"]:
        return ""
    elif progress_ratio < bc["early_max"]:
        return f"""
## 신체 변화 및 반응 지시 (진행도 {int(progress_ratio * 100)}% - 초기 증상)
* {name}{p1['topic']}의 몸에서 {body_name}({body_desc})의 초기 증상이 시작됩니다:
  - {body_name} 초기 증상: 체온이 살짝 오르고, {name2}{p2['topic']}의 체취가 더 강하게 느껴짐
  - {name}이 자신의 변화를 알아채고 "내가 좀 이상해졌나?" 하며 당황하는 묘사
  - {name2}의 냄새를 맡을 때 무의식적으로 코를 찌르는 미세한 반응
  - 밤에 잠들 때 {name2}{p2['topic']} 곁으로 무의식적으로 기어가는 행동"""
    elif progress_ratio < bc["mid_max"]:
        body_type_hints = VARS["body_change_types"]
        if body_name == "서큐버스화":
            return f"""
## 신체 변화 및 반응 지시 (진행도 {int(progress_ratio * 100)}% - 서큐버스화 진행)
* {name}{p1['topic']}의 몸이 서큐버스로 변이되고 있습니다:
  - 체온 상승: 평소보다 몸이 더워지고, {name2}{p2['topic']}의 손만 닿아도 전율이 감돌음
  - 체취 민감도 증가: {name2}{p2['topic']}의 냄새를 맡으면 무의식적으로 코를 찌름
  - 발정기 증상: {name2}가 곁에 없으면 불안하고, 곁에 있으면 허벅지를 비비며 흥분
  - 가슴과 엉덩이가 살짝 커지는 변화 (옷이 타이트해짐)
  - {name}이 거울을 보고 "내가 언제 이렇게..." 하며 놀라는 장면
  - {name2}의 체취를 들이마시며 "형님 냄새가 너무 좋아"라고 중얼거리는 묘사"""
        elif body_name == "BSS":
            return f"""
## 신체 변화 및 반응 지시 (진행도 {int(progress_ratio * 100)}% - BSS)
* {name}{p1['topic']}의 가슴과 엉덩이가 커지고 있습니다:
  - 평소 입던 옷이 타이트해지고, 단추가 팽팽하게 당겨짐
  - {name2}가 "언니 옷이 작아진 것 같아"라고 말하면 얼굴이 붉어짐
  - 가슴이 무거워지고, 걸을 때 흔들리는 것을 느끼며 부끄러워함
  - {name}이 거울을 보고 "내가 언제 이렇게..." 하며 놀라는 장면"""
        else:
            return f"""
## 신체 변화 및 반응 지시 (진행도 {int(progress_ratio * 100)}% - {body_name})
* {name}{p1['topic']}의 몸에서 {body_name}({body_desc})이 진행되고 있습니다:
  - 체온 상승과 {name2}{p2['topic']}에 대한 본능적 끌림 증가
  - 자신의 변화를 알아채고 당황하면서도 {name2}에게 숨기려는 묘사
  - 밤에 {name2}{p2['topic']} 곁에서 자다 무의식적으로 몸을 붙이는 행동"""
    else:
        if body_name == "서큐버스화":
            return f"""
## 신체 변화 및 반응 지시 (진행도 {int(progress_ratio * 100)}% - 서큐버스 완전체)
* {name}{p1['topic']}이 완전히 서큐버스로 변이되었습니다:
  - 체온이 높고, {name2}{p2['topic']}의 체취를 끊임없이 흡입하며 흥분
  - {name2}가 곁에 없으면 발정기처럼 숨을 헐떡이며 찾아 헤매는 증상
  - 가슴과 엉덩이가 확실히 커져 옷이 팽팽하게 당겨짐
  - {name2}{p2['subject']}의 등에 기대어 체취를 들이마시며 "더 줘" "더 냄새 맡게 해줘"라고 요구
  - 서큐버스의 본능이 깨어나 {name2}를 자신의 것으로 만들려는 집착
  - {corruption_text} + {body_name}의 영향으로 이성이 녹아내리는 묘사"""
        elif body_name == "BSS":
            return f"""
## 신체 변화 및 반응 지시 (진행도 {int(progress_ratio * 100)}% - BSS 완전체)
* {name}{p1['topic']}의 가슴과 엉덩이가 확실히 커졌습니다:
  - 평소 옷은 다 못 입고, {name2}{p2['subject']}의 옷을 빌려입음
  - 가슴이 무거워져 {name2}의 어깨에 기대어 쉰다며 접근
  - {name2}가 {name}{p1['topic']}의 가슴을 잡으면 "아, 거기 말고" 하며 부끄러워하면서도 밀어내지 않음"""
        else:
            return f"""
## 신체 변화 및 반응 지시 (진행도 {int(progress_ratio * 100)}% - {body_name} 완전체)
* {name}{p1['topic']}이 완전히 {body_name}({body_desc})되었습니다:
  - {name2}{p2['topic']}에 대한 본능적 끌림이 극대화
  - {corruption_text} + {body_name}의 영향으로 이성이 완전히 녹아듦
  - {name2}를 자신의 것으로 만들려는 집착과 본능적 행동"""

def _extract_kiskungjeonkyeol(episode_content):
    result = {'기': '', '승': '', '전': '', '결': '', 'header': ''}
    for key in ['기', '승', '전', '결']:
        # 기: 또는 [기] 형식 모두 지원
        marker = f'{key}:'
        alt_marker = f'[{key}]'
        if marker in episode_content:
            idx = episode_content.index(marker) + len(marker)
        elif alt_marker in episode_content:
            idx = episode_content.index(alt_marker) + len(alt_marker)
        else:
            continue
        rest = episode_content[idx:].strip()
        lines = rest.split('\n')
        content_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                break
            # 다른 마커 감지 (기:, [기] 모두)
            if any(f'{k}:' in stripped or f'[{k}]' in stripped for k in ['기', '승', '전', '결']):
                break
            content_lines.append(stripped)
        if content_lines:
            result[key] = ' '.join(content_lines)

    header_match = re.search(r'##\s*EP\s*\d+:\s*([^\n]+)', episode_content)
    if header_match:
        result['header'] = header_match.group(1).strip()
    else:
        situ_match = re.search(r'\[장소:[^\]]*\]\s*\[?상황:\s*([^\]\n]+)', episode_content)
        if situ_match:
            result['header'] = situ_match.group(1).strip()
        else:
            first_line = episode_content.split('\n')[0].strip()
            if first_line:
                result['header'] = first_line
    return result

# =============================================================================
# full_episode_gen (메인)
# =============================================================================

def full_episode_gen(ep_num=0, callback=None, log_file_name="debug_api_episode.log"):
    try:
        _log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
        os.makedirs(_log_dir, exist_ok=True)
        log_file = open(os.path.join(_log_dir, log_file_name), "a", encoding="utf-8")
        def log(msg):
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            log_file.write(f"[{timestamp}] {msg}\n")
            log_file.flush()

        log("=" * 60)
        log(f"[full_episode_gen] 시작 시간: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        log(f"에피소드 번호: {ep_num}")
        log(f"total_episodes: {config.total_episodes}")
        log(f"episode_gen_flag: {config.episode_gen_flag}")
        log(f"result_text 길이: {len(config.result_text) if config.result_text else 0}")
        log(f"episode_content 채움 수: {sum(1 for ep in config.episode_content if ep and ep.strip())}/{len(config.episode_content)}")
        log(f"episode_full_track 상태: {[config.episode_full_track[i] for i in range(config.total_episodes)]}")
        log("-" * 40)

        config.current_episode_index = 0
        log("[DEBUG] 기본 character_sheet(0) 호출 시작")
        default_protagonist_sheet, _ = character_setup.character_sheet(0)
        log(f"[DEBUG] default_protagonist_sheet 길이: {len(default_protagonist_sheet)}")
        log("[DEBUG] partner_sheet() 호출 시작")
        default_partner_sheet = character_setup.partner_sheet()
        log(f"[DEBUG] default_partner_sheet 길이: {len(default_partner_sheet)}")

        proto_sheets = getattr(config, 'episode_protagonist_sheets', None)
        part_sheets = getattr(config, 'episode_partner_sheets', None)
        log(f"[DEBUG] episode_protagonist_sheets: {len(proto_sheets) if proto_sheets else 'None'}개")
        log(f"[DEBUG] episode_partner_sheets: {len(part_sheets) if part_sheets else 'None'}개")

        episode_list = config.result_text if config.result_text else ""
        log(f"[DEBUG] episode_list (result_text) 길이: {len(episode_list)}")
        if episode_list:
            log(f"[DEBUG] episode_list 미리보기:\n{episode_list}")

        if ep_num == 0:
            episodes_to_gen = range(1, config.total_episodes + 1)
            log(f"[DEBUG] 전체 생성 모드: EP 1~{config.total_episodes}")
        elif ep_num == -1:
            episodes_to_gen = []
            for i in range(config.total_episodes):
                if not config.episode_full_track[i]:
                    episodes_to_gen.append(i + 1)
            if not episodes_to_gen:
                log("모든 에피소드가 이미 생성되었습니다.")
            else:
                log(f"[DEBUG] 이어서 생성 모드: {episodes_to_gen}")
        else:
            episodes_to_gen = [ep_num]
            log(f"[DEBUG] 단일 생성 모드: EP {ep_num}")

        log(f"[DEBUG] 생성할 에피소드 목록: {list(episodes_to_gen)}")
        all_chapter_content = []

        for current_ep in episodes_to_gen:
            log(f"\n{'='*40}")
            log(f"[EP{current_ep}] 시작")
            log(f"{'='*40}")

            ep_line = f"Episode {current_ep}:"
            ep_planned = ""
            for line in episode_list.split("\n"):
                if line.startswith(ep_line):
                    ep_planned = line[len(ep_line):].strip()
                    break
            log(f"[EP{current_ep}] [DEBUG] ep_planned: {'EMPTY' if not ep_planned else ep_planned}")

            info_lines = {
                "total_episodes": config.total_episodes,
                "updated_count": current_ep,
                "current_episode": current_ep,
                "status": f"[EP{current_ep}/{config.total_episodes}] 캐릭터 시트 주입..."
            }

            ep_content_raw = config.episode_content[current_ep - 1] if current_ep - 1 < len(config.episode_content) else ""
            log(f"[EP{current_ep}] [DEBUG] episode_content[{current_ep-1}] 길이: {len(ep_content_raw)}")
            if ep_content_raw:
                log(f"[EP{current_ep}] [DEBUG] episode_content[{current_ep-1}] 미리보기:\n{ep_content_raw}")
            else:
                log(f"[EP{current_ep}] [DEBUG] episode_content[{current_ep-1}]가 비어있습니다!")

            ep_sections = _extract_kiskungjeonkyeol(ep_content_raw)
            log(f"[EP{current_ep}] [DEBUG] 기/승/전/결 추출 결과:")
            log(f"  기: {'EMPTY' if not ep_sections['기'] else ep_sections['기']}")
            log(f"  승: {'EMPTY' if not ep_sections['승'] else ep_sections['승']}")
            log(f"  전: {'EMPTY' if not ep_sections['전'] else ep_sections['전']}")
            log(f"  결: {'EMPTY' if not ep_sections['결'] else ep_sections['결']}")
            log(f"  header: {ep_sections['header']}")

            progression_array = getattr(config, 'progression_array', [])
            ep_progression = progression_array[current_ep - 1] if current_ep - 1 < len(progression_array) else ""
            current_phase = _extract_phase_from_progression(ep_progression)
            log(f"[EP{current_ep}] [DEBUG] phase={current_phase}, progression={ep_progression}")

            sex_hint = ""
            intimacy_level = _detect_intimacy_level(config.ep_corruption_guides_map, current_ep)

            special_req = getattr(config, 'special_writing_req', {})
            ep_special = special_req.get(current_ep, [])
            if ep_special:
                log(f"[EP{current_ep}] [special_writing_req] 특별 작성 요청: {ep_special}")
            else:
                log(f"[EP{current_ep}] [special_writing_req] 없음")

            body_change_hint = _build_body_change_hint(current_ep, config.total_episodes)
            if body_change_hint:
                log(f"[EP{current_ep}] [DEBUG] body_change_hint 생성됨 (진행도={int(current_ep / config.total_episodes * 100)}%)")

            flag_inc = getattr(config, 'inc_flag', 0)
            honorific_hint = _get_honorific_hint(flag_inc, current_ep, config.total_episodes, config.name, config.name2)
            log(f"[EP{current_ep}] [DEBUG] honorific_hint 생성됨")

            # first_event / second_event 강조
            event_emphasis = ""
            first_event_text = getattr(config, 'first_event', '')
            second_event_text = getattr(config, 'second_event', '')
            first_event_ep = getattr(config, 'first_event_ep', -1)
            second_event_ep = getattr(config, 'second_event_ep', -1)
            if current_ep == first_event_ep and first_event_text:
                event_emphasis = f"""
## 핵심 사건 강조 (첫 사건)
* 이 에피소드에서 반드시 아래 사건을 포함하여 묘사하세요:
  - {first_event_text}
* {config.name}과 {config.name2}의 관계를 결정짓는 중요한 순간입니다."""
                log(f"[EP{current_ep}] [DEBUG] first_event 강조 적용: {first_event_text}")
            elif current_ep == second_event_ep and second_event_text:
                event_emphasis = f"""
## 핵심 사건 강조 (두 번째 사건)
* 이 에피소드에서 반드시 아래 사건을 포함하여 묘사하세요:
  - {second_event_text}
* {config.name}가 사랑에 깊게 빠지는 중요한 전환점입니다."""
                log(f"[EP{current_ep}] [DEBUG] second_event 강조 적용: {second_event_text}")

            # 에피소드 분할 범위에 따른 장르/톤 설정
            # config에서 theme_gen_auto.py가 저장한 에피소드 분할 범위 활용
            intro_end = getattr(config, 'intro_end_ep', None)
            crisis_start = getattr(config, 'crisis_start_ep', None)
            crisis_end = getattr(config, 'crisis_end_ep', None)
            ending_start = getattr(config, 'ending_start_ep', None)

            genre_tone_hint = ""
            if intro_end is not None and current_ep <= intro_end:
                genre_tone_hint = "## 장르 톤\n* 평범한 러브코메디 라이트 노벨 스타일로 작성하세요."
            elif crisis_start is not None and crisis_end is not None and crisis_start <= current_ep <= crisis_end:
                genre_tone_hint = "## 장르 톤\n* 살짝 음란한 러브코메디 라이트 노벨(청소년향) 스타일로 작성하세요."
            elif ending_start is not None and current_ep >= ending_start:
                genre_tone_hint = "## 장르 톤\n* 제약없는 성인향 음란 러브코메디 라이트 노벨 스타일로 작성하세요."

            config.messages_history = []

            ep_idx = current_ep - 1
            if proto_sheets and ep_idx < len(proto_sheets) and proto_sheets[ep_idx]:
                protagonist_sheet = proto_sheets[ep_idx]
                partner_sheet = part_sheets[ep_idx] if part_sheets and ep_idx < len(part_sheets) else default_partner_sheet
                log(f"[EP{current_ep}] [DEBUG] episode_protagonist_sheets[{ep_idx}] 사용 (길이: {len(protagonist_sheet)})")
            else:
                config.current_episode_index = ep_idx
                protagonist_sheet = default_protagonist_sheet
                partner_sheet = default_partner_sheet
                log(f"[EP{current_ep}] [DEBUG] fallback 기본 시트 사용 (episode_protagonist_sheets[{ep_idx}] 없음)")

            rag_dialog_lines = []
            rag_dialog_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "rag_dialog.txt")
            config.rag_dialog = "\n".join(rag_dialog_lines) if rag_dialog_lines else "(대사 목록 없음)"

            if current_ep == 1:
                request_extended = f"{config.name}, {config.name2}의 관계는 {config.relationship}입니다."
            else:
                request_extended = ""

            prev_episode_ref = ""
            if current_ep > 1 and current_ep - 2 >= 0:
                prev_content = config.episode_full_content[current_ep - 2]
                if prev_content:
                    prev_parts = prev_content.split("#####")
                    if len(prev_parts) >= 4:
                        prev_conclusion = prev_parts[3].strip()
                        prev_episode_ref = f"""
## 이전 에피소드 (EP{current_ep - 1}) 결말:
{prev_conclusion}...
"""

            info_lines["status"] = f"[EP{current_ep}/{config.total_episodes}] 기(Introduction) 작성..."
            ki_content = ep_sections.get('기', '')
            log(f"[EP{current_ep}] [DEBUG] ki_content 길이: {len(ki_content)}")
            ki_prompt_extra = ""
            if ki_content:
                ki_prompt_extra = f"""
## [기] 에피소드 요약:
{ki_content}

위 요약을 바탕으로 아래 지시에 따라 상세하게 작성하세요."""

            if current_ep >= 3:
                prompt_extended = """

## 핵심 원칙: 1화 = 1개의 명확한 '선(Boundary)' 넘기

한 에피소드 안에서 6~8개의 변화를 주되, 그 변화가 거시적인 진도가 아니라
**'하나의 선(Boundary)을 넘기 위한 미시적인 공방전'**이 되어야 합니다.

[기] 상황의 통제와 변수 발생 (약 1,000자 / 변화 1~2개)
* 변화 1 (명분/환경의 세팅):
* 변화 2 (평상심의 균열):

이 선을 넘기 위해서 이전 에피소드 내용에 대한 신체적/정신적 반응을 꼭 반영할 것."""
            else:
                prompt_extended = ""

            prompt_ending = f"""
**중요**: 이 에피소드는 마지막 에피소드임, 소설의 마지막이라는 느낌을 줄 수 있는 서술을 꼭 사용할 것""" if current_ep == config.total_episodes else ""

            pov_ki = _get_pov_template("ki", config.name, config.name2)
            pov_seung = _get_pov_template("seung", config.name, config.name2)
            pov_jeon = _get_pov_template("jeon", config.name, config.name2)
            pov_gyeol = _get_pov_template("gyeol", config.name, config.name2)
            pov_map = {"기": pov_ki, "승": pov_seung, "전": pov_jeon, "결": pov_gyeol}

            prompts = _load_prompts()
            user_prompt = _build_prompt(
                prompts["part1_ki"],
                prompt_ending=prompt_ending, protagonist_sheet=protagonist_sheet,
                partner_sheet=partner_sheet, request_extended=request_extended,
                prev_episode_ref=prev_episode_ref, name=config.name, name2=config.name2,
                header=ep_sections.get('header', ''), ki_prompt_extra=ki_prompt_extra,
                pov_ki=pov_ki, sex_hint=sex_hint, body_change_hint=body_change_hint,
                honorific_hint=honorific_hint, prompt_extended=prompt_extended,
                event_emphasis=event_emphasis,
                first_event=getattr(config, 'first_event', ''),
                second_event=getattr(config, 'second_event', ''),
                import_point=getattr(config, 'import_point', ''),
                genre_tone_hint=genre_tone_hint
            )
            log(f"[EP{current_ep}] [PROMPT_1] Part 1: Introduction (1차/2차 호출 통합)")
            part1_result = call_openai_api(user_prompt, callback=callback, info_lines=info_lines)
            log(f"[EP{current_ep}] [USER]\n{user_prompt}...")
            log(f"[EP{current_ep}] [AI]\n{part1_result}...")
            full_response = f"## EPISODE {current_ep} ##\n" + part1_result

            # Part 2 - 승
            info_lines["status"] = f"[EP{current_ep}/{config.total_episodes}] 승(Development) 작성..."
            seung_content = ep_sections.get('승', '')
            seung_prompt_extra = ""
            if seung_content:
                seung_prompt_extra = f"""
## [승] 에피소드 요약:
{seung_content}

위 요약을 바탕으로 아래 지시에 따라 상세하게 작성하세요."""

            if current_ep >= 3:
                prompt_extended = """

[승] 저항과 침식을 반영할 것.
* 변화 3 (방어기제 발동):
* 변화 4 (물리적/심리적 퇴로 차단):"""
            else:
                prompt_extended = ""

            user_prompt = _build_prompt(
                prompts["part2_seung"],
                prompt_ending=prompt_ending, pov_seung=pov_seung,
                seung_prompt_extra=seung_prompt_extra, sex_hint=sex_hint,
                body_change_hint=body_change_hint, honorific_hint=honorific_hint,
                prompt_extended=prompt_extended, name=config.name, name2=config.name2,
                genre_tone_hint=genre_tone_hint
            )
            log(f"[EP{current_ep}] [PROMPT_2] Part 2: Development")
            part2_result = call_openai_api(user_prompt, callback=callback, info_lines=info_lines)
            log(f"[EP{current_ep}] [USER]\n{user_prompt}...")
            log(f"[EP{current_ep}] [AI]\n{part2_result}...")
            full_response += "\n\n------------------------\n#####\n\n" + part2_result

            # Part 3 - 전
            info_lines["status"] = f"[EP{current_ep}/{config.total_episodes}] 전(Climax) 작성..."
            jeon_content = ep_sections.get('전', '')
            jeon_prompt_extra = ""
            if jeon_content:
                jeon_prompt_extra = f"""
## [전] 에피소드 요약:
{jeon_content}

위 요약을 바탕으로 아래 지시에 따라 상세하게 작성하세요."""

            if current_ep > 3:
                prompt_extended = """
[작성 가이드]
* 결정적 자극/접촉: 이번 화의 목표인 '선'을 넘는 순간입니다.
* 이성과 본능의 충돌: 이 찰나의 순간을 '시간을 멈춘 것처럼' 길게 묘사합니다.
* 음란한 장면인 경우 매우 디테일하게 행동, 신음소리를 아주 천박하게 표현할 것.
* 감각적 디테일과 심리적 붕괴에 집중하세요. 쾌락으로 인해 이성의 끈이 끊어지고 본능이 폭발하는 순간을 '시간을 느리게 확장하여' 묘사하세요. 수치심이 쾌감으로 역전되는 적나라한 묘사가 필수입니다.
* 일본 에로 라이트노벨 특유의 농밀한 심리 묘사, 질척한 신체 감각 묘사를 적극 활용하세요.
* 신음 소리("하아, 읏...", "아앗, 큭...")를 대사와 지문에 자연스럽게 섞으세요."""
            else:
                prompt_extended = ""

            user_prompt = _build_prompt(
                prompts["part3_jeon"],
                prompt_ending=prompt_ending, jeon_prompt_extra=jeon_prompt_extra,
                pov_jeon=pov_jeon, sex_hint=sex_hint, body_change_hint=body_change_hint,
                honorific_hint=honorific_hint, prompt_extended=prompt_extended,
                name=config.name, name2=config.name2,
                genre_tone_hint=genre_tone_hint
            )
            log(f"[EP{current_ep}] [PROMPT_3] Part 3: Climax")
            part3_result = call_openai_api(user_prompt, callback=callback, info_lines=info_lines)
            log(f"[EP{current_ep}] [USER]\n{user_prompt}...")
            log(f"[EP{current_ep}] [AI]\n{part3_result}...")
            full_response += "\n\n------------------------\n#####\n\n" + part3_result

            # Part 4 - 결
            info_lines["status"] = f"[EP{current_ep}/{config.total_episodes}] 결(Conclusion) 작성..."
            gyeol_content = ep_sections.get('결', '')
            gyeol_prompt_extra = ""
            if gyeol_content:
                gyeol_prompt_extra = f"""
## [결] 에피소드 요약:
{gyeol_content}

위 요약을 바탕으로 아래 지시에 따라 상세하게 작성하세요."""

            progress_ratio = current_ep / config.total_episodes
            protagonist_mood = _get_progress_mood(progress_ratio)
            partner_action = _get_partner_action(config.name)

            if current_ep >= 3:
                prompt_extended = """

[결] 여운과 잔재 (약 1,500자 / 변화 1개)
* 변화 8 (돌이킬 수 없는 흔적): 상황이 끝난 후 혼자 남았을 때, 타겟이 자신에게 남은 '흔적'을 확인합니다."""
            else:
                prompt_extended = ""

            user_prompt = _build_prompt(
                prompts["part4_gyeol"],
                prompt_ending=prompt_ending, gyeol_prompt_extra=gyeol_prompt_extra,
                pov_gyeol=pov_gyeol, name=config.name, name2=config.name2,
                partner_action=partner_action, protagonist_mood=protagonist_mood,
                body_change_hint=body_change_hint, honorific_hint=honorific_hint,
                prompt_extended=prompt_extended,
                genre_tone_hint=genre_tone_hint
            )
            log(f"[EP{current_ep}] [PROMPT_4] Part 4: Conclusion (진행도={int(progress_ratio*100)}%, 감정선={protagonist_mood[:20]}..., 파트너행동={partner_action[:20]}...)")
            part4_result = call_openai_api(user_prompt, callback=callback, info_lines=info_lines)
            log(f"[EP{current_ep}] [USER]\n{user_prompt}...")
            log(f"[EP{current_ep}] [AI]\n{part4_result}...")
            full_response += "\n\n------------------------\n#####\n\n" + part4_result

            # 에피소드 헤더 제거하고 내용만 추출
            chapter_content = re.sub(r'##\s*EPISODE\s*\d+\s*##', '', full_response).strip()

            # 7차 호출: 전체 리뷰
            info_lines["status"] = f"[EP{current_ep}/{config.total_episodes}] 리뷰 중..."

            if current_ep <= 3:
                prompt_extended = f"""
중요: 현재 에피소드 {current_ep}는 초반이므로 처음부터 음란하거나 천박할 필요는 절대 없다는 것을 명심할 것!!!
독자는 처음부터 스토리 전개 없이 막나가는 걸 원하지는 않음.
1. 각 파트의 역할이 적절한가?
2. 파트 간의 흐름이 자연스러운가? (연결고리, 장소/시간 변화)
3. {honorific_hint} (호칭 변화가 잘 지켜졌는가?)
"""
            else:
                prompt_extended = f"""
중요: 현재 에피소드 {current_ep}는 이제 스토리 중반을 넘었으니 제한없이 독자를 만족시켜야 함.
1. 각 파트의 역할이 적절한가?
2. 파트 간의 흐름이 자연스러운가? (연결고리, 장소/시간 변화)
3. 은유적이고 얌전한 표현이 쓰이지 않았는가? (조금 더 직설적이고 천박한 단어로 교체할 것을 지시할 것)
4. 1인칭 주인공의 심리 묘사(수치심 -> 쾌락 굴복)가 생생하게 담겼는가?
5. {honorific_hint} (호칭 변화가 잘 지켜졌는가?)
6. 신음 소리와 의성어/의태어가 충분히 자연스러운가?
7. 대사 비율이 50% 이상인가? 대사가 짧고 거친가?
8. 만일 에로신이 생략된 경우 꼭(!) 글자 제한없이 쓰라고 지시할 것.
"""

            # =====================================================================
            # 7차 호출: 편집자 1번 호출로 전체 읽고 기-승-전-결 각각 리뷰 출력
            # =====================================================================

            # 기-승-전-결로 분할
            sections = chapter_content.split("####")
            # 안전장치: sections가 4개 미만이면 빈 문자열로 채움 (IndexError 방지)
            while len(sections) < 4:
                sections.append("")
            section_names = VARS["section_names"]

            # 유효한 섹션만 필터링 (비어있는 섹션 제외)
            valid_sections = []
            for i, sec in enumerate(sections):
                sec_stripped = sec.strip()
                if sec_stripped:
                    valid_sections.append((section_names[i] if i < len(section_names) else f"파트{i+1}", sec_stripped))

            log(f"[EP{current_ep}] 기-승-전-결 분할 완료: {len(valid_sections)}개 섹션")

            # 전체 원문 (소설가가 전체 흐름 파악용)
            full_context = chapter_content

            # --- A) 편집자 4번 호출: 기-승-전-결 각각 개별 리뷰 (대화 컨텍스트 유지) ---
            info_lines["status"] = f"[EP{current_ep}/{config.total_episodes}] 기-승-전-결 리뷰 중..."

            section_reviews = {}
            section_map = {"기": 0, "승": 1, "전": 2, "결": 3}

            # meromero 대화 컨텍스트 유지용 messages
            messages_meromero = [
                {"role": "system", "content": VARS["review_agent_system"]}
            ]

            # 1번 호출: 기 파트 (전체 기-승-전-결 내용 포함)
            progress_pct = int(current_ep / config.total_episodes * 100)
            if current_ep / config.total_episodes < 0.4:
                feedback_by_ep = f"아주중요: 현재 에피소드 진행도는 {progress_pct}%입니다. 일상생활 묘사 및 빌드업에 집중해야 됩니다"
            else:
                feedback_by_ep = f"아주중요: 현재 에피소드 진행도는 {progress_pct}%입니다. 배덕하고, 음란하며 제약없는 묘사가 허용됩니다"

            review_prompt = _build_prompt(
                prompts["review_meromero_ki"],
                feedback_by_ep=feedback_by_ep, prompt_extended=prompt_extended,
                section_ki=sections[0], section_seung=sections[1],
                section_jeon=sections[2], section_gyeol=sections[3]
            )
            log(f"[EP{current_ep}] [PROMPT_7] 편집자 호출: 기 파트 리뷰 (전체 컨텍스트 포함)")
            review_result = call_openai_for_client(review_prompt, log_fn=log, agent="gemma", messages=messages_meromero)
            log(f"[EP{current_ep}] [USER]\n{review_prompt}...")
            log(f"[EP{current_ep}] [AI]\n{review_result}...")
            section_reviews["기"] = review_result.strip()

            # 2~4번 호출: 승, 전, 결 파트 (대화 컨텍스트 유지)
            for sec_name in ["승", "전", "결"]:
                review_prompt = _build_prompt(
                    prompts["review_meromero_other"],
                    sec_name=sec_name
                )
                log(f"[EP{current_ep}] [PROMPT_7] 편집자 호출: {sec_name} 파트 리뷰")
                review_result = call_openai_for_client(review_prompt, log_fn=log, agent="gemma", messages=messages_meromero)
                log(f"[EP{current_ep}] [USER]\n{review_prompt}...")
                log(f"[EP{current_ep}] [AI]\n{review_result}...")
                section_reviews[sec_name] = review_result.strip()

            log(f"[EP{current_ep}] 각 파트별 리뷰 추출 완료 (4번 API 호출)")

            # 전 에피소드 요약
            if current_ep > 1:
                prev_episode_summary = config.episode_content[current_ep - 2] if current_ep - 2 < len(config.episode_content) else ""
                prev_episode = f"""
[전 에피소드 요약]
{prev_episode_summary}
"""
            else:
                prev_episode = ""

            # Qwen: 대화 컨텍스트 유지하며 각 파트별 개별 호출
            section_reviews2 = {}
            section_map2 = {"기": 0, "승": 1, "전": 2, "결": 3}
            messages2 = [
                {"role": "system", "content": VARS["review_agent_system"]}
            ]

            if config.json_value.get("agent_2nd", "no") == "yes":
                review_prompt = _build_prompt(
                    prompts["review_qwen_ki"],
                    prompt_extended=prompt_extended, prev_episode=prev_episode,
                    section_ki=sections[0], section_seung=sections[1],
                    section_jeon=sections[2], section_gyeol=sections[3]
                )
                log(f"[EP{current_ep}] [PROMPT_7] 편집자2 호출: 기 파트 리뷰 (전체 컨텍스트 포함)")
                review_result = call_openai_for_client(review_prompt, log_fn=log, agent="gemma", messages=messages2)
                log(f"[EP{current_ep}] [USER]\n{review_prompt}...")
                log(f"[EP{current_ep}] [AI]\n{review_result}...")
                section_reviews2["기"] = review_result.strip()

                for sec_name in ["승", "전", "결"]:
                    review_prompt = _build_prompt(
                        prompts["review_qwen_other"],
                        sec_name=sec_name
                    )
                    log(f"[EP{current_ep}] [PROMPT_7] 편집자2 호출: {sec_name} 파트 리뷰")
                    review_result = call_openai_for_client(review_prompt, log_fn=log, agent="gemma", messages=messages2)
                    log(f"[EP{current_ep}] [USER]\n{review_prompt}...")
                    log(f"[EP{current_ep}] [AI]\n{review_result}...")
                    section_reviews2[sec_name] = review_result.strip()

                log(f"[EP{current_ep}] 각 파트별 리뷰 추출 완료 (4번 API 호출)")
            else:
                log(f"[EP{current_ep}] agent_2nd=no이므로 Qwen 호출 skip")

            # --- B) 소설가가 각 섹션별 리뷰를 사용하여 개별 재작성 ---
            info_lines["status"] = f"[EP{current_ep}/{config.total_episodes}] 기-승-전-결 재작성 중..."
            revised_sections = []

            config.messages_history = []

            if current_ep / config.total_episodes < 0.4:
                another_feedback = "아주중요: 현재 에피소드는 초반이므로 편집자의 리뷰를 순화해서 받아드릴 것! 편집자는 처음부터 수위를 높이고 싶지만 너무 어색해짐"
            else:
                another_feedback = "아주중요: 현재 에피소드는 초반이후이므로 편집자의 리뷰 반영할 것"

            for i, (sec_name, sec_content) in enumerate(valid_sections):
                context_block = f"""

## 전체 에피소드 컨텍스트 (흐름 파악용):
{full_context}""" if i == 0 else ""

                revise_prompt = _build_prompt(
                    prompts["revise_section"],
                    sec_name=sec_name, another_feedback=another_feedback,
                    review1=section_reviews.get(sec_name, ''),
                    review2=section_reviews2.get(sec_name, ''),
                    pov=pov_map.get(sec_name, ''),
                    sec_content=sec_content, context_block=context_block
                )
                log(f"[EP{current_ep}] [PROMPT_8_{sec_name}] '{sec_name}' 파트 재작성")
                revised_sec = call_openai_api(revise_prompt, callback=callback, info_lines=info_lines)
                revised_sections.append(revised_sec)
                log(f"[EP{current_ep}] [USER]\n{revise_prompt}...")
                log(f"[EP{current_ep}] [AI]\n{revised_sec}...")

            # 재작성된 기-승-전-결 하나로 합치기
            revised_content = "\n\n----------------------------------\n#####\n\n".join(revised_sections)

            # 수정된 내용 저장
            config.episode_full_original_content[current_ep - 1] = chapter_content
            config.episode_full_content[current_ep - 1] = revised_content
            config.episode_full_track[current_ep - 1] = True
            all_chapter_content.append(revised_content)

            # 마크다운 파일 저장 (리뷰 전/후)
            result_dir = os.path.join("result")
            os.makedirs(result_dir, exist_ok=True)

            filename_before = f"episode_{current_ep:02d}.md"
            filepath_before = os.path.join(result_dir, filename_before)
            with open(filepath_before, "w", encoding="utf-8") as f:
                f.write(f"# Episode {current_ep}\n\n")
                f.write(chapter_content)
            log(f"[EP{current_ep}] 리뷰 전 저장: {filepath_before}")

            filename_after = f"episode_{current_ep:02d}_reviewed.md"
            filepath_after = os.path.join(result_dir, filename_after)
            with open(filepath_after, "w", encoding="utf-8") as f:
                f.write(f"# Episode {current_ep}\n\n")
                f.write(revised_content)
            log(f"[EP{current_ep}] 리뷰 후 저장: {filepath_after}")

            config.messages_history = []
            log(f"[EP{current_ep}] 완료 (기-승-전-결별 리뷰+수정 적용)")

        final_result = "\n\n".join(all_chapter_content)
        log(f"[full_episode_gen] 완료 - 총 {len(all_chapter_content)}개 에피소드 생성")
        log_file.close()
        return final_result

    except Exception as e:
        log_file.close()
        return f"전체 소설 생성 중 오류 발생: {e}\n(API 키 설정 등을 확인하세요)"
