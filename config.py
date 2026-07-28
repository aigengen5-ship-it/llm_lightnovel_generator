import json
import random as rand

# Setup
with open('plot.json') as f:
    json_value = json.load(f)
#json_value = ""

# Episode storage - create arrays based on total_episodes from episode_setup.json
try:
    with open('data/episode_setup.json', 'r', encoding='utf-8') as ef:
        episode_setup = json.load(ef)
    total_episodes = episode_setup.get("total_episodes", 12)
except Exception:
    total_episodes = 12

# Episode content array (index 0 = episode 1, etc.)
episode_content = ["" for _ in range(total_episodes)]
# Episode track array to monitor which episodes have been received
episode_track = [False for _ in range(total_episodes)]

episode_full_content = ["" for _ in range(total_episodes)]
episode_full_original_content = ["" for _ in range(total_episodes)]  # 리뷰 전 원문
# Episode track array to monitor which episodes have been received
episode_full_track = [False for _ in range(total_episodes)]

# Episode별 캐릭터 시트 배열 (plot_gen에서 동적 생성)
episode_protagonist_sheets = []
episode_partner_sheets = []

# Episode별 스냅샷 (character_sheet_extended에서 사용)
episode_snapshots = []

# Character A
name = ""
sex = ""
nationality = ""
age = -1
job = ""
job_attribute = ""
objective = ""
personality_real = ""
personality_text = ""
rel1 = ""
rel1_update = ""

# Character B
name2 = ""
sex2 = "남자"
nationality2 = ""
age2 = 0
job2 = ""
outfit2 = "일상복"
appearance2 = "평범한 일상복"
personality2 = "착함"
talking_style2 = "평범하게 말함"

# Appearance (Character A)
hair_color = ""
hair_style = ""
eye_color = ""
eye_shape = ""
skin_color = ""
face_style = ""
acc = ""
clothes = ""
body_dic = {}
breasts_size = -1
hip_size = -1
body_size = -1
bimbo_clothes1 = ""
bimbo_clothes2 = ""
eye_danbooru = ""

# Theme, plot
guide_num = 2
plot = ""
plot_result = ""
result_text = ""
first_trigger = ""
second_trigger = ""
first_event = ""
second_event = ""
first_event_ep = -1    # first_event가 배치된 에피소드 번호
second_event_ep = -1   # second_event가 배치된 에피소드 번호
rag_word = ""
rag_dialog = ""

# Theme temporary variables (set by theme_gen, processed by job_and_age_init)
theme_job1 = ""
theme_job2 = ""
theme_age_diff_min = 0
theme_age_diff_max = 0

# Theme extended parts (parts[5:] from theme line, stored as array)
temp_theme = []

# Theme 확장 변수들 (theme_gen / theme_gen_auto에서 동적 할당)
theme_body_change = None           # 신체 변화 정보 dict
theme_corruption_elements = []     # 타락 요소 배열
theme_jinshugai = ""               # 진수개 정보
theme_events = []                  # 이벤트 배열
theme_breeds = []                  # 번reed 배열
selected_jinshugai_id = None       # 명령행에서 전달된 jinshugai ID
cmd_job = None
cmd_job2 = None

# 타락 가이드 (theme_gen에서 생성)
corruption_elements = []           # 타락 요소 상세
body_change = None                 # 신체 변화 dict
body_change_sign = ""              # 신체 변화 징후
corruption_guides = ""             # 타락 가이드 텍스트
partner_corruption_guides = ""     # 파트너 타락 가이드 텍스트

# 트리거 (theme_gen에서 생성)
abnormal_trigger = ""              # 비정상 트리거
crisis_trigger = ""                # 위기 트리거

# 페르소나 (theme_gen에서 생성)
persona_text = ""                  # 페르소나 텍스트
relationship = ""                  # 관계 정보
relationship_development = ""      # 관계 발전 정보

# 잡 정보
job_raw = ""                       # 직업 원문 (character_setup에서 사용)

# import_point (theme_templates.yaml에서 읽어들임, 중요포인트로 강조)
import_point = ""

# 행복도 (character_setup에서 초기화, story_gen에서 업데이트)
happiness = rand.randint(0,6) * 10

