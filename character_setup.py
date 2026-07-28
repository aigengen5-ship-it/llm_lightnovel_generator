import random as rand
import config

def random_prompt(wildcard, mynumber):
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

def name_define(flag = True):
    """캐릭터의 이름과 국적을 설정하는 함수"""
    nationality_tag = ["korean", "japanese", "western", "fantasy", "others"]
    
    # Character A setup
    if config.nationality == "" or flag == True:
        config.nationality = nationality_tag[1] # Default to japanese
        if config.sex == "여자" or config.sex == "female":
            nametag = "female"
        else:            
            nametag = "male"

        name_tag_path = "./data/name/" + nametag + "_" + config.nationality + ".txt"
        if config.name == "" or flag == True:
            config.name = random_prompt(name_tag_path, -1)

    # Character B setup
    if config.nationality2 == "" or flag == True:
        config.nationality2 = nationality_tag[1] # Default to japanese

        if config.sex2 == "여자":
            nametag2 = "female"
        else:            
            nametag2 = "male"

        name_tag2_path = "./data/name/" + nametag2 + "_" + config.nationality2 + ".txt"
        if config.name2 == "" or flag == True:
            config.name2 = random_prompt(name_tag2_path, -1)

def set_inc_relationship():
    """inc_flag=1: 가족애 모드 관계 설정 (관계 → 성별 → 직업/나이)"""
    # relation.txt 내용 통합
    RELATIONS = [
        ("이모", "남자조카"), ("이모", "여자조카"),
        ("남자사촌", "여자사촌"), ("여자사촌", "남자사촌"),
        ("남자사촌", "남자사촌"), ("여자사촌", "여자사촌"),
        ("딸", "아버지"), ("딸", "엄마"), ("아들", "아빠"), ("아들", "엄마"),
        ("아빠", "딸"), ("아빠", "아들"), ("엄마", "아들"), ("엄마", "딸"),
        ("형", "남동생"), ("오빠", "여동생"), ("누나", "남동생"), ("누나", "여동생"),
        ("삼촌", "남자조카"), ("삼촌", "여자조카"),
        ("여동생", "오빠"), ("여동생", "언니"),
        ("남동생", "형"), ("남동생", "오빠"),
    ]
    gender_map = {
        "남자조카": "남자", "남자사촌": "남자", "아버지": "남자", "아빠": "남자",
        "아들": "남자", "형": "남자", "오빠": "남자", "남동생": "남자", "삼촌": "남자",
        "이모": "여자", "여자조카": "여자", "여자사촌": "여자", "딸": "여자",
        "엄마": "여자", "누나": "여자", "언니": "여자", "여동생": "여자",
    }

    # 관계 선택 (동성 피함)
    while True:
        rel1, rel2 = rand.choice(RELATIONS)
        sex = gender_map.get(rel1, "여자")
        sex2 = gender_map.get(rel2, "남자")
        #if not (sex == "여자" and sex2 == "여자") and not (sex == "남자" and rand.randint(0, 3) > 0):
        if sex == "여자" and sex2 == "남자":
            break

    config.rel1 = rel1
    config.rel2 = rel2
    config.sex = sex
    config.sex2 = sex2

    # 직업/나이 설정 (관계별 나이 차이 검증)
    parent_rels = ["아버지", "아빠", "엄마"]
    child_rels = ["아들", "딸"]
    uncle_aunt_rels = ["삼촌", "이모"]
    nephew_niece_rels = ["남자조카", "여자조카"]
    sibling_cousin_rels = ["형", "오빠", "누나", "언니", "남동생", "여동생", "남자사촌", "여자사촌"]

    while True:
        # 직업 로드
        temp1 = random_prompt("./data/job.txt", -1)
        job_data1 = temp1.split(",")
        tempjob, tempsex, tempagemin, tempagemax = job_data1[0], job_data1[1], int(job_data1[2]), int(job_data1[3])

        temp2 = random_prompt("./data/job2.txt", -1)
        job_data2 = temp2.split(",")
        temp2job, temp2sex, temp2agemin, temp2agemax = job_data2[0], job_data2[1], int(job_data2[2]), int(job_data2[3])

        age1_min, age1_max = max(13, tempagemin), min(40, tempagemax)
        age2_min, age2_max = max(13, temp2agemin), min(40, temp2agemax)
        if age1_min > age1_max or age2_min > age2_max:
            continue

        age1 = rand.randint(age1_min, age1_max)
        age2 = rand.randint(age2_min, age2_max)

        # 관계별 나이 검증
        is_valid = True
        if rel1 in parent_rels and age1 < age2 + 15:
            is_valid = False
        elif rel1 in child_rels and age1 > age2 - 15:
            is_valid = False
        elif rel1 in uncle_aunt_rels and age1 < age2 + 10:
            is_valid = False
        elif rel1 in nephew_niece_rels and age1 > age2 - 10:
            is_valid = False
        elif rel1 in sibling_cousin_rels:
            if rel1 in ["형", "오빠", "누나", "언니"] and age1 <= age2:
                is_valid = False
            elif rel1 in ["남동생", "여동생"] and age1 >= age2:
                is_valid = False
            elif rel1 in ["남자사촌", "여자사촌"] and abs(age1 - age2) < 1:
                is_valid = False
        # 성별 검증
        if sex == "남자" and "남" not in tempsex:
            is_valid = False
        if sex2 == "남자" and "남" not in temp2sex:
            is_valid = False
        if sex == "여자" and "여" not in tempsex:
            is_valid = False
        if sex2 == "여자" and "여" not in temp2sex:
            is_valid = False

        if is_valid:
            config.job = tempjob
            config.age = age1
            config.job2 = temp2job
            config.age2 = age2
            break


