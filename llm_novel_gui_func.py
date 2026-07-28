"""
llm_novel_gui_func.py
=====================
GUI 화면 그리기와 무관한 핵심 로직 함수들을 분리한 모듈.

llm_novel_gui.py는 화면 표시(curses 그리기, 키 입력 처리)만 담당하고,
실제 GUI에서 필요한 부가 작업(저장/복구/파싱/빌드 등)은 본 모듈에서 처리한다.

추후 수정 시에도 동일한 원칙으로 분리하여 유지보수성을 확보한다.
"""

import json
import logging
import os
import re
import yaml
import sys
import io
import importlib
import hashlib
import uuid
import random as rand
import config
import character_setup
import story_gen
import full_episode_gen
import plot_gen
import anima_gen
import openAPI_control
from persona import generate_ultimate_heroine_progression

SAVE_STATE_FILE = os.path.join("data", "save_state.json")

# 모듈 레벨 로거
logger = logging.getLogger(__name__)


def init_logger(log_file: str = None, level: int = logging.DEBUG) -> None:
    """로거를 초기화합니다.

    Args:
        log_file: 로그 파일 경로
        level: 로그 레벨 (기본 DEBUG)
    """
    if logger.handlers:
        return  # 이미 초기화됨

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logger.setLevel(level)

    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


# -------------------------------------------------------------------------
# Config 저장/복구 관련 함수
# -------------------------------------------------------------------------

def get_config_vars() -> dict:
    """config 모듈의 모든 변수를 딕셔너리로 추출합니다."""
    exclude_vars = {
        'body_dic', 'messages_history', 'system_prompt', 'json_value',
        'json', 'rand', 'ef', 'f', 'episode_setup',
    }
    vars_dict = {}
    for key in dir(config):
        if not key.startswith('_'):
            val = getattr(config, key)
            if not callable(val) and key not in exclude_vars:
                vars_dict[key] = val
    return vars_dict


