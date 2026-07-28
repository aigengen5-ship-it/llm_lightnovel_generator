"""
anima_gen_control.py
====================
9번 메뉴 (전체 자동 실행) + ANIMA 생성 제어 로직을 분리한 모듈.

llm_novel_gui_func.py의 run_auto_sequence를 재-export하여
역호환을 유지합니다.

Actual logic: llm_novel_gui_func.run_auto_sequence
"""

from llm_novel_gui_func import run_auto_sequence

__all__ = ["run_auto_sequence"]