def job_and_age_init():
    """직업을 랜덤하게 선택하고 그에 따른 나이를 계산하는 함수"""
    # inc_flag=1: 가족애 모드 전용 관계 설정 (이미 설정된 경우 재설정 금지)
    if config.json_value.get("extended", "no") == "yes" and getattr(config, 'inc_flag', 0) == 1:
        if not getattr(config, 'rel1', ''):
            set_inc_relationship()
        return

    # theme_gen에서 저장된 임시변수 처리
    theme_job1 = config.theme_job1
    theme_job2 = config.theme_job2
    age_diff_max = config.theme_age_diff_max
    age_diff_min = config.theme_age_diff_min

    # 주인공 직업 설정
    # cmd_job이 설정되면 해당 라인 직업 강제 적용
    cmd_job_val = getattr(config, 'cmd_job', None)
    if cmd_job_val is not None:
        job_lines = open("./data/job.txt", "r", encoding="utf-8").read().strip().split("\n")
        idx = config.cmd_job - 1  # 1-based
        if 0 <= idx < len(job_lines):
            job_data = job_lines[idx].strip()
            config.job_raw = job_data
            config.job = job_data.split(",")[0]
            try:
                parts = job_data.split(",")
                if len(parts) >= 4:
                    config.age = rand.randint(int(parts[2]), int(parts[3]))
            except (ValueError, IndexError):
                config.age = rand.randint(20, 30)
    elif theme_job1:
        # #누나(학생회장) 형식에서 실제 직업 추출
        import re
        match = re.search(r'\(([^)]+)\)', theme_job1)
        config.job = match.group(1) if match else theme_job1
        # 나이가 설정되지 않았다면 기본값 설정
        if not getattr(config, 'age', 0) or config.age == -1:
            config.age = rand.randint(20, 40)
    elif config.job == "RANDOM":
        job_data = random_prompt("./data/job.txt", -1)
        if job_data:
            config.job_raw = job_data
            config.job = job_data.split(",")[0]
            try:
                parts = job_data.split(",")
                if len(parts) >= 4:
                    config.age = rand.randint(int(parts[2]), int(parts[3]))
                else:
                    config.age = rand.randint(20, 30)
            except (ValueError, IndexError):
                config.age = rand.randint(20, 30)
        else:
            config.job = "평범한 직업"
            config.age = 25
    else:
        config.job = config.job if config.job else "평범한 직업"
        config.age = config.age if config.age else 25

    # '학생' 직업에 대한 나이 및 세부 직업 설정 (주인공)
    if config.job == "대학생":
        config.age = rand.randint(20, 23)
    elif config.job == "고등학생":
        if not getattr(config, 'age', 0) or config.age == -1:
            config.age = rand.randint(17, 19)
    elif config.job == "중학생":
        if not getattr(config, 'age', 0) or config.age == -1:
            config.age = rand.randint(14, 16)
    elif  config.job.find("학생") > -1:
        if not getattr(config, 'age', 0) or config.age == -1:
            config.age = rand.randint(20, 23)
    else:
        if not getattr(config, 'age', 0):
            config.age = rand.randint(20, 40)

    # 상대방 직업 설정
    # cmd_job2가 설정되면 해당 라인 직업 강제 적용
    if getattr(config, 'cmd_job2', None) is not None:
        job2_lines = open("./data/job2.txt", "r", encoding="utf-8").read().strip().split("\n")
        idx = config.cmd_job2 - 1  # 1-based
        if 0 <= idx < len(job2_lines):
            job2_data = job2_lines[idx].strip()
            config.job2_raw = job2_data
            config.job2 = job2_data.split(",")[0]
            try:
                parts = job2_data.split(",")
                if len(parts) >= 4:
                    config.age2 = rand.randint(int(parts[2]), int(parts[3]))
            except (ValueError, IndexError):
                config.age2 = rand.randint(20, 30)
    elif theme_job2:
        # #아들(대학생) 형식에서 실제 직업 추출
        import re
        match = re.search(r'\(([^)]+)\)', theme_job2)
        config.job2 = match.group(1) if match else theme_job2
    elif not config.job2:
        config.job2 = "평범한 직업"

    # 나이 차이 적용 (theme_gen에서 저장된 값 사용)
    if age_diff_max > 0 and age_diff_min > 0:
        try:
            diff = rand.randint(age_diff_min, age_diff_max)
            
            # 상대방 직업에 따른 나이 범위
            if config.job2 == "학생":
                min_age2, max_age2 = 14, 19
            elif config.job2 == "대학생":
                min_age2, max_age2 = 20, 23
            else:
                min_age2, max_age2 = 20, 40
            
            # 주인공 나이를 기준으로 상대방 나이 계산
            if rand.randint(0, 1) == 0:
                config.age2 = config.age + diff
            else:
                config.age2 = config.age - diff
            
            # 범위 제한
            config.age2 = min(max(config.age2, min_age2), max_age2)
        except (ValueError, IndexError):
            pass
    
    # '학생' 직업에 대한 나이 및 세부 직업 설정 (상대방)
    if config.job2 == "대학생":
        if not getattr(config, 'age2', 0) or config.age2 == -1:
            config.age2 = rand.randint(20, 23)
    elif config.job2 == "고등학생":
        if not getattr(config, 'age2', 0) or config.age2 == -1:
            config.age2 = rand.randint(17, 19)
    elif config.job2 == "중학생":
        if not getattr(config, 'age2', 0) or config.age2 == -1:
            config.age2 = rand.randint(14, 16)
    elif  config.job2.find("학생") > -1:
        if not getattr(config, 'age2', 0) or config.age2 == -1:
            config.age2 = rand.randint(14, 19)
    else:
        if not getattr(config, 'age2', 0) or config.age2 == -1:
            config.age2 = rand.randint(20, 40)
    
    # extended 모드이고 inc_flag가 1이면 calculate_inc_age 사용
    if config.json_value["extended"] == "yes":
        if config.inc_flag == 1:
            import story_gen
            story_gen.calculate_inc_age()