def save_config_state() -> None:
    """config의 모든 변수를 JSON 파일로 저장합니다."""
    try:
        vars_dict = get_config_vars()
        with open(SAVE_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(vars_dict, f, ensure_ascii=False, indent=2)
        logger.info("Config 저장 성공: %s (%d개 변수)", SAVE_STATE_FILE, len(vars_dict))
    except Exception as e:
        logger.error("Config 저장 실패: %s", e)


def load_config_state() -> None:
    """JSON 파일에서 config 변수를 복구합니다."""
    if not os.path.exists(SAVE_STATE_FILE):
        logger.debug("저장된 config 파일이 없음: %s", SAVE_STATE_FILE)
        return
    try:
        with open(SAVE_STATE_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            saved_vars = json.loads(content)
        for key, val in saved_vars.items():
            setattr(config, key, val)
        logger.info("Config 복구 성공: %s (%d개 변수)", SAVE_STATE_FILE, len(saved_vars))
    except json.JSONDecodeError as e:
        logger.error("Config 복구 실패 (JSON 파싱 오류): %s", e)
    except Exception as e:
        logger.error("Config 복구 실패: %s", e)


def reset_config_state() -> None:
    """저장된 config 상태를 삭제하고 기본값으로 초기화합니다."""
    try:
        if os.path.exists(SAVE_STATE_FILE):
            os.remove(SAVE_STATE_FILE)
            logger.info("저장된 config 파일 삭제: %s", SAVE_STATE_FILE)
        # 명령줄 인자 값 보존
        _cmd_job = getattr(config, 'cmd_job', None)
        _cmd_job2 = getattr(config, 'cmd_job2', None)
        _inc_flag = getattr(config, 'inc_flag', 0)
        importlib.reload(config)
        # 명령줄 인자 값 복원
        config.cmd_job = _cmd_job
        config.cmd_job2 = _cmd_job2
        config.inc_flag = _inc_flag
        logger.info("Config 초기화 완료 (모듈 리로드)")
    except Exception as e:
        logger.error("Config 초기화 실패: %s", e)


def load_config_export() -> str:
    """data/config_export.yaml 파일을 읽어 config 변수를 업데이트합니다 (YAML/JSON 호환)."""
    export_file = os.path.join("data", "config_export.yaml")
    if not os.path.exists(export_file):
        logger.debug("config_export.yaml이 없음")
        return ""
    try:
        with open(export_file, "r", encoding="utf-8") as f:
            content = f.read()
        # YAML로 로드 (JSON도 YAML의 부분집합이므로 호환됨)
        exported_vars = yaml.load(content, Loader=yaml.FullLoader)
        if not exported_vars:
            logger.debug("config_export.yaml이 비어 있음")
            return ""
        for key, val in exported_vars.items():
            setattr(config, key, val)
        logger.info("config_export.yaml에서 %d개 변수 로드 완료", len(exported_vars))
        return "config_export.yaml"
    except Exception as e:
        logger.error("config_export.yaml 로드 실패: %s", e)
        return ""


# -------------------------------------------------------------------------
# Progression 생성 및 파싱
# -------------------------------------------------------------------------

def generate_and_parse_progression() -> str:
    """generate_ultimate_heroine_progression을 호출하고 반환값을 사용하여 config.progression_array에 저장."""
    total_eps = config.total_episodes
    logger.info("Progression 생성 시작 (total_episodes=%d)", total_eps)

    # stdout 캡처 (표시용)
    old_stdout = sys.stdout
    sys.stdout = captured = io.StringIO()
    try:
        result = generate_ultimate_heroine_progression(total_eps)
    finally:
        sys.stdout = old_stdout

    # 반환값의 episodes 직접 사용
    progression_array = []
    for ep in result["episodes"]:
        desc = f"{ep['animal_desc']} ({ep['matrix_desc']})"
        progression_array.append(desc)

    config.progression_array = progression_array
    config.persona_result = result
    logger.info("Progression 생성 완료 (총 %d개 에피소드)", len(progression_array))
    return f"Progression 생성 완료 (총 {len(progression_array)}개 에피소드)"


# -------------------------------------------------------------------------
# 에피소드 파싱 및 테이블 빌드
# -------------------------------------------------------------------------

def split_episodes(text: str) -> list:
    """## EPISODE N ## 패턴으로 텍스트를 에피소드 단위로 분리합니다.

    패턴이 하나도 없으면 전체 텍스트를 단일 에피소드로 반환합니다.
    빈 텍스트이면 빈 리스트를 반환합니다.
    """
    if not text or not text.strip():
        return []
    pattern = r'(##\s*EPISODE\s*\d+\s*##)'
    parts = re.split(pattern, text)
    episodes = []
    current_episode = ""
    for part in parts:
        if re.match(pattern, part):
            if current_episode:
                episodes.append(current_episode.strip())
            current_episode = part + "\n"
        else:
            current_episode += part
    if current_episode:
        episodes.append(current_episode.strip())
    # 패턴이 없으면 전체 텍스트를 단일 에피소드로 반환
    if not episodes:
        return [text.strip()]
    return episodes


def build_episode_full_track_table() -> str:
    """episode_full_track 상태를 테이블 문자열로 반환합니다.

    열 의미:
      기 = 에피소드 요약(episode_content) 존재
      승 = 에피소드 본문(episode_full_content) 존재
      전 = episode_full_track 플래그 설정
      결 = result/episode_XX.md 파일 저장
    """
    total_eps = config.total_episodes
    lines = []
    lines.append("=== 스토리 생성 현황 (Episode Full Track) ===\n")
    lines.append(f"{'Ep':>4} | {'기':>4} | {'승':>4} | {'전':>4} | {'결':>4} | 상태")
    lines.append("-" * 50)

    for i in range(total_eps):
        ep_num = i + 1
        has_summary = bool(config.episode_content[i].strip()) if i < len(config.episode_content) else False
        has_full_content = bool(config.episode_full_content[i].strip()) if i < len(config.episode_full_content) else False
        tracked = config.episode_full_track[i] if i < len(config.episode_full_track) else False
        md_path = os.path.join("result", f"episode_{ep_num:02d}.md")
        has_md_file = os.path.exists(md_path)
        status = "✓" if (tracked and (has_full_content or has_md_file)) else (" " if tracked else "?")
        lines.append(
            f"{ep_num:>4} "
            f"| {'O' if has_summary else ' ':>4} "
            f"| {'O' if has_full_content else ' ':>4} "
            f"| {'O' if tracked else ' ':>4} "
            f"| {'O' if has_md_file else ' ':>4} "
            f"| {status}"
        )

    completed = sum(1 for t in config.episode_full_track if t)
    lines.append(f"\n완료: {completed}/{config.total_episodes}")
    lines.append("\n[W] + 에피소드 번호: 단일 에피소드 작성")
    lines.append("[W] + 0: 전체 에피소드 작성")
    return "\n".join(lines)


# -------------------------------------------------------------------------
# Config 파일 내보내기/복구
# -------------------------------------------------------------------------

def export_config_to_file(filepath: str) -> str:
    """config 변수를 config.py 정의 순서대로 YAML 파일로 내보냅니다."""
    try:
        export_order = [
            "json_value",
            "total_episodes",
            "episode_content",
            "episode_track",
            "episode_full_content",
            "episode_full_original_content",
            "episode_full_track",
            "episode_protagonist_sheets", "episode_partner_sheets",
            "name", "sex", "nationality", "age", "job", "job_attribute",
            "objective", "personality_real", "personality_text", "rel1", "rel1_update",
            "happiness",
            "name2", "sex2", "nationality2", "age2", "job2", "appearance2",
            "personality2", "outfit2", "talking_style2",
            "hair_color", "hair_style", "eye_color", "eye_shape", "skin_color",
            "face_style", "acc", "clothes",
            "breasts_size", "hip_size", "body_size",
            "bimbo_clothes1", "bimbo_clothes2",
            "love_value",
            "plot", "plot_result", "result_text",
            "first_trigger", "second_trigger",
            "first_event", "second_event",
            "first_event_ep", "second_event_ep",
            "rag_word", "rag_dialog",
            # 테마 설정
            "change_awareness", "corruption_flow", "corruption_reason",
            "resistance_reason", "selected_jinshugai_id", "guide_num",
            # 테마 임시 변수
            "theme_job1", "theme_job2", "theme_age_diff_min", "theme_age_diff_max",
            "temp_theme",
            # theme_agent 결과
            "theme_breeds", "theme_jinshugai", "theme_events",
            "theme_body_change", "theme_corruption_elements",
            # 타락 가이드
            "corruption_elements", "body_change", "body_change_sign",
            "corruption_guides", "partner_corruption_guides",
            # 트리거
            "abnormal_trigger", "crisis_trigger",
            # 페르소나
            "persona_text", "relationship", "relationship_development",
            # 잡 정보
            "job_raw",
            # import_point
            "import_point",
            # 현재 에피소드 인덱스
            "current_episode_index",
            # progression / 플래그
            "progression_array",
            "episode_gen_flag",
            # Progress tracking
            "plot_hash", "theme_auto_complete_flag", "progress_step",
            # OpenAPI
            "stream_enb",
            # RP 설정
            "muscle_enb", "minion_enb", "vulgarity_enb",
            # ANIMA 태그 배열
            "face_tag", "makeup_tag", "marks_tag", "body_tag",
            "bodystyle_tag", "exposure_tag", "p_exposure_tag", "background_tag",
            # ANIMA 스칼라
            "body_shape", "current_level", "episode_num", "episode_step",
            # ANIMA 표현/변화 배열
            "expression_arr", "changes_arr", "expression",
            # ANIMA 추가 데이터
            "sentences_anima", "location", "pose", "clothes_simple", "action_tag",
            # ANIMA 리뷰 배열
            "review_stats", "review_safety", "review_pose",
            "review_location", "review_notes",
            # EP별 특별 작성 요청
            "special_writing_req",
            # EP별 타락 가이드 맵
            "ep_corruption_guides_map",
            # Extended: 성경험 및 Phase별 카운터
            "sex_count", "inc_flag", "masturbation_count", "patting_count",
            "normal_sex_count", "reverse_sex_count", "cowboy_sex_count",
            "anal_sex_count", "pose_sex_count", "episode_snapshots",
        ]
        vars_dict = {}
        for var in export_order:
            val = getattr(config, var, None)
            if val is not None:
                vars_dict[var] = val
        # 기존 파일 삭제 후 새로 생성
        if os.path.exists(filepath):
            os.remove(filepath)
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(vars_dict, f, allow_unicode=True, default_flow_style=False,
                      sort_keys=False, width=120)
        logger.info("설정 내보내기 성공: %s (%d개 변수)", filepath, len(vars_dict))
        return f"설정 내보내기 성공: {filepath}"
    except Exception as e:
        logger.error("설정 내보내기 실패: %s", e)
        return f"설정 내보내기 실패: {e}"


def restore_config_from_file(filepath: str) -> str:
    """지정된 파일에서 config 변수를 복구합니다 (YAML/JSON 호환)."""
    if not os.path.exists(filepath):
        logger.warning("복구 파일을 찾을 수 없음: %s", filepath)
        return f"파일을 찾을 수 없습니다: {filepath}"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            # yaml.safe_load는 JSON도 YAML 서브셋으로 자동 파싱
            saved_vars = yaml.safe_load(f)
        for key, val in saved_vars.items():
            setattr(config, key, val)
        logger.info("설정 복구 성공: %s (총 %d개 변수)", filepath, len(saved_vars))
        return f"설정 복구 성공: {filepath} (총 {len(saved_vars)}개 변수)"
    except Exception as e:
        logger.error("설정 복구 실패: %s", e)
        return f"설정 복구 실패: {e}"


def archive_to_done(result_dir: str = "result", comfyui_dir: str = None, done_dir: str = "done") -> str:
    """전체 자동 실행 완료 후 result/의 markdown과 ComfyUI output의 png를 done/book{N}/로 아카이브.

    Args:
        result_dir: 마크다운 파일이 있는 디렉토리 (기본 "result")
        comfyui_dir: PNG 파일이 있는 ComfyUI output 디렉토리 (기본 ~/AI/ComfyUI/output)
        done_dir: 아카이브 대상 디렉토리 (기본 "done")

    Returns:
        결과 메시지 문자열
    """
    if comfyui_dir is None:
        comfyui_dir = os.path.join(os.path.expanduser("~"), "AI", "ComfyUI", "output")

    try:
        # 1. 다음 book 번호 결정 (기존 done/book{N}/ 중 최대 N+1)
        if os.path.exists(done_dir):
            existing_books = [
                d for d in os.listdir(done_dir)
                if os.path.isdir(os.path.join(done_dir, d)) and re.match(r'^book\d+$', d)
            ]
            if existing_books:
                max_num = max(int(re.search(r'\d+', d).group()) for d in existing_books)
                book_num = max_num + 1
            else:
                book_num = 1
        else:
            book_num = 1

        dest_dir = os.path.join(done_dir, f"book{book_num}")
        os.makedirs(dest_dir, exist_ok=True)

        # 2. result/의 .md 파일 복사
        md_count = 0
        if os.path.exists(result_dir):
            for fname in os.listdir(result_dir):
                if fname.endswith(".md"):
                    src = os.path.join(result_dir, fname)
                    dst = os.path.join(dest_dir, fname)
                    import shutil
                    shutil.copy2(src, dst)
                    md_count += 1
                    logger.info("아카이브: %s -> %s", src, dst)

        # 3. ComfyUI 큐가 비어질 때까지 HTTP API 폴링으로 대기
        logger.info("ComfyUI 큐 대기 시작...")
        try:
            import time
            import json
            import urllib.request

            # HTTP API로 큐 상태를 30초마다 확인 (최대 30회 = 15분)
            for poll in range(30):
                try:
                    with urllib.request.urlopen("http://127.0.0.1:8188/queue", timeout=5) as resp:
                        queue_data = json.loads(resp.read())
                    running = len(queue_data.get("queue_running", []))
                    pending = len(queue_data.get("queue_pending", []))
                    remaining = running + pending
                    if remaining == 0:
                        logger.info("ComfyUI 큐 비었음 - 60초 대기 후 파일 복사")
                        time.sleep(60)
                        break
                    logger.info(f"ComfyUI 큐: running={running}, pending={pending} (남은 {remaining}개, {poll+1}/30회)")
                except Exception as e:
                    logger.info(f"ComfyUI 큐 확인 실패: {e}")
                time.sleep(30)
        except Exception as e:
            logger.info(f"ComfyUI 큐 대기 실패: {e} - 즉시 파일 복사")

        # 4. ComfyUI output의 .png 파일 복사 (하위 디렉토리 포함)
        png_count = 0
        if os.path.exists(comfyui_dir):
            for root, dirs, files in os.walk(comfyui_dir):
                for fname in files:
                    if fname.lower().endswith(".png"):
                        src = os.path.join(root, fname)
                        dst = os.path.join(dest_dir, fname)
                        import shutil
                        shutil.copy2(src, dst)
                        png_count += 1

        logger.info("아카이브 완료: %s (md=%d, png=%d)", dest_dir, md_count, png_count)
        return f"아카이브 완료: {dest_dir} (markdown={md_count}개, png={png_count}개)"
    except Exception as e:
        logger.error("아카이브 실패: %s", e)
        return f"아카이브 실패: {e}"


# -------------------------------------------------------------------------
# Progress tracking 관련 함수 (1번 메뉴 theme_gen_auto 전용)
# -------------------------------------------------------------------------

PROGRESS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress")


def generate_plot_hash() -> str:
    """1번 메뉴 실행 시 고유 hash code를 생성하여 반환합니다.

    Returns:
        16자리 hex hash 문자열
    """
    raw_hash = uuid.uuid4().hex[:16]
    config.plot_hash = raw_hash
    logger.info("Plot hash 생성: %s", raw_hash)
    return raw_hash


def get_theme_auto_updated_vars() -> dict:
    """1번 메뉴(theme_gen_auto)에서 업데이트된 변수만 추출합니다.

    theme_gen_auto 파이프라인에서 변경되는 변수만 포함합니다.
    순서는 theme_gen_auto.py의 실행 순서를 따릅니다.

    Returns:
        변수명: 값 딕셔너리
    """
    theme_auto_vars_order = [
        # [1] jinshugai 템플릿
        "selected_jinshugai_id",
        # [2] resistance/corruption reason
        "resistance_reason", "corruption_reason",
        # [3] 직업 및 나이
        "sex", "sex2", "job", "age", "job2", "age2",
        # [4] body_dic 초기화 + 아키타입
        "breasts_size", "hip_size", "body_size",
        "hair_color", "hair_style", "eye_color", "skin_color",
        "face_style", "acc", "body_shape", "personality_real",
        # [5] 상대방 외모
        "appearance2", "talking_style2", "personality2", "outfit2",
        # [6] 이름
        "name", "name2", "nationality", "nationality2",
        # [7] 관계
        "relationship",
        # [8] Progression
        "persona_text",
        # [9] 트리거
        "first_trigger", "second_trigger",
        # [10] 관계 발전
        "relationship_development",
        # [11] 타락 요소 + 신체 변화
        "corruption_elements", "body_change", "body_change_sign",
        "change_awareness", "corruption_flow",
        # [12] 위기 트리거
        "crisis_trigger",
        # [13] 진행도 사건
        "theme_breeds", "theme_events",
        # [14] 비정상 트리거 + 빙보 복장
        "abnormal_trigger", "bimbo_clothes1", "bimbo_clothes2",
        # [15] LLM 테마 생성
        "plot",
        # [16] LLM 타락 가이드
        "corruption_guides", "partner_corruption_guides",
        # [17] 최종 정리
        "theme_body_change", "theme_corruption_elements", "theme_jinshugai",
        "progression_array",
        "theme_job1", "theme_job2", "theme_age_diff_max", "theme_age_diff_min",
        "temp_theme", "plot_result", "rel1_update",
        # 기타
        "rel1", "job_attribute", "objective", "personality_text",
        "happiness", "clothes", "love_value",
    ]
    vars_dict = {}
    for var in theme_auto_vars_order:
        val = getattr(config, var, None)
        if val is not None:
            vars_dict[var] = val
    return vars_dict


def save_theme_vars_yaml(hash_code: str, vars_dict: dict = None) -> str:
    """1번에서 업데이트된 변수를 progress/에 YAML로 저장합니다.

    YAML 첫 줄에 hash code를 포함하여 1번과 4번 파일의 일치 여부를
    확인할 수 있도록 합니다.

    Args:
        hash_code: plot_hash 코드
        vars_dict: 저장할 변수 딕셔너리 (None이면 get_theme_auto_updated_vars() 호출)

    Returns:
        저장된 파일 경로
    """
    if vars_dict is None:
        vars_dict = get_theme_auto_updated_vars()

    os.makedirs(PROGRESS_DIR, exist_ok=True)
    filepath = os.path.join(PROGRESS_DIR, f"theme_{hash_code}.yaml")

    try:
        # 기존 파일 삭제 후 새로 생성
        if os.path.exists(filepath):
            os.remove(filepath)

        with open(filepath, "w", encoding="utf-8") as f:
            # 첫 줄에 hash code 주석으로 기록
            f.write(f"# plot_hash: {hash_code}\n")
            yaml.dump(vars_dict, f, allow_unicode=True, default_flow_style=False,
                      sort_keys=False, width=120)
        logger.info("Theme 변수 YAML 저장: %s (%d개 변수)", filepath, len(vars_dict))
        return filepath
    except Exception as e:
        logger.error("Theme 변수 YAML 저장 실패: %s", e)
        return ""


def save_progress_state(hash_code: str, step: int, plot_json: dict = None) -> str:
    """진행 상태를 progress/에 JSON으로 저장합니다.

    plot.json과 hash code를 포함한 global 정보를 저장합니다.

    Args:
        hash_code: plot_hash 코드
        step: 진행 단계 (0=초기, 1=플롯완료, 2=에피소드완료, 3=스토리완료)
        plot_json: plot.json 데이터 (None이면 현재 config.json_value 사용)

    Returns:
        저장된 파일 경로
    """
    os.makedirs(PROGRESS_DIR, exist_ok=True)
    filepath = os.path.join(PROGRESS_DIR, f"progress_{hash_code}.json")

    try:
        state = {
            "plot_hash": hash_code,
            "progress_step": step,
            "theme_auto_complete": config.theme_auto_complete_flag,
            "total_episodes": config.total_episodes,
            "plot": config.plot,
            "plot_result": config.plot_result,
            "name": config.name,
            "name2": config.name2,
            "job": config.job,
            "job2": config.job2,
            "age": config.age,
            "age2": config.age2,
        }
        if plot_json:
            state["plot_json"] = plot_json
        else:
            state["plot_json"] = config.json_value

        # 기존 파일 삭제 후 새로 생성
        if os.path.exists(filepath):
            os.remove(filepath)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        logger.info("Progress 상태 JSON 저장: %s (step=%d)", filepath, step)
        return filepath
    except Exception as e:
        logger.error("Progress 상태 JSON 저장 실패: %s", e)
        return ""


def save_episodes_and_sheets_to_progress(hash_code: str) -> list:
    """에피소드 내용과 캐릭터 시트를 progress 디렉토리에 텍스트 파일로 저장합니다.

    Args:
        hash_code: plot_hash 코드

    Returns:
        저장된 파일 경로 리스트
    """
    os.makedirs(PROGRESS_DIR, exist_ok=True)
    saved_files = []

    total_eps = getattr(config, 'total_episodes', 10)
    episode_content = getattr(config, 'episode_content', [])
    proto_sheets = getattr(config, 'episode_protagonist_sheets', [])
    partner_sheets = getattr(config, 'episode_partner_sheets', [])

    for i in range(total_eps):
        ep_num = i + 1
        ep_text = episode_content[i] if i < len(episode_content) else ""
        proto_sheet = proto_sheets[i] if i < len(proto_sheets) else ""
        partner_sheet = partner_sheets[i] if i < len(partner_sheets) else ""

        # 에피소드 내용 저장
        ep_filepath = os.path.join(PROGRESS_DIR, f"ep{ep_num:02d}_{hash_code}.txt")
        try:
            with open(ep_filepath, "w", encoding="utf-8") as f:
                f.write(f"=== Episode {ep_num} ===\n\n")
                f.write(f"# 주인공 ({getattr(config, 'name', '')})\n")
                f.write(f"직업: {getattr(config, 'job', '')}\n")
                f.write(f"나이: {getattr(config, 'age', '')}\n\n")
                f.write(f"# 상대방 ({getattr(config, 'name2', '')})\n")
                f.write(f"직업: {getattr(config, 'job2', '')}\n")
                f.write(f"나이: {getattr(config, 'age2', '')}\n\n")
                f.write(f"--- 에피소드 내용 ---\n\n")
                f.write(ep_text + "\n\n")
                f.write(f"--- 주인공 캐릭터 시트 ---\n\n")
                f.write(proto_sheet + "\n\n")
                f.write(f"--- 상대방 캐릭터 시트 ---\n\n")
                f.write(partner_sheet + "\n")
            saved_files.append(ep_filepath)
        except Exception as e:
            logger.error("에피소드 %d 저장 실패: %s", ep_num, e)

    logger.info("에피소드/캐릭터시트 저장 완료: %d개 파일 (hash=%s)", len(saved_files), hash_code)
    return saved_files


def load_progress_state() -> dict:
    """progress/ 디렉토리에서 가장 최근 진행 상태를 로드합니다.

    Returns:
        진행 상태 딕셔너리 (파일 없음이면 빈 dict)
    """
    if not os.path.exists(PROGRESS_DIR):
        logger.debug("Progress 디렉토리 없음: %s", PROGRESS_DIR)
        return {}

    # progress_*.json 파일中寻找 가장 최근 파일
    progress_files = []
    for fname in os.listdir(PROGRESS_DIR):
        if fname.startswith("progress_") and fname.endswith(".json"):
            fpath = os.path.join(PROGRESS_DIR, fname)
            progress_files.append((fpath, os.path.getmtime(fpath)))

    if not progress_files:
        logger.debug("Progress 파일 없음")
        return {}

    # 가장 최근 파일 선택
    progress_files.sort(key=lambda x: x[1], reverse=True)
    latest_file = progress_files[0][0]

    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        logger.info("Progress 상태 로드: %s (hash=%s, step=%d)",
                    latest_file, state.get("plot_hash", "unknown"),
                    state.get("progress_step", 0))
        return state
    except Exception as e:
        logger.error("Progress 상태 로드 실패: %s", e)
        return {}


def load_episodes_from_progress(hash_code: str) -> list:
    """progress/ep{N:02d}_{hash}.txt 파일에서 에피소드 내용(기/승/전/결)을 로드합니다.

    Args:
        hash_code: plot_hash 코드

    Returns:
        에피소드 내용 리스트 (기/승/전/결 추출된 텍스트)
    """
    if not hash_code or not os.path.exists(PROGRESS_DIR):
        return []

    total_eps = getattr(config, 'total_episodes', 10)
    episode_contents = []

    for i in range(total_eps):
        ep_num = i + 1
        ep_filepath = os.path.join(PROGRESS_DIR, f"ep{ep_num:02d}_{hash_code}.txt")

        if not os.path.exists(ep_filepath):
            episode_contents.append("")
            continue

        try:
            with open(ep_filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # --- 에피소드 내용 --- 섹션 추출
            start_marker = "--- 에피소드 내용 ---"
            end_marker = "--- 주인공 캐릭터 시트 ---"

            if start_marker in content and end_marker in content:
                start_idx = content.index(start_marker) + len(start_marker)
                end_idx = content.index(end_marker)
                ep_text = content[start_idx:end_idx].strip()
            else:
                ep_text = content

            # 기/승/전/결 추출
            sections = {'기': '', '승': '', '전': '', '결': ''}
            for key in ['기', '승', '전', '결']:
                marker = f'{key}:'
                if marker in ep_text:
                    idx = ep_text.index(marker) + len(marker)
                    rest = ep_text[idx:].strip()
                    lines = rest.split('\n')
                    content_lines = []
                    for line in lines:
                        stripped = line.strip()
                        if not stripped:
                            break
                        # 다른 마커 감지
                        if any(f'{k}:' in stripped for k in ['기', '승', '전', '결']):
                            break
                        # ##EPISODE N: 패턴 감지
                        if re.match(r'##\s*EPISODE\s*\d+', stripped):
                            break
                        content_lines.append(stripped)
                    if content_lines:
                        sections[key] = ' '.join(content_lines)

            # 기/승/전/결 형식으로 재조립
            result_parts = []
            for key in ['기', '승', '전', '결']:
                if sections[key]:
                    result_parts.append(f"{key}:\n{sections[key]}")

            episode_contents.append('\n\n'.join(result_parts))
            logger.info("에피소드 %d 로드 완료 (hash=%s)", ep_num, hash_code)

        except Exception as e:
            logger.error("에피소드 %d 로드 실패: %s", ep_num, e)
            episode_contents.append("")

    return episode_contents


def verify_hash_match(hash_code: str) -> bool:
    """hash code가 현재 config와 일치하는지 확인합니다.

    Args:
        hash_code: 확인할 hash 코드

    Returns:
        일치하면 True
    """
    # theme YAML 파일 존재 확인
    yaml_path = os.path.join(PROGRESS_DIR, f"theme_{hash_code}.yaml")
    json_path = os.path.join(PROGRESS_DIR, f"progress_{hash_code}.json")

    if not os.path.exists(yaml_path) or not os.path.exists(json_path):
        return False

    # JSON의 hash 확인
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        return state.get("plot_hash") == hash_code
    except Exception:
        return False


def complete_theme_auto() -> None:
    """1번 메뉴(theme_gen_auto) 완료 처리.

    flag 설정 + progress 상태 저장 + theme 변수 YAML 저장
    """
    hash_code = config.plot_hash
    if not hash_code:
        logger.warning("plot_hash가 없음. 생성跳过.")
        return

    # 1. flag 설정
    config.theme_auto_complete_flag = True
    config.progress_step = 1

    # 2. theme 변수 YAML 저장
    vars_dict = get_theme_auto_updated_vars()
    save_theme_vars_yaml(hash_code, vars_dict)

    # 3. progress 상태 JSON 저장
    save_progress_state(hash_code, 1)

    logger.info("1번 메뉴 완료 처리: hash=%s, step=1", hash_code)


def clear_progress_directory() -> int:
    """progress/ 디렉토리의 모든 파일을 삭제합니다.

    Returns:
        삭제된 파일 개수
    """
    if not os.path.isdir(PROGRESS_DIR):
        return 0

    deleted_count = 0
    for fname in os.listdir(PROGRESS_DIR):
        fpath = os.path.join(PROGRESS_DIR, fname)
        try:
            if os.path.isfile(fpath):
                os.remove(fpath)
                deleted_count += 1
                logger.info("Progress 파일 삭제: %s", fname)
        except Exception as e:
            logger.warning("Progress 파일 삭제 실패 (%s): %s", fname, e)

    logger.info("Progress 디렉토리 정리 완료 (총 %d개 파일 삭제)", deleted_count)
    return deleted_count


def reset_progress() -> None:
    """진행 상태를 초기화합니다 (C 키 누를 때 호출)."""
    config.plot_hash = ""
    config.theme_auto_complete_flag = False
    config.progress_step = 0
    clear_progress_directory()
    logger.info("Progress 상태 초기화")


def get_progress_summary() -> str:
    """현재 진행 상태를 요약 문자열로 반환합니다.

    Returns:
        진행 상태 요약 문자열
    """
    if not config.plot_hash:
        return "진행 상태: 초기화 필요 (C를 눌러 시작)"

    step_labels = {
        0: "초기",
        1: "플롯 완료",
        2: "에피소드 완료",
        3: "스토리 완료",
    }
    step_label = step_labels.get(config.progress_step, "알 수 없음")
    complete_mark = "✓" if config.theme_auto_complete_flag else "✗"

    return (f"Hash: {config.plot_hash} | 단계: {step_label} | "
            f"1번완료: {complete_mark}")


# -------------------------------------------------------------------------
# 전체 자동 실행 시퀀스 (9번 메뉴)
# -------------------------------------------------------------------------

_menu1_logger = logging.getLogger("menu1_flow")


def run_auto_sequence(
    episode_files: list,
    current_file_index: int,
    anima_enb: bool,
    callback=None,
):
    """
    전체 자동 실행 시퀀스 (9번 메뉴 로직).

    흐름:
        1. 초기화 (config 리로드 + 캐릭터 랜덤 + 테마 생성)
        2. 플롯 생성 (job/character/personality 설정 + plot 생성 + theme_agent)
        3. 에피소드 생성 (extended 또는 standard 모드)
        4. 스토리 생성 (full_episode_gen)
        5. ANIMA 생성 (anima_enb 활성화 시)

    Args:
        episode_files: episode_setup.json의 files 목록
        current_file_index: 현재 에피소드 파일 인덱스
        anima_enb: ANIMA 활성화 여부
        callback: GUI 업데이트 콜백 함수
            signature: callback(step: str, status: str, content_text: str)
            step: "init", "plot", "episode", "story", "anima", "done"
            status: 상태 바 텍스트
            content_text: CONTENT 영역에 표시할 텍스트

    Returns:
        dict: {"success": bool, "content_text": str, "current_file_index": int}
    """
    export_path = os.path.join("data", "config_export.yaml")

    def cb(step: str, status: str, content: str):
        if callback:
            callback(step, status, content)

    try:
        # =========================================================
        # 1. 초기화
        # =========================================================
        _menu1_logger.info("=" * 50)
        _menu1_logger.info("[9번 메뉴] 전체 자동 실행 시작")
        cb("init", "초기화 중...", "[전체 자동 실행]\n\n1. 초기화 중...")

        _menu1_logger.info("[9번] 1단계: 초기화 시작")
        saved_jinshugai_id = getattr(config, 'selected_jinshugai_id', None)
        saved_inc_flag = getattr(config, 'inc_flag', 0)
        reset_config_state()
        config.selected_jinshugai_id = saved_jinshugai_id
        config.inc_flag = saved_inc_flag

        # Progress 디렉토리 초기화 + 새 hash 생성
        reset_progress()
        new_hash = generate_plot_hash()
        _menu1_logger.info(f"[9번] 새 hash 생성: {new_hash}")

        character_setup.random_setup_all()

        use_theme_auto = config.json_value.get("theme_auto", "no") == "yes"
        _menu1_logger.info(f"[9번] theme_auto={use_theme_auto}")
        if use_theme_auto:
            # cmd_job/cmd_job2 적용을 위해 job_and_age_init 호출
            character_setup.job_and_age_init()
            import theme_gen_auto
            theme_result = theme_gen_auto.theme_gen_auto(
                "테마 자동 생성 모드",
                num_episodes=config.total_episodes,
                log_fn=logger.info,
            )
            config.theme_jinshugai = theme_result["jinshugai"]
            config.theme_events = theme_result.get("events")
        else:
            story_gen.theme_gen()

        prog_msg = generate_and_parse_progression()
        config.episode_gen_flag = False
        _menu1_logger.info(
            f"[9번] 초기화 완료 - name={config.name}, "
            f"age={getattr(config, 'age', 'N/A')}, "
            f"job={getattr(config, 'job', 'N/A')}"
        )

        # theme_auto 모드이면 1번 완료 처리 (progress 저장 + theme 변수 YAML 저장)
        if use_theme_auto:
            complete_theme_auto()
            _menu1_logger.info(f"[9번] theme_auto 1번 완료 저장됨 (hash={config.plot_hash})")

        export_config_to_file(export_path)
        cb("init", "초기화 완료", "[전체 자동 실행]\n\n1. 초기화 완료")

        # =========================================================
        # 2. 플롯 생성
        # =========================================================
        _menu1_logger.info("[9번] 2단계: 플롯 생성 시작")
        cb("plot", "1번: 플롯 생성 중...", "[전체 자동 실행]\n\n1. 초기화 완료\n\n2. 1번: 플롯 생성 중...")

        character_setup.job_and_age_init()
        _menu1_logger.info(f"[9번] job_and_age_init 완료 - job={config.job}, age={getattr(config, 'age', 'N/A')}")
        character_setup.character_init(config.sex, config.json_value)
        _menu1_logger.info("[9번] character_init 완료")
        character_setup.archetype_setup(config.json_value)
        _menu1_logger.info("[9번] archetype_setup 완료")
        character_setup.personality_init(config.json_value)
        _menu1_logger.info(f"[9번] personality_init 완료 - personality_real={config.personality_real}")
        plot_text = story_gen.generate_plot()
        _menu1_logger.info(f"[9번] generate_plot 완료 (길이={len(plot_text)})")

        # theme_agent
        use_theme_agent = config.json_value.get("theme_agent", "no") == "yes"
        _menu1_logger.info(f"[9번] theme_agent={use_theme_agent}")
        if use_theme_agent and not use_theme_auto:
            import theme_gen as theme_gen_module
            story_info = f"""
스토리: {plot_text.split('\n')[0] if '\n' in plot_text else plot_text[:100]}
테마: {getattr(config, 'plot', '')}
주인공({config.name}, {getattr(config, 'age', '')}세)과 상대방({config.name2}, {getattr(config, 'age2', '')}세)의 이야기입니다.
관계 설정 및 직업({getattr(config, 'job', '')} / {getattr(config, 'job2', '')})을 바탕으로 스토리가 전개됩니다.
"""
            theme_result = theme_gen_module.generate_updated_theme(
                story_info, num_episodes=config.total_episodes
            )
            config.plot = theme_result["theme"]
            config.theme_breeds = theme_result["breeds"]
            config.theme_jinshugai = theme_result["jinshugai"]
            config.theme_events = theme_result["events"]
            config.plot_result = plot_text + f"\n\n[업데이트된 테마]\n{theme_result['theme']}"
            _menu1_logger.info("[9번] theme_agent 업데이트 완료")

        export_config_to_file(export_path)
        cb("plot", "1번: 플롯 생성 완료", "[전체 자동 실행]\n\n1. 초기화 완료\n\n2. 1번: 플롯 생성 완료")

        # =========================================================
        # 3. 에피소드 생성
        # =========================================================
        _menu1_logger.info("[9번] 3단계: 에피소드 생성 시작")
        cb("episode", "4번: 에피소드 생성 중...", "[전체 자동 실행]\n\n1. 초기화 완료\n\n2. 1번: 플롯 생성 완료\n\n3. 4번: 에피소드 생성 중...")

        prog_msg = generate_and_parse_progression()
        use_extended = config.json_value.get("extended", "no") == "yes"
        _menu1_logger.info(f"[9번] extended={use_extended}")

        if use_extended:
            jinshugai_list = getattr(config, "theme_jinshugai", None)
            if jinshugai_list and len(jinshugai_list) > 0:
                template_id = jinshugai_list[0].get("id", rand.randint(1, 10))
            else:
                template_id = rand.randint(1, 10)
            theme_msg = getattr(config, "plot", "")
            total_eps = config.total_episodes

            def plot_callback(status_msg: str):
                cb("episode", status_msg,
                   f"[전체 자동 실행]\n\n1. 초기화 완료\n\n2. 1번: 플롯 생성 완료\n\n3. 4번: 에피소드 생성 중...\n\n{status_msg}")

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                plot_result = plot_gen.plot_gen_extended(
                    template_id=template_id,
                    total_episodes=total_eps,
                    theme_msg=theme_msg,
                    breeds_data=getattr(config, "theme_breeds", None),
                    jinshugai_templates=getattr(config, "theme_jinshugai", None),
                    progression_events=getattr(config, "theme_events", None),
                    callback=plot_callback,
                )
            finally:
                sys.stdout = old_stdout

            ep_header_pattern = re.compile(
                r'(?:##\s*)?(?:\*\*)?EPISODE\s*(\d+)(?:\*\*)?\s*[#:]?\s*(.*)'
            )
            episodes_parsed_dict = {}
            current_ep_num = None
            current_ep_lines = []
            for line in plot_result.split("\n"):
                stripped = line.strip()
                match = ep_header_pattern.match(stripped)
                if match:
                    if current_ep_num is not None and current_ep_lines:
                        episodes_parsed_dict[current_ep_num] = "\n".join(current_ep_lines).strip()
                    current_ep_num = int(match.group(1))
                    rest = match.group(2).strip().rstrip("*").rstrip("#").strip()
                    current_ep_lines = [rest] if rest else []
                elif current_ep_num is not None and stripped:
                    current_ep_lines.append(stripped)
            if current_ep_num is not None and current_ep_lines:
                episodes_parsed_dict[current_ep_num] = "\n".join(current_ep_lines).strip()

            episodes_parsed = []
            for i in range(1, total_eps + 1):
                episodes_parsed.append(episodes_parsed_dict.get(i, ""))

            for i in range(len(config.episode_content)):
                if i < len(episodes_parsed):
                    config.episode_content[i] = episodes_parsed[i]
                else:
                    config.episode_content[i] = ""

            result_lines = ["=== 생성된 에피소드 리스트 (Extended) ==="]
            result_lines.append(f"템플릿: {plot_gen.TEMPLATES[template_id]['name']}")
            result_lines.append(f"총 {len(episodes_parsed)}개 에피소드 생성")
            result_lines.append("")
            for idx, ep in enumerate(episodes_parsed):
                result_lines.append(f"Episode {idx + 1}: {ep}")
            result_lines.append("")
            config.result_text = "\n".join(result_lines)
            config.episode_gen_flag = True
            _menu1_logger.info(f"[9번] extended 에피소드 생성 완료 - {len(episodes_parsed)}개")
        else:
            # 표준 모드
            _menu1_logger.info(
                f"[9번] 표준 모드 episode_gen 호출 시작 - episode_files={len(episode_files)}개"
            )
            ep_gen = story_gen.episode_gen
            if episode_files:
                idx = (current_file_index + 1) % len(episode_files)
                current_file_index = idx
                current_file = episode_files[current_file_index]
                filename = current_file.get("filename", "")
                description = current_file.get("description", "")
                if filename:
                    ep_gen(filename_override=filename)
                else:
                    ep_gen()
                _menu1_logger.info(f"[9번] episode_gen(filename={filename}) 완료")
            else:
                ep_gen()
                _menu1_logger.info("[9번] episode_gen() 완료")
            _menu1_logger.info(
                f"[9번] episode_gen_flag={config.episode_gen_flag}, "
                f"result_text 길이={len(config.result_text) if config.result_text else 0}"
            )
            for i in range(len(config.episode_content)):
                content_preview = config.episode_content[i][:60] if config.episode_content[i] else "EMPTY"
                _menu1_logger.info(f"[9번] episode_content[{i}]: {content_preview}...")

        # 에피소드 내용과 캐릭터 시트를 progress 디렉토리에 저장
        plot_hash = getattr(config, 'plot_hash', '')
        if plot_hash:
            saved_ep_files = save_episodes_and_sheets_to_progress(plot_hash)
            _menu1_logger.info(f"[9번] progress 저장 완료: {len(saved_ep_files)}개 파일")

        export_config_to_file(export_path)
        cb("episode", "4번: 에피소드 생성 완료", "[전체 자동 실행]\n\n1. 초기화 완료\n\n2. 1번: 플롯 생성 완료\n\n3. 4번: 에피소드 생성 완료")

        # =========================================================
        # 4. 스토리 생성
        # =========================================================
        _menu1_logger.info("[9번] 4단계: 스토리 생성 시작")
        cb("story", "6번: 스토리 생성 중...", "[전체 자동 실행]\n\n1. 초기화 완료\n\n2. 1번: 플롯 생성 완료\n\n3. 4번: 에피소드 생성 완료\n\n4. 6번: 스토리 생성 중...")

        def stream_callback(text, info_lines=None):
            if info_lines:
                current_ep = info_lines.get("current_episode")
                updated_count = info_lines.get("updated_count", 0)
                status = info_lines.get("status", "")
                progress_text = f"[전체 자동 실행]\n\n1. 초기화 완료\n\n2. 1번: 플롯 생성 완료\n\n3. 4번: 에피소드 생성 완료\n\n4. 6번: 스토리 생성 중...\n\n{status}"
                if text:
                    progress_text += f"\n\n{text[:500]}..."
                cb("story", f"생성중... {updated_count}/{config.total_episodes}", progress_text)

        final_result = full_episode_gen.full_episode_gen(ep_num=0, callback=stream_callback)
        _menu1_logger.info(f"[9번] full_episode_gen 완료 - episode_full_track={list(config.episode_full_track)}")
        cb("story", "6번: 스토리 생성 완료", "[전체 자동 실행]\n\n1. 초기화 완료\n\n2. 1번: 플롯 생성 완료\n\n3. 4번: 에피소드 생성 완료\n\n4. 6번: 스토리 생성 완료")

        # =========================================================
        # 5. ANIMA 생성 (anima_enb 활성화 시)
        # =========================================================
        if anima_enb:
            _menu1_logger.info("[9번] 5단계: ANIMA 생성 시작")
            cb("anima", "10번: ANIMA 생성 중...", "[전체 자동 실행]\n\n1. 초기화 완료\n\n2. 1번: 플롯 생성 완료\n\n3. 4번: 에피소드 생성 완료\n\n4. 6번: 스토리 생성 완료\n\n5. 10번: ANIMA 생성 중...")

            client = openAPI_control.get_openai_client()
            anima_gen.anima_setup(config.json_value)

            for ep_idx in range(config.total_episodes):
                ep_num = ep_idx + 1
                init_result = anima_gen.init_anima_tags(ep_idx, client, config.json_value)
                if isinstance(init_result, dict) and init_result["status"] != "missing":
                    anima_gen.anima_gen_standing(
                        episode=ep_idx,
                        messages_history_rp=config.messages_history,
                        json_value=config.json_value,
                        client_rp=client,
                        sex=config.sex,
                        name=config.name,
                        name2=config.name2,
                    )
                    # 기-승-전-결 4회 호출
                    for step_num in range(1, 5):
                        config.episode_step = f"{step_num}"
                        _menu1_logger.info(f"[9번] ANIMA simple EP{ep_num} step={config.episode_step}")
                        anima_gen.anima_gen_simple(
                            episode=ep_idx,
                            messages_history_rp=config.messages_history,
                            json_value=config.json_value,
                            client_rp=client,
                            sex=config.sex,
                            name=config.name,
                            name2=config.name2,
                        )
                cb("anima", f"ANIMA EP{ep_num} 완료",
                   f"[전체 자동 실행]\n\n1. 초기화 완료\n\n2. 1번: 플롯 생성 완료\n\n3. 4번: 에피소드 생성 완료\n\n4. 6번: 스토리 생성 완료\n\n5. 10번: ANIMA 생성 중... (EP{ep_num})")

        # =========================================================
        # 완료
        # =========================================================
        _menu1_logger.info("[9번] 전체 자동 실행 완료!")
        content_text = f"[전체 자동 실행 완료]\n\n1. 초기화 완료\n\n2. 1번: 플롯 생성 완료\n\n3. 4번: 에피소드 생성 완료\n\n4. 6번: 스토리 생성 완료\n\n총 {config.total_episodes}개의 에피소드가 result/ 디렉토리에 저장되었습니다."
        if anima_enb:
            content_text += "\n\n5. ANIMA 이미지 생성 완료"

        # 아카이브: result/의 markdown과 ComfyUI output의 png를 done/book{N}/로 이동
        _menu1_logger.info("[9번] 아카이브 시작...")
        archive_result = archive_to_done()
        _menu1_logger.info(archive_result)
        content_text += f"\n\n6. 아카이브 완료: {archive_result}"
        cb("done", "전체 자동 실행 완료", content_text)

        return {
            "success": True,
            "content_text": content_text,
            "current_file_index": current_file_index,
        }

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _menu1_logger.info(f"[9번] 오류 발생: {e}\n\n{tb}")
        cb("done", f"오류: {e}", f"전체 자동 실행 중 오류 발생:\n{e}\n\n{tb}")
        return {
            "success": False,
            "content_text": f"전체 자동 실행 중 오류 발생:\n{e}\n\n{tb}",
            "current_file_index": current_file_index,
        }
