import random as rand
import re
import json
import config
import character_setup
from common_def import name_chg, get_particles
import os
import time
from openai import APITimeoutError, APIStatusError
from openAPI_control import call_openai_api

def random_prompt(wildcard, mynumber=-1):
    try:
        with open(wildcard, 'r', encoding='utf-8') as r1:
            prompt_org = r1.readlines()
        if mynumber != -1:
            prompt_sel = prompt_org[mynumber]
        else:
            temp = rand.randint(0, len(prompt_org) - 1)
            prompt_sel = prompt_org[temp]
        return prompt_sel.strip()
    except Exception as e:
        print(f"Error reading prompt file {wildcard}: {e}")
        return ""


def theme_gen():
    """
    data/theme.txt에서 테마를 랜덤하게 선택하여 
    플롯, 나이 차이, 직업 설정을 수행합니다.
    """
    try:
        if config.json_value["extended"] == "yes":
            theme_file = theme_file_sel()
        else:            
            theme_file = "./data/theme.txt"
        with open(theme_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if not lines:
                return "테마 파일을 읽을 수 없습니다."
            
            line = rand.choice(lines).strip()
            if not line:
                return "빈 테마 라인이 선택되었습니다."
            
            parts = line.split("#")
            
            # 1) 첫번째 항목: 플롯
            if len(parts) > 0:
                config.plot = parts[0].strip()

            # 임시변수에 직업과 나이 차이 정보 저장 (job_and_age_init에서 처리)
            if len(parts) > 1:
                job1 = parts[1].strip()
                config.theme_job1 = job1 if job1 != "NONE" else ""

            if len(parts) > 2:
                job2 = parts[2].strip()
                config.theme_job2 = job2 if job2 != "NONE" else ""

            # 나이 차이 (최대, 최소) 저장
            if len(parts) > 3:
                try:
                    config.theme_age_diff_max = int(parts[3].strip())
                    config.theme_age_diff_min = int(parts[4].strip())
                except (ValueError, IndexError):
                    config.theme_age_diff_max = 0
                    config.theme_age_diff_min = 0
            else:
                config.theme_age_diff_max = 0
                config.theme_age_diff_min = 0

            # 6개 이상 parts가 있으면 temp_theme에 저장
            if len(parts) >= 6:
                config.temp_theme = [p.strip() for p in parts[5:]]
            else:
                config.temp_theme = []

            config.nationality = ""
            config.nationality2 = ""
            config.name = ""
            config.name2 = ""
            character_setup.name_define()                
                    
            return f"테마 적용 완료: {config.plot}"
    except Exception as e:
        return f"theme_gen 오류 발생: {e}"

def generate_plot():
    """플롯을 생성하여 반환합니다."""
    # 실제 구현에서는 LLM API 등을 호출하겠지만, 여기서는 설정된 플롯 기반의 텍스트를 반환합니다.
    if not getattr(config, 'plot', ""):
        return "플롯이 설정되지 않았습니다. 먼저 주인공 설정을 확인하세요."
    
    # inc_flag 체크: 가족애 모드
    story_type = "연애 라노벨(성인/성인)"
    if config.json_value.get("extended", "no") == "yes" and getattr(config, 'inc_flag', 0) == 1:
        story_type = "연애 라노벨(가족애)"
    
    config.plot_result = f"--- 생성된 플롯 ---\n(엔터를 치면 랜덤하게 다시 생성됩니다)\n\n스토리: {story_type}\n테마: {config.plot}\n"
    config.plot_result += f"주인공({config.name}, {config.age}세)과 상대방({config.name2}, {config.age2}세)의 이야기입니다.\n"
    config.plot_result += f"관계 설정 및 직업({config.job} / {config.job2})을 바탕으로 스토리가 전개됩니다."
    
    return config.plot_result

def episode_gen(filename_override: str = None):
    """에피소드 설정을 기반으로 에피소드 리스트를 생성합니다.
    
    Args:
        filename_override: 특정 에피소드 파일명을 지정합니다. None이면 직업에 따라 자동 선택.
    
    Returns:
        생성된 에피소드 리스트 텍스트.
    """
    try:
        print(f"[episode_gen] 시작 (filename_override={filename_override})")
        
        # 1. setup.json 읽기
        with open("./data/episode_setup.json", 'r', encoding='utf-8') as f:
            setup_data = json.load(f)
        
        config.total_episodes = setup_data.get("total_episodes", 12)
        print(f"[episode_gen] episode_setup.json 읽음 - total_episodes={config.total_episodes}")
        
        # 2. 파일 선택
        if filename_override:
            filename = filename_override
            print(f"[episode_gen] 파일 선택: filename_override={filename}")
        else:
            # 직업에 따른 파일 선택
            job_combined = (getattr(config, 'job', "") + getattr(config, 'job2', ""))
            print(f"[episode_gen] 파일 자동 선택 - job={getattr(config, 'job', '')}, job2={getattr(config, 'job2', '')}, combined={job_combined}")
            if "선생" in job_combined and "학생" in job_combined:
                filename = "episode_s2t.txt"
            elif "학생" in job_combined and "학생" in job_combined:
                filename = "episode_s2s.txt"
            else:
                filename = "episode_a2a.txt"
            print(f"[episode_gen] 선택된 파일: {filename}")
        
        # 3. 에피소드 파일 읽기 및 밸런스 있는 추출
        episode_file_path = f"./data/{filename}"
        print(f"[episode_gen] 에피소드 파일 읽기: {episode_file_path}")
        with open(episode_file_path, 'r', encoding='utf-8') as f:
            all_episodes = [line.strip() for line in f if line.strip()]
        
        if not all_episodes:
            print(f"[episode_gen] 에피소드 파일이 비어있습니다!")
            return "에피소드 파일이 비어있습니다."
        
        print(f"[episode_gen] 에피소드 파일에서 {len(all_episodes)}개 항목 읽음")
        
        # 필요한 랜덤 에피소드 개수 계산
        num_random = config.total_episodes - 4
        print(f"[episode_gen] 필요한 랜덤 에피소드 수: num_random={num_random} (total={config.total_episodes} - 4)")
        
        if len(all_episodes) < num_random:
            # 파일 내용이 부족하면 중복 허용하여 추출
            print(f"[episode_gen] 파일 내용 부족 ({len(all_episodes)} < {num_random}) - 중복 허용 추출")
            sampled_episodes = [rand.choice(all_episodes) for _ in range(num_random)]
        else:
            # 파일을 균등한 구간으로 나누어 밸런스 있게 추출
            num_sections = min(10, len(all_episodes))
            section_size = len(all_episodes) // num_sections
            sampled_episodes = []
            print(f"[episode_gen] 밸런스 추출 - sections={num_sections}, section_size={section_size}")
            
            for section_idx in range(num_sections):
                start = section_idx * section_size
                end = start + section_size if section_idx < num_sections - 1 else len(all_episodes)
                section = all_episodes[start:end]
                
                count = round(num_random / num_sections)
                if len(section) < count:
                    sampled_episodes.extend(section)
                    print(f"  [episode_gen] section[{section_idx}]: {len(section)}개 전체 추출 (부족)")
                else:
                    sampled_episodes.extend(rand.sample(section, count))
                    print(f"  [episode_gen] section[{section_idx}]: {count}개 추출 (from {len(section)})")
            
            # 추출된 개수가 필요 개수와 다르면 조정
            if len(sampled_episodes) > num_random:
                sampled_episodes = sampled_episodes[:num_random]
                print(f"[episode_gen] 추출 초과 조정: {len(sampled_episodes)+num_random} -> {num_random}")
            elif len(sampled_episodes) < num_random:
                remaining = [ep for ep in all_episodes if ep not in sampled_episodes]
                if remaining:
                    add_count = min(num_random - len(sampled_episodes), len(remaining))
                    sampled_episodes.extend(rand.sample(remaining, add_count))
                    print(f"[episode_gen] 추출 부족 조정: +{add_count}개 추가")
        
        print(f"[episode_gen] 최종 sampled_episodes: {len(sampled_episodes)}개")
        
        # 4. 기-승-전-결 구조 배치
        plot_val = getattr(config, 'plot', "설정된 플롯 없음")
        print(f"[episode_gen] 기승전결 배치 - plot_val={plot_val[:50]}...")
        episodes_array = [None] * config.total_episodes
        episodes_array[0] = f"[기] {plot_val} - 첫 만남과 설레는 기류"
        episodes_array[config.total_episodes - 1] = f"[결] {plot_val} - 깊어진 사랑과 서로의 확인"
        
        pos_seung = config.total_episodes // 3
        pos_jeon = (config.total_episodes * 2) // 3
        if pos_seung == 0: pos_seung = 1
        if pos_jeon >= config.total_episodes: pos_jeon = config.total_episodes - 2
        if pos_seung == pos_jeon: pos_jeon += 1
        
        print(f"[episode_gen] 기승전결 위치: 기=0, 승={pos_seung}, 전={pos_jeon}, 결={config.total_episodes-1}")
        
        episodes_array[pos_seung] = f"[승] {plot_val} - 서서히 가까워지는 마음"
        episodes_array[pos_jeon] = f"[전] {plot_val} - 고백과 관계의 전환점"
        
        # 나머지 빈칸을 랜덤 에피소드로 채우기
        random_idx = 0
        for i in range(config.total_episodes):
            if episodes_array[i] is None:
                episodes_array[i] = sampled_episodes[random_idx]
                random_idx += 1
        
        print(f"[episode_gen] episodes_array 구성 완료: {len(episodes_array)}개")
        for i, ep in enumerate(episodes_array):
            print(f"  [episode_gen] EP{i+1}: {ep[:60]}...")
        
        # 5. 결과 포맷팅
        config.result_text = "--- 생성된 에피소드 리스트 ---\n(파일: {filename})\n".format(filename=filename)
        for idx, ep in enumerate(episodes_array):
            config.result_text += f"Episode {idx + 1}: {ep}\n"
            if idx < len(config.episode_content):
                config.episode_content[idx] = ep
        config.episode_gen_flag = True
        
        print(f"[episode_gen] config.episode_content 저장 완료: {len(config.episode_content)}개")
        print(f"[episode_gen] config.episode_gen_flag={config.episode_gen_flag}")
        for i, ep in enumerate(config.episode_content):
            print(f"  [episode_gen] config.episode_content[{i}]: {ep[:60] if ep else 'EMPTY'}...")
        
        print(f"[episode_gen] 완료")
        return config.result_text

    except Exception as e:
        print(f"[episode_gen] 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return f"에피소드 생성 중 오류 발생: {e}"

def generate_single_episode(ep_num: int, callback=None, structure_type: str = "") -> str:
    """단일 에피소드의 전체 소설 내용을 생성합니다.
    
    Args:
        ep_num: 생성할 에피소드 번호 (1-based)
        callback: 스트리밍 콜백 함수
        structure_type: 구조 타입 ("기", "승", "전", "결" 등). 빈 문자열이면 일반 에피소드.
    
    Returns:
        생성된 에피소드 텍스트.
    """
    try:
        protagonist_sheet, _ = character_setup.character_sheet(0)
        partner_sheet = character_setup.partner_sheet()
        episode_list = config.result_text if config.result_text else ""

        # 현재 에피소드의 계획된 내용 추출
        ep_line = f"Episode {ep_num}:"
        ep_planned = ""
        for line in episode_list.split("\n"):
            if line.startswith(ep_line):
                ep_planned = line[len(ep_line):].strip()
                break

        # 구조 타입에 따른 프롬프트 추가
        structure_prompt = ""
        if structure_type == "기":
            structure_prompt = "\nThis is the INTRODUCTION (기) - Focus on first meeting and initial atmosphere between characters."
        elif structure_type == "승":
            structure_prompt = "\nThis is the DEVELOPMENT (승) - Focus on characters getting closer and deepening their bond."
        elif structure_type == "전":
            structure_prompt = "\nThis is the TWIST/CLIMAX (전) - Focus on emotional explosion and turning point in their relationship."
        elif structure_type == "결":
            structure_prompt = "\nThis is the CONCLUSION (결) - Focus on deepened affection and mutual confirmation between characters."

        user_prompt = (
            f"Please write a full novel chapter for Episode {ep_num} based on the following information:\n\n"
            f"### Protagonist Sheet:\n{protagonist_sheet}\n\n"
            f"### Partner Sheet:\n{partner_sheet}\n\n"
            f"### Episode {ep_num} Plan:\n{ep_planned}\n\n"
            f"{structure_prompt}\n\n"
            f"Write a detailed, engaging chapter in Korean light novel rom-com style. "
            f"Include sweet dialogue, funny moments, cute descriptions, and emotional depth. "
            f"Keep the tone lighthearted and romantic, suitable for a young adult romance comedy. "
            f"Make it at least 2000 words long.\n\n"
            f"Start with: ## EPISODE {ep_num} ##"
        )

        info_lines = {
            "total_episodes": config.total_episodes,
            "updated_count": ep_num,
            "current_episode": ep_num,
            "status": f"Generating Episode {ep_num}/{config.total_episodes}..."
        }

        chapter = call_openai_api(user_prompt, callback=callback, info_lines=info_lines)

        # 에피소드 헤더 제거하고 내용만 추출
        chapter_content = re.sub(r'##\s*EPISODE\s*\d+\s*##', '', chapter).strip()
        config.episode_full_content[ep_num - 1] = chapter_content
        config.episode_full_track[ep_num - 1] = True

        return chapter

    except Exception as e:
        return f"에피소드 {ep_num} 생성 중 오류 발생: {e}"


def _update_character_sheets_from_episode(episode_text: str, ep_num: int) -> None:
    """에피소드 생성 후 캐릭터 시트 관련 config 변수를 업데이트합니다.

    에피소드 내용에서 캐릭터 상태 변화를 감지하고 config 변수를 갱신합니다.
    다음 에피소드 생성 시 최신 캐릭터 시트가 사용되도록 합니다.

    Args:
        episode_text: 생성된 에피소드 텍스트
        ep_num: 에피소드 번호 (1-based)
    """
    if not episode_text:
        return

    # love_value 증가 (에피소드 진행마다 관계도 상승)
    current_love = getattr(config, 'love_value', 0)
    config.love_value = min(current_love + 5, 100)

    # happiness 증가
    current_happiness = getattr(config, 'happiness', 0)
    config.happiness = min(current_happiness + 3, 100)




def episode_summary_gen(callback=None):
    """캐릭터 시트와 에피소드 리스트를 기반으로 OpenAI를 통해 상세 줄거리를 생성합니다.
    각 에피소드를 개별적으로 루프 돌며 생성하며, progression_array를 프롬프트에 포함합니다.
    각 에피소드는 기-승-전-결 구조로 출력됩니다.
    API 요청/응답은 debug_api_pre.log에 기록됩니다.
    """
    log_file = None
    try:
        # extended 모드 체크
        use_extended = config.json_value.get("extended", "no") == "yes"
        ep_gen = episode_gen_extended if use_extended else episode_gen
        episode_list = ep_gen()

        # progression_array 읽기
        progression_array = getattr(config, 'progression_array', [])

        # 초기화: episode_content와 episode_track 리셋
        for i in range(len(config.episode_content)):
            config.episode_content[i] = ""
            config.episode_track[i] = False

        # 로그 파일 열기
        log_file = open("debug_api_pre.log", "w", encoding="utf-8")

        def log(msg: str):
            log_file.write(msg + "\n")
            log_file.flush()

        log("=" * 60)
        log(f"[episode_summary_gen] 시작 시간: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        log(f"총 에피소드: {config.total_episodes}")
        log(f"progression_array 길이: {len(progression_array)}")
        log("=" * 60)

        # API 호출용 클라이언트 생성
        api_key = os.environ.get("OPENAI_API_KEY", "gemma-4-31b")
        client = OpenAI(
            base_url="http://" + config.json_value.get("ip_main", "192.168.1.162") + ":" + config.json_value["port_main"] + "/v1",
            api_key=api_key
        )

        # 각 에피소드 개별 생성 루프
        for ep_idx in range(config.total_episodes):
            ep_num = ep_idx + 1
            log(f"\n--- Episode {ep_num} 생성 시작 ---")

            # 1. 입력 데이터 수집 (에피소드마다 캐릭터 시트 재읽기)
            # plot_gen_extended에서 생성된 시트 배열이 있으면 사용, 없으면 직접 생성
            proto_sheets = getattr(config, 'episode_protagonist_sheets', None)
            part_sheets = getattr(config, 'episode_partner_sheets', None)
            if proto_sheets and ep_idx < len(proto_sheets) and proto_sheets[ep_idx]:
                protagonist_sheet = proto_sheets[ep_idx]
                partner_sheet = part_sheets[ep_idx] if part_sheets and ep_idx < len(part_sheets) else character_setup.partner_sheet()
            else:
                # current_episode_index 설정: character_sheet_extended()가 올바른 스냅샷을 참조하도록
                config.current_episode_index = ep_idx
                protagonist_sheet, _ = character_setup.character_sheet(getattr(config, 'love_value', 0))
                partner_sheet = character_setup.partner_sheet()
            log(f"[캐릭터 시트 업데이트] Episode {ep_num} - love_value={getattr(config, 'love_value', 0)}")

            # 캐릭터 시트를 debug_character_sheet.log에 기록
            with open("debug_character_sheet.log", "a", encoding="utf-8") as cs_log:
                cs_log.write(f"{'=' * 60}\n")
                cs_log.write(f"[Episode {ep_num}] 캐릭터 시트 (love_value={getattr(config, 'love_value', 0)})\n")
                cs_log.write(f"{'=' * 60}\n")
                cs_log.write(f"\n### 주인공 시트 ###\n\n{protagonist_sheet}\n")
                cs_log.write(f"\n### 상대방 시트 ###\n\n{partner_sheet}\n")
                cs_log.write(f"\n{'-' * 60}\n\n")

            # 현재 에피소드의 progression 데이터
            ep_progression = progression_array[ep_idx] if ep_idx < len(progression_array) else ""

            # 현재 에피소드의 줄거리 (episode_list에서 추출)
            ep_lines = episode_list.strip().split("\n")
            ep_story = ""
            for line in ep_lines:
                if f"Episode {ep_num}:" in line or f"Episode {ep_num} [" in line:
                    ep_story = line.split(":", 1)[1].strip() if ":" in line else line
                    break

            # progression_array에서 phase 추출
            phase_match = re.search(r'<([^>]+)>', ep_progression)
            phase_name = phase_match.group(1).strip() if phase_match else "미정"

            # 첫 에피소드는 평범하고 일상적인 전개
            if ep_num == 1:
                seung_desc = "캐릭터들의 평범하고 일상적인 모습"
                jeon_desc = "자연스러운 일상 속에서의 미묘한 변화"
            else:
                seung_desc = "갈등이나 변화의 시작"
                jeon_desc = "감정의 폭발이나 관계의 전환점"

            # user_prompt 구성
            user_prompt = (
                f"Please generate detailed story content for Episode {ep_num} only.\n\n"
                f"### Protagonist Sheet:\n{protagonist_sheet}\n\n"
                f"### Partner Sheet:\n{partner_sheet}\n\n"
                f"### All Episodes Overview:\n{episode_list}\n\n"
                f"### Episode {ep_num} Summary:\n{ep_story}\n\n"
                f"### {config.name}'s Current State (Animal Metaphor):\n{ep_progression}\n\n"
                f"Please write this episode with the following structure:\n"
                f"[기] 도입 - 상황 설정과 캐릭터의 현재 상태\n"
                f"[승] 전개 - {seung_desc}\n"
                f"[전] 전환 - {jeon_desc}\n"
                f"[결] 결말 - 에피소드의 마무리와 다음 에피소드로의 연결\n\n"
                f"Write in a Korean light novel rom-com style: sweet, funny, and romantic. "
                f"Include cute dialogue, funny misunderstandings, and heartwarming moments. "
                f"Keep the tone lighthearted and suitable for young adult readers.\n"
                f"Make sure the {phase_name} phase is clearly reflected in the story.\n"
                f"Provide the result in Korean.\n"
            )

            log(f"[USER PROMPT] Episode {ep_num}:")
            log(user_prompt)

            # messages_history 설정 (시스템 프롬프트 + 현재 요청)
            if not config.messages_history or config.messages_history[0].get("role") != "system":
                config.messages_history.insert(0, {"role": "system", "content": config.system_prompt})

            # 이전 대화는 유지하고 현재 에피소드 요청 추가
            ep_messages = config.messages_history.copy()
            ep_messages.append({"role": "user", "content": user_prompt})

            temp = 0.9 + rand.randint(0, 1) / 10.0
            top_p = 0.95
            repeat_penalty = 1.15
            top_k = 64
            my_extra_params = {
                "repeat_penalty": repeat_penalty,
                "top_k": top_k
            }

            # API 호출
            full_response = ""
            max_try = 0
            timeout_check = 0

            while timeout_check == 0:
                try:
                    response = client.chat.completions.create(
                        model="gemma-4-31B-it",
                        stream_options={"include": True},
                        messages=ep_messages,
                        temperature=temp,
                        top_p=top_p,
                        stream=config.stream_enb,
                        timeout=300.0,
                        extra_body=my_extra_params)
                    timeout_check = 1
                except APITimeoutError:
                    log(f"[TIMEOUT] Episode {ep_num} - 재시도 {max_try + 1}")
                    timeout_check = 0
                    max_try += 1
                    time.sleep(10)
                    if max_try > 3:
                        log(f"[ERROR] Episode {ep_num} - 서버 응답 실패")
                        full_response = f"(에피소드 {ep_num} 생성 실패)"
                        break

            if config.stream_enb:
                for chunk in response:
                    if chunk.usage:
                        log(f"[TOKEN] Episode {ep_num} - Prompt: {chunk.usage.prompt_tokens}, "
                            f"Completion: {chunk.usage.completion_tokens}, "
                            f"Total: {chunk.usage.total_tokens}")
                    if not chunk.choices:
                        continue
                    content = chunk.choices[0].delta.content
                    if content:
                        full_response += content

            # 응답 로그
            log(f"[ASSISTANT RESPONSE] Episode {ep_num}:")
            log(full_response)

            # 응답을 messages_history에 추가
            ep_messages.append({"role": "assistant", "content": full_response})
            config.messages_history = ep_messages

            # 에피소드 내용 저장
            config.episode_content[ep_idx] = full_response.strip()
            config.episode_track[ep_idx] = True

            # callback 호출
            if callback:
                info_lines = {
                    "total_episodes": config.total_episodes,
                    "updated_count": ep_num,
                    "current_episode": ep_num,
                    "status": f"Episode {ep_num} 완료 ({phase_name})"
                }
                callback(full_response, info_lines)

            # 2. 에피소드 생성 후 캐릭터 시트 업데이트
            _update_character_sheets_from_episode(full_response, ep_num)
            log(f"--- Episode {ep_num} 완료 ---")

        # 최종 결과물 조합
        result_parts = ["--- AI 생성 에피소드 상세 요약 ---\n"]
        for i in range(config.total_episodes):
            ep_num = i + 1
            if config.episode_content[i]:
                result_parts.append(f"## EPISODE {ep_num} ##\n{config.episode_content[i]}\n")
            else:
                result_parts.append(f"## EPISODE {ep_num} ##\n(에피소드 {ep_num}을(를) 생성하지 못했습니다)\n")

        final_result = "\n".join(result_parts)
        log(f"\n[완료] 전체 {config.total_episodes}개 에피소드 생성 완료")
        return final_result

    except Exception as e:
        return f"에피소드 보완 생성 중 오류 발생: {e}\n(API 키 설정 등을 확인하세요)"
    finally:
        if log_file:
            log_file.close()


# =============================================================================
# Extended 모드 전용 함수 (story_gen_extended.py에서 병합)
# =============================================================================

# Phase 이름 → phase index (0-based) 매핑
PHASE_MAP = {
    "혐오": 0,
    "경계": 1,
    "보통": 2,
    "친밀": 3,
    "애정": 4,
    "집착": 5,
    "결말": 6,
    "중독": 5,
}


def _replace_names(line: str) -> str:
    """NAME1 → [NAME], NAME2 → [NAME2] 변환 후 name_chg 호출."""
    line = line.replace("NAME2", "[NAME2]")
    line = line.replace("NAME1", "[NAME]")
    return name_chg(line, config.name, config.name2)


def _parse_main_episode_file(filepath: str) -> list:
    """메인 스토리 에피소드 파일을 읽어서 리스트로 반환."""
    episodes = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {filepath}")
        return episodes
    
    for line in lines:
        line = line.strip()
        if line:
            clean = re.sub(r'^\d+\.\s*', '', line)
            if clean:
                clean = _replace_names(clean)
                episodes.append(clean)
    
    return episodes


def _parse_episode_file(filepath: str) -> list:
    """에피소드 파일을 phase별로 분리하여 7개의 리스트로 반환."""
    phases = [[] for _ in range(7)]
    current_phase = 0
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {filepath}")
        return phases
    
    for line in lines:
        line = line.strip()
        phase_match = re.match(r'###\s*\[Phase\s+(\d+)\]', line)
        if phase_match:
            current_phase = int(phase_match.group(1)) - 1
            if current_phase < 0: current_phase = 0
            if current_phase > 6: current_phase = 6
        elif line and not line.startswith('###'):
            clean = re.sub(r'^\d+\.\s*', '', line)
            if clean:
                clean = _replace_names(clean)
                phases[current_phase].append(clean)
    
    return phases


def _extract_phase_from_progression(line: str) -> int:
    """progression_array 라인에서 <상태>를 추출하여 phase index 반환."""
    match = re.search(r'<([^>]+)>', line)
    if match:
        phase_name = match.group(1).strip()
        return PHASE_MAP.get(phase_name, 0)
    return 0


def _get_phase_transition_content(prev_phase: int, curr_phase: int, ep_index: int = 0) -> str:
    """Phase 전환 시 추가할 에피소드 내용을 반환하고 config 카운터 업데이트."""
    name = config.name
    name2 = config.name2
    
    p1 = get_particles(name)
    p2 = get_particles(name2)
    
    # 기존 카운터가 있으면 에피소드 증가에 따라 랜덤 증가
    #if ep_index > 0:
    #    if config.masturbation_count > 0:
    #        config.masturbation_count += rand.randint(0, 1)
    #    if config.patting_count > 0:
    #        config.patting_count += rand.randint(0, 1)
    #    if config.normal_sex_count > 0:
    #        config.normal_sex_count += rand.randint(0, 2)
    #    if config.reverse_sex_count > 0:
    #        config.reverse_sex_count += rand.randint(0, 1)
    #    if config.cowboy_sex_count > 0:
    #        config.cowboy_sex_count += rand.randint(0, 1)
    #    if config.anal_sex_count > 0:
    #        config.anal_sex_count += rand.randint(0, 1)
    #    if config.pose_sex_count > 0:
    #        config.pose_sex_count += rand.randint(0, 1)
    
    # 1) 보통(2) -> 친밀(3): 첫 눈맞춤과 설렘
    if prev_phase == 2 and curr_phase == 3:
        contents = [
            f"{name}이 우연히 {name2}{p2['object']}와 눈이 마주치자, 가슴이 쿵쾅거리며 얼굴이 새빨개지기",
            f"{name2}가 {name}{p1['topic']}의 손을 자연스럽게 잡자, 전율이走り며 숨이 막히기",
            f"{name}이 {name2}{p2['subject']}의 미소를 보자, 마음이 녹아내리며 설레는 감정에 잠기기",
        ]
        result = rand.choice(contents)
    # 2) 친밀(3) -> 애정(4): 첫 키스
    elif prev_phase == 3 and curr_phase == 4:
        contents = [
            f"{name2}가 {name}{p1['topic']}의 이마에 부드럽게 입을 맞추며 '너무 예쁘다'라고 속삭이고, 숨죽여 듣기",
            f"{name}이 {name2}{p2['subject']}의 손을 잡고 자연스럽게 다가가며 첫 키스를 나누기",
            f"{name2}가 {name}{p1['topic']}의 머리를 쓰다듬으며 '귀엽다'고 농담하자, 얼굴이 새빨개져 숨지기",
        ]
        result = rand.choice(contents)
    # 3) 애정(4): 50% 확률로 첫 포옹
    elif curr_phase == 4:
        if rand.random() < 0.5:
            contents = [
                f"{name2}가 {name}{p1['object']} 품에 안으며, 따뜻한 포옹으로 서로의 마음을 확인하기",
                f"{name}이 {name2}{p2['subject']}의 어깨에 기대어, 서로의 체온을 느끼며 깊은 포옹을 나누기",
                f"{name2}가 {name}{p1['topic']}의 손을 꽉 쥐며 '나랑 같이 있어줘'라고 간청하기",
            ]
            result = rand.choice(contents)
        else:
            result = ""
    # 4) 애정(4) -> 집착(5): 첫 데이트 또는 함께 하는 시간
    elif prev_phase == 4 and curr_phase == 5:
        if rand.random() < 0.5:
            contents = [
                f"{name}이 {name2}{p2['subject']}와 함께 공원 벤치에 앉아, 노을 지는 하늘을 보며 서로의 미래를 이야기하기",
                f"{name2}가 {name}{p1['topic']}에게 '오늘부터 우리 officially 연인이지?'라고 묻자, 고개를 끄덕이며 미소 짓기",
            ]
        else:
            contents = [
                f"{name}이 {name2}{p2['subject']}와 함께 영화를 보며, 자연스럽게 손을 맞잡고 서로의 체온을 느끼기",
                f"{name2}가 {name}{p1['topic']}에게 '너 없이는 하루도 못 살 것 같아'라고 고백하며, 서로의 사랑을 확인하기",
            ]
        result = rand.choice(contents)
    # 5) 집착/중독(5): 50% 확률로 서로의 사랑 확인 또는 깊은 대화
    elif curr_phase == 5:
        if rand.random() < 0.5:
            contents = [
                f"{name}이 {name2}{p2['subject']}의 손을 꽉 쥐며 '내가 너를 정말 사랑해'라고 고백하며, 서로의 마음을 확인하기",
                f"{name2}가 {name}{p1['topic']}의 눈을 바라보며 '너 없이는 아무것도 할 수 없어'라고 속삭이기",
            ]
        else:
            contents = [
                f"{name}이 {name2}{p2['subject']}와 함께 밤하늘을 보며, 서로의 꿈과 미래를 이야기하며 깊은 대화를 나누기",
                f"{name2}가 {name}{p1['topic']}의 어깨에 기대어 '우리 영원히 같이 있어'라고 간청하며, 서로의 사랑을 확인하기",
            ]
        result = rand.choice(contents)
    # 6) 결말(6): 최종 사랑의 확인
    elif curr_phase == 6:
        contents = [
            f"{name}이 {name2}{p2['subject']}의 품에 파고들어, 서로의 사랑을 확인하며 영원한 결합을誓하기",
            f"{name2}가 {name}{p1['object']} 손을 잡고 '우리 이야기 이제부터 시작이야'라고 미소 지으며, 새로운 시작을 함께하기",
        ]
        result = rand.choice(contents)
    else:
        result = ""
    
    return result


def episode_gen_extended(filename_override: str = None):
    """progression_array와 에피소드 파일을 기반으로 에피소드 리스트를 생성합니다 (Extended 모드)."""
    try:
        progression = getattr(config, 'progression_array', [])
        if not progression:
            return "progression_array가 비어있습니다. 먼저 C/R/1번 메뉴를 실행하세요."
        
        with open("./data/episode_setup.json", 'r', encoding='utf-8') as f:
            setup_data = json.load(f)
        
        config.total_episodes = setup_data.get("total_episodes", 12)
        files_list = setup_data.get("files", [])
        
        if filename_override:
            main_filename = filename_override
        elif files_list:
            job_combined = (getattr(config, 'job', "") + getattr(config, 'job2', ""))
            selected_file = None
            if "선생" in job_combined and "학생" in job_combined:
                selected_file = next((f for f in files_list if "s2t" in f.get("filename", "")), None)
            elif "학생" in job_combined and "학생" in job_combined:
                selected_file = next((f for f in files_list if "s2s" in f.get("filename", "")), None)
            
            if selected_file:
                main_filename = selected_file["filename"]
            else:
                main_filename = rand.choice(files_list)["filename"]
        else:
            main_filename = "episode_a2a.txt"
        
        main_episodes = _parse_main_episode_file(f"./data/{main_filename}")
        
        # 서브 스토리 파일 로드
        if config.inc_flag == 1:
            nor_phases = _parse_episode_file("./data_extended/episode_inc.txt")
        else:        
            nor_phases = _parse_episode_file("./data_extended/episode_nor.txt")
        
        temp_theme = getattr(config, 'temp_theme', [])
        if temp_theme and temp_theme[0] and "블러디핑크" in str(temp_theme[0]):
            second_file = "./data_extended/episode_bp.txt"
        else:
            second_file = "./data_extended/episode_bimbo.txt"
        
        second_phases = _parse_episode_file(second_file)
        
        phase_counts = [0] * 7
        episode_phases = []
        
        for line in progression:
            phase_idx = _extract_phase_from_progression(line)
            episode_phases.append(phase_idx)
            phase_counts[phase_idx] += 1
        
        phase_names = ["혐오", "경계", "보통", "친밀", "애정", "집착/중독", "결말"]
        phase_summary = []
        for i, count in enumerate(phase_counts):
            if count > 0:
                phase_summary.append(f"{phase_names[i]}: {count}개")
        
        episodes_array = []
        prev_phase = -1
        
        plot_val = getattr(config, 'plot', "설정된 플롯 없음")
        
        total_eps = len(episode_phases)
        pos_seung = total_eps // 3 if total_eps > 3 else 1
        pos_jeon = (total_eps * 2) // 3 if total_eps > 3 else total_eps - 2
        if pos_seung == pos_jeon: pos_jeon = pos_seung + 1
        if pos_jeon >= total_eps: pos_jeon = total_eps - 2
        
        # 메인 스토리 추출
        num_main_needed = len(episode_phases)
        if len(main_episodes) < num_main_needed:
            main_sampled = [main_episodes[i % len(main_episodes)] for i in range(num_main_needed)]
        else:
            num_sections = min(10, len(main_episodes))
            section_size = len(main_episodes) // num_sections
            main_sampled = []
            
            for section_idx in range(num_sections):
                start = section_idx * section_size
                end = start + section_size if section_idx < num_sections - 1 else len(main_episodes)
                section = main_episodes[start:end]
                
                count = round(num_main_needed / num_sections)
                if len(section) < count:
                    main_sampled.extend(section)
                else:
                    main_sampled.extend(rand.sample(section, count))
            
            if len(main_sampled) > num_main_needed:
                main_sampled = main_sampled[:num_main_needed]
            elif len(main_sampled) < num_main_needed:
                remaining = [ep for ep in main_episodes if ep not in main_sampled]
                if remaining:
                    main_sampled.extend(rand.sample(remaining, min(num_main_needed - len(main_sampled), len(remaining))))
        
        sub_used_indices = {phase_idx: set() for phase_idx in range(7)}
        
        for i, phase_idx in enumerate(episode_phases):
            main_story = ""
            if i < len(main_sampled):
                main_story = main_sampled[i]
            
            nor_pool = nor_phases[phase_idx]
            second_pool = second_phases[phase_idx]
            
            combined_pool = []
            if nor_pool: combined_pool.extend(nor_pool)
            if second_pool: combined_pool.extend(second_pool)
            
            sub_story = ""
            if combined_pool:
                available = [ep for j, ep in enumerate(combined_pool) if j not in sub_used_indices[phase_idx]]
                if available:
                    sub_story = rand.choice(available)
                    sub_used_indices[phase_idx].add(combined_pool.index(sub_story))
                else:
                    sub_story = rand.choice(combined_pool)
            
            if main_story and sub_story:
                selected = f"{main_story} → {sub_story}"
            elif main_story:
                selected = main_story
            elif sub_story:
                selected = sub_story
            else:
                selected = f"[Phase {phase_idx + 1}] 에피소드 데이터 없음"
            
            transition_content = _get_phase_transition_content(prev_phase, phase_idx, ep_index=i)
            if transition_content:
                selected = f"{selected} + {transition_content}"
            
            episodes_array.append(selected)
            prev_phase = phase_idx
        
        # 기-승-전-결 마커 추가
        episodes_array[0] = f"[기] {plot_val} - 첫 만남\n{episodes_array[0]}"
        if pos_seung < total_eps:
            episodes_array[pos_seung] = f"[승] {plot_val} - 서서히 가까워지는 마음\n{episodes_array[pos_seung]}"
        if pos_jeon < total_eps:
            episodes_array[pos_jeon] = f"[전] {plot_val} - 고백과 관계의 전환점\n{episodes_array[pos_jeon]}"
        episodes_array[total_eps - 1] = f"[결] {plot_val} - 깊은 사랑과 완전한 결합\n{episodes_array[total_eps - 1]}"
        
        total_eps = len(episodes_array)
        config.total_episodes = total_eps
        
        result_lines = []
        result_lines.append("=== 생성된 에피소드 리스트 (Extended) ===")
        result_lines.append(f"메인 스토리: {main_filename}")
        result_lines.append(f"서브 스토리: {second_file.split('/')[-1]}")
        result_lines.append(f"Phase 분포: {', '.join(phase_summary)}")
        result_lines.append("")
        
        for idx, ep in enumerate(episodes_array):
            phase_name = phase_names[min(episode_phases[idx], 6)]
            result_lines.append(f"Episode {idx + 1} [{phase_name}]: {ep}")
        
        config.result_text = "\n".join(result_lines)
        config.episode_gen_flag = True
        return config.result_text
    
    except Exception as e:
        return f"에피소드 생성 중 오류 발생: {e}"


def theme_file_sel(force_inc=None):
    """Extended 모드 테마 파일 선택.
    force_inc가 지정되면 해당 값을 유지, 기본값 0."""
    if force_inc is not None:
        config.inc_flag = force_inc

    if config.inc_flag == 1:
        theme_file = "./data_extended/theme_extended_inc.txt"
    else:
        theme_file = "./data_extended/theme_extended.txt"
    return theme_file

def calculate_inc_age():
    """inc_flag가 1일 때 나이 계산."""
    theme_job1 = getattr(config, 'theme_job1', '')
    theme_job2 = getattr(config, 'theme_job2', '')
    job1 = getattr(config, 'job', '')
    job2 = getattr(config, 'job2', '')
    
    def get_student_age_range(job):
        if '중학생' in job: return (13, 15)
        elif '고등학생' in job: return (16, 18)
        elif '대학생' in job: return (19, 23)
        elif '학생' in job: return (13, 23)
        return None
    
    age_range1 = get_student_age_range(job1) or get_student_age_range(theme_job1)
    age_range2 = get_student_age_range(job2) or get_student_age_range(theme_job2)
    is_student1 = age_range1 is not None
    is_student2 = age_range2 is not None
    
    age_diff_max = getattr(config, 'theme_age_diff_max', 5)
    age_diff_min = getattr(config, 'theme_age_diff_min', 0)
    if age_diff_max < age_diff_min:
        age_diff_max, age_diff_min = age_diff_min, age_diff_max
    
    younger_keywords = ['여동생', '남동생', '아들', '딸', '동생']
    older_keywords = ['엄마', '아빠', '누나', '언니', '오빠', '형', '아버지', '어머니']
    is_younger = any(kw in theme_job1 for kw in younger_keywords)
    is_older = any(kw in theme_job1 for kw in older_keywords)
    
    diff = rand.randint(age_diff_min, age_diff_max) if age_diff_max > 0 else 0
    
    if is_student1 and is_student2:
        min_age1, max_age1 = age_range1
        min_age2, max_age2 = age_range2
        config.age = rand.randint(min_age1, max_age1)
        if is_younger: config.age2 = config.age + diff
        elif is_older: config.age2 = config.age - diff
        else: config.age2 = config.age + (diff if rand.random() < 0.5 else -diff)
        config.age = min(max(config.age, min_age1), max_age1)
        config.age2 = min(max(config.age2, min_age2), max_age2)
    elif is_student1:
        min_age1, max_age1 = age_range1
        config.age = rand.randint(min_age1, max_age1)
        config.age2 = config.age + diff
        config.age2 = min(max(config.age2, 20), 40)
    elif is_student2:
        min_age2, max_age2 = age_range2
        config.age2 = rand.randint(min_age2, max_age2)
        config.age = config.age2 + diff
        config.age = min(max(config.age, 20), 40)
    else:
        if is_younger:
            config.age = rand.randint(20, 35)
            config.age2 = config.age + diff
        elif is_older:
            config.age2 = rand.randint(20, 35)
            config.age = config.age2 + diff
        else:
            config.age = rand.randint(20, 40)
            config.age2 = config.age + (diff if rand.random() < 0.5 else -diff)
        config.age = min(max(config.age, 20), 40)
        config.age2 = min(max(config.age2, 20), 40)
    
    attempts = 0
    while (config.age < 1 or config.age2 < 1 or config.age <= 10 or config.age2 <= 10 or config.age > 40 or config.age2 > 40):
        diff = rand.randint(age_diff_min, age_diff_max) if age_diff_max > 0 else 0
        if is_student1 and is_student2:
            min_age1, max_age1 = age_range1
            min_age2, max_age2 = age_range2
            config.age = rand.randint(min_age1, max_age1)
            config.age2 = config.age + diff if is_younger else config.age - diff if is_older else config.age + (diff if rand.random() < 0.5 else -diff)
            config.age = min(max(config.age, min_age1), max_age1)
            config.age2 = min(max(config.age2, min_age2), max_age2)
        elif is_student1:
            min_age1, max_age1 = age_range1
            config.age = rand.randint(min_age1, max_age1)
            config.age2 = min(max(config.age + diff, 20), 40)
        elif is_student2:
            min_age2, max_age2 = age_range2
            config.age2 = rand.randint(min_age2, max_age2)
            config.age = min(max(config.age2 + diff, 20), 40)
        else:
            config.age = rand.randint(20, 35)
            config.age2 = min(max(config.age + diff, 20), 40)
        attempts += 1
        if attempts > 10:
            config.age = 25
            config.age2 = 25 + diff
            break
    
    return f"나이 계산 완료: {config.name}({config.age}세), {config.name2}({config.age2}세)"