# 현재 에피소드 인덱스 (plot_gen / story_gen / full_episode_gen에서 사용)
current_episode_index = 0

# Other settings
love_value = 0
inc_flag = 0

# Heroine progression array (from persona.generate_ultimate_heroine_progression)
progression_array = []

# Episode gen flag (set when episode_gen is called from menu 4)
episode_gen_flag = False

# Progress tracking (1번 메뉴 theme_gen_auto 완료 시 저장)
plot_hash = ""                     # 1번 실행 시 생성되는 고유 hash code
theme_auto_complete_flag = False   # 1번(theme_gen_auto) 완료 플래그
progress_step = 0                  # 진행 단계: 0=초기, 1=플롯완료, 2=에피소드완료, 3=스토리완료

# RP/ANIMA 설정 (rp_extended.rp_call용)
muscle_enb = False
minion_enb = True
vulgarity_enb = True

# ANIMA 태그 배열 (에피소드 수만큼)
face_tag = ["" for _ in range(total_episodes)]
makeup_tag = ["" for _ in range(total_episodes)]
marks_tag = ["" for _ in range(total_episodes)]
body_tag = ["" for _ in range(total_episodes)]
bodystyle_tag = ["" for _ in range(total_episodes)]
exposure_tag = ["" for _ in range(total_episodes)]
p_exposure_tag = ["" for _ in range(total_episodes)]
background_tag = ["" for _ in range(total_episodes)]

# ANIMA 스칼라
body_shape = ""
current_level = 0
episode_num = 0

# ANIMA 표현/변화 배열 (llm_novel_illustration_gen.py에서 채움)
expression_arr = ["" for _ in range(total_episodes)]
changes_arr = ["" for _ in range(total_episodes)]
expression = ""

# ANIMA char_prompts_lines 배열 (init_anima_tags Step 10에서 채움, standing/simple 공통 사용)
char_prompts_lines_hair = ["" for _ in range(total_episodes)]      # She/He has {hair_color} hair, {hair_style}.
char_prompts_lines_body = ["" for _ in range(total_episodes)]      # She/He has a {body_shape} body.
char_prompts_lines_exposure = ["" for _ in range(total_episodes)]  # She/He is wearing {exposure_tag}.
char_prompts_lines_marks = ["" for _ in range(total_episodes)]     # She/He has {marks_tag} on her body.
char_prompts_lines_bodystyle = ["" for _ in range(total_episodes)] # She/He is {bodystyle_tag}.
char_prompts_lines_p_exposure = ["" for _ in range(total_episodes)] # She/He has {p_exposure_tag} visible.
char_prompts_lines_background = ["" for _ in range(total_episodes)] # She/He is in {bg} {time_of_day}.
char_prompts_lines_background_effect = ["" for _ in range(total_episodes)] # {background_tag} surround her/him.

# ANIMA 추가 데이터
sentences_anima = ["" for _ in range(total_episodes)]
location = ""
pose = ""
episode_step = 0
clothes_simple = ""
action_tag = []

# ANIMA 리뷰 배열 (init_anima_tags 전용)
review_stats = [[0]*7 for _ in range(total_episodes)]  # [M, L, A, O, I, S, D]
review_safety = ["" for _ in range(total_episodes)]    # safe | sensitive | nsfw | explicit
review_pose = ["" for _ in range(total_episodes)]      # LLM 추출 pose
review_location = ["" for _ in range(total_episodes)]  # LLM 추출 location
review_notes = ["" for _ in range(total_episodes)]     # LLM 리뷰 요약 JSON 문자열

# EP별 특별 작성 요청 ($가 포함된 가이드에서 추출)
special_writing_req = {}  

# EP별 타락 가이드 맵 (plot_gen에서 생성, full_episode_gen에서 친밀도 판별에 사용)
ep_corruption_guides_map = {}  # EP 번호 → {"protagonist": [...], "partner": [...]}

# OpenAPI
stream_enb = False
system_prompt = "당신은 청년용 살짝 엣찌한 러브코메디 라이트 노벨 작가입니다. 일본 클리쉐에 능숙하지만, 한국어로 소설을 씁니다"
system_prompt_anima = ""
messages_history = [ {"role": "system", "content": system_prompt} ]