def personality_init(json_value):
    """성격, 말투 및 인생 목표를 설정하는 함수"""
    # 1. 성격 태그 설정
    tag = random_prompt("data/personality_tag.txt", json_value.get("personality", 0) - 1)
    if tag:
        # 태그에서 실제 성격 명칭 추출 (보통 #으로 구분)
        config.personality_real = tag.split("#")[0].strip()
    else:
        config.personality_real = "평범한 성격"
    
    # 2. 성격 세부 설명(text) 설정
    try:
        with open("./data/personality.txt", 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if config.personality_real in line and line.startswith("##"):
                    text = []
                    for j in range(i+1, len(lines)):
                        if lines[j].startswith("##"): break
                        text.append(lines[j])
                    config.personality_text = "".join(text).strip()
                    break
    except Exception:
        config.personality_text = "특별한 특징이 없는 평범한 성격입니다."

    # 3. 인생 목표 설정 (참조 디렉토리에서 명시적 로직을 찾지 못해 기본 랜덤 리스트 구현)
    objectives = ["세계 평화", "부자가 되는 것", "진정한 사랑 찾기", "최고의 전문가 되기", "조용한 삶 살기", "복수 성공"]
    config.objective = rand.choice(objectives)
    config.happiness = 0
    if (config.sex == "female"):
        if (config.age < 20):
            config.clothes = random_prompt("./data_comfyui/clothes_student.txt", -1)
        else:        
            config.clothes = random_prompt("./data_comfyui/clothes_adult.txt", -1)
    else:
        config.clothes = "평범한 남자 옷"

def archetype_setup(json_value):
    """
    config.job을 기반으로 data/character_archetypes.json에서
    매칭되는 아키타입을 찾아 캐릭터 외모/성격/복장을 오버라이드한다.

    plot.json의 archtype_enb == "yes"일 때만 사용.
    character_init() 이후에 호출해야 body_dic이 준비됨.

    Args:
        json_value: plot.json에서 로드된 설정 딕셔너리
    """
    # archtype_enb 체크
    if json_value.get("archtype_enb", "no") != "yes":
        return

    # 현재 설정된 직업 확인
    current_job = config.job if config.job else ""
    if not current_job:
        return

    # 아키타입 JSON 로드
    try:
        with open("./data/character_archetypes.json", "r", encoding="utf-8") as f:
            import json
            archetype_data = json.load(f)
    except Exception as e:
        print(f"Error reading character_archetypes.json: {e}")
        return

    # enabled == "yes"인 아키타입 중 jobs에 current_job이 포함된 것 필터링
    # '범용'이 jobs에 있으면 모든 직업에 매칭 가능
    candidates = []
    for arch in archetype_data.get("archetypes", []):
        if arch.get("enabled", "no") != "yes":
            continue
        arch_jobs = arch.get("jobs", [])
        if current_job in arch_jobs or "범용" in arch_jobs:
            candidates.append(arch)

    if not candidates:
        # 매칭되는 아키타입이 없으면 기존 랜덤 설정 유지
        return

    # 여러 매칭 중 랜덤 선택
    selected = rand.choice(candidates)

    # --- 외모 필드 오버라이드 ---
    config.hair_color = selected.get("hair_color", config.hair_color)
    config.hair_style = selected.get("hair_style", config.hair_style)
    config.face_style = selected.get("face_style", config.face_style)
    config.eye_color = selected.get("eye_color", config.eye_color)
    config.skin_color = selected.get("skin_color", config.skin_color)
    config.acc = selected.get("accessories", config.acc)
    config.clothes = selected.get("clothes", config.clothes)

    # --- 체형: 문자열 → body_dic 인덱스로 변환 ---
    def _archetype_resolve_index(dic_key, arch_value):
        """아키타입의 문자열 체형 값을 body_dic 인덱스로 변환."""
        lst = config.body_dic.get(dic_key, [])
        if not lst:
            return 0
        arch_val_stripped = arch_value.strip().rstrip(",")
        for i, item in enumerate(lst):
            if item.strip().rstrip(",") == arch_val_stripped:
                return i
        # 정확히 일치하지 않으면 부분 매칭 시도
        for i, item in enumerate(lst):
            if arch_val_stripped in item.strip().rstrip(",") or item.strip().rstrip(",") in arch_val_stripped:
                return i
        # 찾지 못하면 0 반환
        return 0

    arch_breasts = selected.get("breasts_size", "")
    if arch_breasts:
        config.breasts_size = _archetype_resolve_index("breasts_size", arch_breasts)

    arch_hip = selected.get("hip_size", "")
    if arch_hip:
        config.hip_size = _archetype_resolve_index("hip_size", arch_hip)

    arch_body = selected.get("body_size", "")
    if arch_body:
        config.body_size = _archetype_resolve_index("body_size", arch_body)

    # --- 성격 오버라이드 ---
    arch_personality = selected.get("personality", "")
    if arch_personality:
        config.personality_real = arch_personality


def random_setup_all():
    """모든 캐릭터 설정을 랜덤하게 초기화하는 함수"""
    # 성별은 여성으로 고정
    config.sex = "female"
    
    # 이름 및 국적 설정
    name_define(True)
    
    # 직업 및 나이 설정
    job_and_age_init()
    
    # 신체 및 외형 설정
    character_init(config.sex, config.json_value)
    
    # 아키타입 기반 오버라이드 (archtype_enb == "yes"일 때)
    archetype_setup(config.json_value)
    
    # 성격 및 목표 설정
    personality_init(config.json_value)

def character_init(sex, json_value):
    """캐릭터의 신체 및 외형 설정을 초기화하는 함수"""
    # local variables for easier access to config
    body_dic = {}
    start = 0
    try:
        with open("./data/body_tag.txt", 'r', encoding='utf-8') as f1:
            temp = f1.readlines() 
            for line in temp: 
                if line[0] == "#":
                    if (start == 1):
                        body_dic[dict_tag] = dict_list
                    dict_tag = line[1:].strip()
                    dict_list = []
                    start = 1
                else:
                    dict_list.append(line.strip())
    except Exception as e:
        print(f"Error reading body_tag.txt: {e}")

    if (sex == "male"):                
        config.breasts_size = 0
        config.hip_size = 0
    else:        
        if config.breasts_size == -1:
            config.breasts_size = rand.randint(0, len(body_dic.get("breasts_size", [0]))//2)
        if config.hip_size == -1:
            config.hip_size =  rand.randint(0, len(body_dic.get("hip_size", [0]))//2)

    # special
    if config.body_size == -1:    
        if config.age <= 16:
            config.body_size = rand.randint(0, len(body_dic.get("body_size", [0])) // 3)
        elif config.age < 20:
            config.body_size = rand.randint(0, len(body_dic.get("body_size", [0])) // 2)
        elif config.age > 30:
            config.body_size = rand.randint(len(body_dic.get("body_size", [0]))//2, len(body_dic.get("body_size", [0])) -1 )
        else:        
            config.body_size = rand.randint(0, len(body_dic.get("body_size", [0])) - 1 )

    # For TAG
    if "body_size" in body_dic:
        config.body_shape = body_dic["body_size"][config.body_size] 

    # Hair color
    if config.hair_color == "":
        config.hair_color = random_prompt("data_comfyui/Hair_04.Color.txt", -1) 

    # Hair Style
    if config.hair_style == "":            
        if sex == "male":
            if rand.randint(0,1) == 0:
                config.hair_style = "short cut,pixie cut,"
            else:
                config.hair_style = "short cut,bob cut,"
        else:
            config.hair_style = random_prompt("data_comfyui/hairlength.txt", -1) + ","
        
        # Select Ponytail/Braid
        if (rand.randint(0,2) == 0):
            config.hair_style += random_prompt("data_comfyui/ponytail.txt", -1) + ","
        elif (rand.randint(0,5) == 0):
            config.hair_style += random_prompt("data_comfyui/hairbraid.txt", -1) + ","
        # Select HairBang
        if (rand.randint(0,2) == 0):
            config.hair_style += random_prompt("data_comfyui/hairbang.txt", -1) + ","
        # Hair Status(wavy...)
        config.hair_style += random_prompt("data_comfyui/hairstatus.txt", -1) + ","
        
        # Clean hair for man
        if sex == "male":
            if rand.randint(0,1) == 0:
                config.hair_style = "short cut,pixie cut,"
            else:
                config.hair_style = "short cut,bob cut,"
        
    # Face 
    if config.eye_color == "":
        config.eye_color = random_prompt("data_comfyui/Eye_Color.txt", -1) + ","

    # Update face
    if "face" in body_dic:
        config.face_style = body_dic["face"][rand.randint(0, len(body_dic["face"])-1)].strip()

    # Eyebrow
    if rand.randint(0,4) == 0:
        config.face_style += "short[TMP] and thin eyebrows, "
    elif rand.randint(0,4) == 1:
        config.face_style += "long[TMP] and thin eyebrows, "
    else:
        config.face_style += "medium[TMP] and thin eyebrows, "

    if rand.randint(0,3) == 0:
        config.face_style = config.face_style.replace("[TMP]", ", straight") 
    elif rand.randint(0,3) == 1:
        config.face_style = config.face_style.replace("[TMP]", ", arched") 
    else:
        #Default
        config.face_style = config.face_style.replace("[TMP]", "") 

    if rand.randint(1, 10) <= json_value.get("freckles", 0):
        config.face_style += "freckles,"

    if rand.randint(1, 10) <= json_value.get("glasses", 0):
        config.face_style += random_prompt("data_comfyui/Eyewear.txt", -1)  + ","

    if rand.randint(1, 10) <= json_value.get("hairacc", 0):
        config.face_style += random_prompt("data_comfyui/Accessories_Hair.txt", -1)  + ","

    config.acc = random_prompt("data_comfyui/accessory.txt", -1)

    # Skin Color Setup
    if config.skin_color == "":
        a = rand.randint(1, 10)
        if a == 1:
            config.skin_color = "dark skin"
        elif a < 5:
            config.skin_color = "white skin"
        else:
            config.skin_color = "pale skin"

    # Save body_dic to config for character_sheet use
    config.body_dic = body_dic
    return                

def character_sheet(love_value):
    if config.job_attribute == "":
        config.job_attribute = rand.choice([ "긍지", "의무", "평범", "불만"])

    temp = love_value
    character_sheet_text = "## Character Sheet ##\n"
    character_sheet_text += "이름: " + config.name + "\n"
    character_sheet_text += "나이: " + str(config.age) + "\n"
    character_sheet_text += "성별: " + config.sex + "\n"
    character_sheet_text += "성격/말투: " + config.personality_real + "\n"
    character_sheet_text += "직업: " + config.job + "\n"
    character_sheet_text += "직업에 대한 평가(긍지/의무/평범/불만): " + config.job_attribute + "\n"
    character_sheet_text += "인생 목표: " + config.objective + "\n"
    character_sheet_text += "현재 느끼는 행복도: " + str(config.happiness) + "%\n"
    character_sheet_text += "머리색: " + config.hair_color + "\n"
    character_sheet_text += "헤어스타일: " + config.hair_style + "\n"
    character_sheet_text += "눈 색깔: " + config.eye_color + "\n"
    character_sheet_text += "피부 색깔: " + config.skin_color + "\n"
    
    # 얼굴 스타일을 두 줄로 나누어 출력
    face_style_text = config.face_style
    mid = len(face_style_text) // 2
    # 콤마(,)가 있다면 그 지점에서 나누는 것이 자연스러움
    comma_pos = face_style_text.find(',', mid)
    if comma_pos != -1:
        line1 = face_style_text[:comma_pos+1]
        line2 = face_style_text[comma_pos+1:].strip()
    else:
        line1 = face_style_text[:mid]
        line2 = face_style_text[mid:]
        
    character_sheet_text += f"얼굴 스타일 1: {line1}\n"
    character_sheet_text += f"얼굴 스타일 2: {line2}\n"
    character_sheet_text += "액서서리: " + config.acc + "\n"
    # body_dic이 비어있을 때 방어 코드
    if not config.body_dic:
        config.body_dic = {"breasts_size": ["medium_breasts"], "hip_size": ["wide_hips"], "body_size": ["young, youthful appearance,"]}
        config.breasts_size = 0
        config.hip_size = 0
        config.body_size = 0

    # config_export.yaml에서 breasts_size/hip_size/body_size가 문자열로 로드된 경우
    # 정수 인덱스로 변환 (list indices must be integers or slices, not str 방지)
    def _resolve_size_index(key, dic_key):
        val = getattr(config, key)
        if isinstance(val, int):
            return val
        # 문자열이면 body_dic에서 인덱스 찾기
        lst = config.body_dic.get(dic_key, [])
        val_stripped = val.strip().rstrip(",")
        for i, item in enumerate(lst):
            if item.strip().rstrip(",") == val_stripped:
                return i
        # 찾지 못하면 0 반환
        return 0

    config.breasts_size = _resolve_size_index("breasts_size", "breasts_size")
    config.hip_size = _resolve_size_index("hip_size", "hip_size")
    config.body_size = _resolve_size_index("body_size", "body_size")

    character_sheet_add = "가슴크기: " + config.body_dic["breasts_size"][config.breasts_size] + "\n"
    character_sheet_add = character_sheet_add.replace("NONE", "평범")
    character_sheet_text += character_sheet_add
    character_sheet_add = "엉덩이 크기: " + config.body_dic["hip_size"][config.hip_size] + "\n"
    character_sheet_add = character_sheet_add.replace("NONE", "평범")
    character_sheet_text += character_sheet_add
    character_sheet_add = "몸매: " + config.body_dic["body_size"][config.body_size] + "\n"
    character_sheet_add = character_sheet_add.replace("NONE", "평범")
    character_sheet_text += character_sheet_add

    character_sheet_add = "복장: " + config.clothes + "\n"
    character_sheet_text += character_sheet_add

    if config.json_value["extended"] == "yes":
        # 에피소드 인덱스가 있으면 해당 시점의 sheet 사용
        ep_index = getattr(config, 'current_episode_index', 0)
        character_sheet_text += character_sheet_extended(ep_index)

    if (config.rel1 != ""):
        character_sheet_text += f"\n혈연관계: {config.name2}의 {config.rel1}.\n"

    rel1_update = getattr(config, 'rel1_update', '')
    if rel1_update:
        character_sheet_text += f"\n{rel1_update}\n"

    character_sheet_text += "\n기타 특징\n\n" + config.personality_text + "\n"

    comfyui_prompt = ""

    return character_sheet_text, comfyui_prompt

def partner_sheet():
    """상대방의 설정을 보여주는 시트를 생성합니다."""
    sheet_text = "## 상대방 캐릭터 시트 ##\n"
    sheet_text += f"상대방 이름: {config.name2}\n"
    sheet_text += f"상대방 나이: {config.age2}\n"
    sheet_text += f"상대방 성별: {config.sex2}\n"
    sheet_text += f"상대방 직업: {config.job2}\n"
    sheet_text += f"상대방 외모: {config.appearance2}\n"
    sheet_text += f"상대방 성격: {config.personality2}\n"
    sheet_text += f"상대방 말투: {config.talking_style2}\n"
    sheet_text += f"상대방 복장: {getattr(config, 'outfit2', getattr(config, 'opponent_outfit', '미설정'))}\n"
    return sheet_text


# Extended: character_sheet 헬퍼 함수

def _snapshot_to_text(snapshot):
    """단일 스냅샷을 텍스트로 변환."""
    lines = []
    
    return "\n".join(lines)


def character_sheet_extended(ep_index: int = 0):
    """에피소드 인덱스에 해당하는 character sheet 반환.
    
    Args:
        ep_index: 에피소드 인덱스 (0-based)
    
    Returns:
        해당 에피소드의 character sheet 텍스트
    """
    # episode_snapshots가 비어있으면 현재 상태 사용
    if not config.episode_snapshots:
        # EP1(초기)이면 카운터 0으로 반환 (플롯 생성 시 누적값이 이미 반영될 수 있음)
        if ep_index == 0:
            snapshot = {
                "sex_count": 0,
                "masturbation_count": 0,
                "patting_count": 0,
                "normal_sex_count": 0,
                "reverse_sex_count": 0,
                "cowboy_sex_count": 0,
                "anal_sex_count": 0,
                "pose_sex_count": 0,
            }
        else:
            snapshot = {
                "sex_count": config.sex_count,
                "masturbation_count": config.masturbation_count,
                "patting_count": config.patting_count,
                "normal_sex_count": config.normal_sex_count,
                "reverse_sex_count": config.reverse_sex_count,
                "cowboy_sex_count": config.cowboy_sex_count,
                "anal_sex_count": config.anal_sex_count,
                "pose_sex_count": config.pose_sex_count,
            }
        return _snapshot_to_text(snapshot)
    
    # 인덱스 범위 체크
    idx = min(ep_index, len(config.episode_snapshots) - 1)
    snapshot = config.episode_snapshots[idx]
    return _snapshot_to_text(snapshot)
