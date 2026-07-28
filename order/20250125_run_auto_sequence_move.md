# 2025-01-25 run_auto_sequence 함수 이동 작업

## 버그 발견
10번 메뉴 실행 시 `run_auto_sequence` 함수가 `anima_gen_control.py`에 있어서 구조가 복잡함.

## 수정 내용

### 1. llm_novel_gui_func.py
- `run_auto_sequence` 함수 추가 (anima_gen_control.py에서 이동)
- 필요한 import 문 추가:
  - `import random as rand`
  - `import story_gen`
  - `import full_episode_gen`
  - `import plot_gen`
  - `import anima_gen`
  - `import openAPI_control`

### 2. anima_gen_control.py
- `llm_novel_gui_func.run_auto_sequence`를 재-export하는 슬림한 래퍼 모듈로 변경
- 역호환 유지 (기존 import 문 그대로 작동)

### 3. llm_novel_gui_textual.py
- `anima_gen_control` import 제거
- `llm_novel_gui_func.run_auto_sequence` 사용으로 변경
- `anima_enb` 변수 주석 해제

## 파일 백업
- `anima_gen_control.py.bak`
- `llm_novel_gui_func.py.bak`
- `llm_novel_gui_textual.py.bak`

## 수정 원칙
GUI 코드 분리 원칙 준수:
- 그리기 및 입력 처리 → `llm_novel_gui_textual.py`
- 데이터 처리, 파일 I/O, 파싱, 테이블 빌드, 자동 실행 로직 → `llm_novel_gui_func.py`
