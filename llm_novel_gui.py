import curses
import textwrap
import re
import json
import os
import sys
import io
import logging
import config
import character_setup
import story_gen
import openAPI_control
import full_episode_gen
import plot_gen
import setup
import importlib
import anima_gen
from persona import generate_ultimate_heroine_progression

# GUI와 무관한 핵심 로직 함수 import (llm_novel_gui_func.py 참조)
import llm_novel_gui_func

# 9번 메뉴 자동 실행 로직 import (anima_gen_control.py 참조)
import anima_gen_control

# 로거 초기화 (파일 로그만)
llm_novel_gui_func.init_logger(log_file=os.path.join("log", "gui_func.log"))

# 1번 메뉴(플롯 생성) 전용 로거
_menu1_logger = logging.getLogger("menu1_flow")
_menu1_logger.setLevel(logging.DEBUG)
_menu1_log_handler = logging.FileHandler(os.path.join("log", "menu1_flow.log"), encoding="utf-8")
_menu1_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
_menu1_logger.addHandler(_menu1_log_handler)

# prompt_toolkit 관련 Import
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, Window, FloatContainer, Float
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import prompt

# config_extended는 config에 병합됨

from typing import List, Tuple

class LLMNovelGUI:
    """LLM 소설 생성기용 텍스트 GUI 클래스.
    
    curses 라이브러리를 사용하여 터미널 환경에서 작동하는 GUI 레이아웃을 제공합니다.
    텍스트 편집은 prompt_toolkit을 사용하여 한글 줄바꿈 및 다중 단축키를 완벽 지원합니다.
    """

    def __init__(self) -> None:
        """클래스 초기화 및 기본 설정."""
        try:
            character_setup.random_setup_all()
        except Exception as e:
            print(f"캐릭터 랜덤 초기화 중 오류 발생: {e}")

        try:
            theme_msg = story_gen.theme_gen()
            self.content_text = f"시스템 준비 완료.\n{theme_msg}"
        except Exception as e:
            self.content_text = f"테마 생성 중 오류 발생: {e}"

        # ANIMA 활성화 여부 확인
        self.anima_enb = bool(config.json_value.get("anima_enb", False))
        
        self.menu_items: List[str] = [
            "1. 플롯 생성 (Generate Plot)",
            "2. 소설 주인공 설정 (Protagonist Setup)",
            "3. 상대방 설정 (Opponent/Partner Setup)",
            "4. 에피소드 생성 (Generate Episode)",
            "5. 생성 및 보완 (Generate & Refine)",
            "6. 스토리 생성 (Generate Full Story)",
            "7. 설정 내보내기 (Export Config)",
            "8. 설정 복구 (Restore Config)",
            "9. 전체 자동 실행 (Auto-Run)",
        ]
        if self.anima_enb:
            self.menu_items.append("10. ANIMA STANDING/EVENT 생성")
        self.menu_items.append("Q/99. 프로그램 종료 (Quit)")
        self.current_selection: int = 0
        init_msg = "시스템 준비 완료. 메뉴에서 항목을 선택하세요."
        if config.selected_jinshugai_id is not None:
            init_msg += f"\n\n[진수개 ID 지정됨: {config.selected_jinshugai_id}]"
        self.content_text: str = init_msg
        
        self.focus = "MENU"
        self.content_selection = 0
        self.scroll_offset = 0
        
        self.episodes: List[str] = []
        self.current_episode_idx: int = 0
        self.episode_mode: bool = False
        self.reset_flag: bool = False  # C 키 누른 후 리셋 상태

        # episode_setup.json 로드
        self.episode_files = []
        self.current_file_index = 0
        episode_json_path = os.path.join("data", "episode_setup.json")
        try:
            with open(episode_json_path, "r", encoding="utf-8") as f:
                episode_data = json.load(f)
            self.episode_files = episode_data.get("files", [])
        except Exception as e:
            self.content_text = f"에피소드 설정 파일 로드 실패: {e}"

        # data/config_export.yaml이 존재하면 config 변수 업데이트
        config_export_loaded = self._load_config_export()

        # 여주인공 progression 생성 및 파싱
        self._generate_and_parse_progression()

        # debug 모드 체크 (plot.json의 debug 값)
        self.debug_mode = bool(config.json_value.get("debug", 0))

        # 진행 상태 로드 (progress/ 디렉토리에서)
        progress_state = llm_novel_gui_func.load_progress_state()
        if progress_state:
            loaded_hash = progress_state.get("plot_hash", "")
            loaded_step = progress_state.get("progress_step", 0)
            config.plot_hash = loaded_hash
            config.progress_step = loaded_step
            config.theme_auto_complete_flag = progress_state.get("theme_auto_complete", False)
            init_msg += f"\n\n[이전 진행 상태 로드]\n{llm_novel_gui_func.get_progress_summary()}"

        # 초기 content_text 설정
        if config_export_loaded:
            try:
                lv = getattr(config, 'love_value', 0)
                sheet, _ = character_setup.character_sheet(lv)
                plot_result = getattr(config, 'plot_result', "")
                if plot_result:
                    self.content_text = f"기존 설정을 복원했습니다.\n\n{plot_result}"
                else:
                    self.content_text = f"기존 설정을 복원했습니다.\n\n{sheet}"
            except Exception as e:
                self.content_text = f"기존 설정을 복원했습니다.\n\n{e}"
        else:
            self.content_text = init_msg if progress_state else "현재 설정이 없습니다."

        self.sheet_mapping = [
            ("이름", "name"), ("나이", "age"), ("성별", "sex"),
            ("성격/말투", "personality_real"), ("직업", "job"),
            ("직업 평가", "job_attribute"), ("인생 목표", "objective"),
            ("머리색", "hair_color"), ("헤어스타일", "hair_style"),
            ("눈 색깔", "eye_color"), ("피부 색깔", "skin_color"),
            ("얼굴 스타일 1", "face_style_1"), ("얼굴 스타일 2", "face_style_2"),
            ("액세서리", "acc"), ("가슴크기", "breasts_size"),
            ("엉덩이 크기", "hip_size"), ("몸매", "body_size"),
            ("성경험", "sex_count"), ("복장", "clothes"),
            ("혈연관계", "rel1"), ("기타 특징", "personality_text"),
            ("상대방 이름", "name2"), ("상대방 나이", "age2"),
            ("상대방 성별", "sex2"), ("상대방 직업", "job2"),
            ("상대방 외모", "appearance2"),
        ]

    # -------------------------------------------------------------------------
    # prompt_toolkit 연동용 편집 헬퍼 메서드
    # -------------------------------------------------------------------------
    def _prompt_toolkit_multiline(self, stdscr: curses.window, title: str, initial_text: str) -> str:
        """다중 라인 텍스트 에디터를 중앙 팝업 형태로 실행합니다."""
        curses.def_prog_mode()
        curses.endwin()

        result = None
        try:
            text_area = TextArea(
                text=initial_text,
                wrap_lines=True,
                focus_on_click=True
            )

            kb = KeyBindings()

            @kb.add('escape', 'escape')
            def save_and_exit(event):
                event.app.exit(result=text_area.text)

            @kb.add('c-c')
            def cancel_and_exit(event):
                event.app.exit(result=None)

            editor_frame = Frame(
                text_area, 
                title=f" {title} [ESC 두 번: 저장 및 종료 | Ctrl-C: 취소] "
            )

            root_container = FloatContainer(
                content=Window(),
                floats=[
                    Float(
                        content=editor_frame,
                        width=132,
                        height=40
                    )
                ]
            )

            app = Application(
                layout=Layout(root_container),
                key_bindings=kb,
                full_screen=True
            )

            result = app.run()
        finally:
            curses.reset_prog_mode()
            stdscr.clear()
            stdscr.refresh()

        return result

    def _edit_value(self, stdscr: curses.window, var_name: str, current_val: str) -> str:
        """단일 라인 텍스트 에디터를 실행합니다 (캐릭터 설정 속성 편집용)."""
        curses.def_prog_mode()
        curses.endwin()
        
        result = None
        try:
            print(f"\n[{var_name} 수정]")
            print("* 엔터(Enter): 저장 후 종료")
            print("* 컨트롤(Ctrl+C): 변경 취소\n")
            result = prompt(f"새로운 값: ", default=str(current_val))
        except KeyboardInterrupt:
            result = None
        finally:
            curses.reset_prog_mode()
            stdscr.clear()
            stdscr.refresh()

        return result

    # -------------------------------------------------------------------------
    # Config 저장/복구 관련 메서드 (llm_novel_gui_func 호출 래퍼)
    # -------------------------------------------------------------------------
    def _get_config_vars(self) -> dict:
        return llm_novel_gui_func.get_config_vars()

    def _save_config_state(self) -> None:
        llm_novel_gui_func.save_config_state()

    def _load_config_state(self) -> None:
        llm_novel_gui_func.load_config_state()

    def _reset_config_state(self) -> None:
        llm_novel_gui_func.reset_config_state()

    def _generate_and_parse_progression(self) -> str:
        return llm_novel_gui_func.generate_and_parse_progression()

    def _load_config_export(self) -> str:
        return llm_novel_gui_func.load_config_export()

    # -------------------------------------------------------------------------
    # GUI 그리기 및 유틸리티 메서드
    # -------------------------------------------------------------------------
    def _get_visual_width(self, text: str) -> int:
        width = 0
        for char in text:
            if ord(char) > 127: width += 2
            else: width += 1
        return width

    def _custom_wrap(self, text: str, max_width: int) -> List[str]:
        lines = []
        for paragraph in text.split('\n'):
            if not paragraph:
                lines.append("")
                continue
            current_line = []
            current_width = 0
            for char in paragraph:
                char_width = 2 if ord(char) > 127 else 1
                if current_width + char_width > max_width:
                    lines.append("".join(current_line))
                    current_line = [char]
                    current_width = char_width
                else:
                    current_line.append(char)
                    current_width += char_width
            if current_line:
                lines.append("".join(current_line))
        return lines

    def _draw_header(self, stdscr: curses.window) -> None:
        height, width = stdscr.getmaxyx()
        header_text = "=== LLM Short Novel Generator GUI ==="
        if width < len(header_text):
            header_text = header_text[:width-1]
        x = max(0, (width - len(header_text)) // 2)
        try:
            stdscr.attron(curses.A_BOLD | curses.A_REVERSE)
            stdscr.addstr(0, x, header_text)
            stdscr.attroff(curses.A_BOLD | curses.A_REVERSE)
        except curses.error: pass

    def _draw_menu(self, stdscr: curses.window) -> None:
        height, width = stdscr.getmaxyx()
        menu_width = 60
        if self.focus == "MENU":
            stdscr.attron(curses.A_BOLD)
            stdscr.addstr(2, 0, " [ MENU ] ", curses.A_BOLD)
            stdscr.attroff(curses.A_BOLD)
        else:
            stdscr.addstr(2, 0, " [ MENU ] ")
        stdscr.addstr(3, 0, "-" * menu_width)

        for idx, item in enumerate(self.menu_items):
            x = 0
            y = 4 + idx
            if idx == self.current_selection:
                stdscr.attron(curses.A_REVERSE)
                text = f"> {item}"
                stdscr.addstr(y, x, text[:menu_width])
                stdscr.attroff(curses.A_REVERSE)
            else:
                text = f"  {item}"
                stdscr.addstr(y, x, text[:menu_width])

    def _draw_content(self, stdscr: curses.window) -> None:
        height, width = stdscr.getmaxyx()
        menu_width = 60
        if width < (menu_width + 132): return
        
        try:
            start_x = menu_width
            if self.focus == "CONTENT":
                stdscr.attron(curses.A_BOLD)
                stdscr.addstr(2, start_x, "[ CONTENT / LOG ] ", curses.A_BOLD)
                stdscr.attroff(curses.A_BOLD)
            else:
                stdscr.addstr(2, start_x, "[ CONTENT / LOG ] ")
            
            start_y = 3
            text_x = start_x + 2
            max_allowed_width = min(132, width - text_x - 1)
            text_wrap_width = max_allowed_width - 2

            wrapped_lines = self._custom_wrap(self.content_text, text_wrap_width)
            max_display_lines = height - start_y - 2
            if max_display_lines < 1: return

            visible_lines = wrapped_lines[self.scroll_offset : self.scroll_offset + max_display_lines]
            
            for i, line in enumerate(visible_lines):
                current_line_idx = self.scroll_offset + i
                y = start_y + i
                
                safe_text = ""
                curr_v_width = 0
                for char in line:
                    char_w = 2 if ord(char) > 127 else 1
                    if curr_v_width + char_w > text_wrap_width: break
                    safe_text += char
                    curr_v_width += char_w
                
                prefix = "* " if (self.focus == "CONTENT" and current_line_idx == self.content_selection) else "  "
                display_text = f"{prefix}{safe_text}"
                
                final_output = ""
                final_v_width = 0
                for char in display_text:
                    char_w = 2 if ord(char) > 127 else 1
                    if final_v_width + char_w > max_allowed_width: break
                    final_output += char
                    final_v_width += char_w

                if self.focus == "CONTENT" and current_line_idx == self.content_selection:
                    stdscr.attron(curses.A_REVERSE)
                    stdscr.addstr(y, text_x, final_output)
                    stdscr.attroff(curses.A_REVERSE)
                else:
                    stdscr.addstr(y, text_x, final_output)
        except curses.error:
            pass

    def _split_episodes(self, text: str) -> List[str]:
        """## EPISODE N ## 패턴으로 텍스트를 에피소드 단위로 분리합니다."""
        return llm_novel_gui_func.split_episodes(text)

    def _update_auto_scroll(self, stdscr: curses.window) -> None:
        height, width = stdscr.getmaxyx()
        menu_width = 60
        text_x = menu_width + 2
        max_allowed_width = min(132, width - text_x - 1)
        text_wrap_width = max_allowed_width - 2
        wrapped_lines = self._custom_wrap(self.content_text, text_wrap_width)
        total_lines = len(wrapped_lines)
        start_y = 3
        max_display_lines = height - start_y - 2
        if total_lines > max_display_lines:
            self.scroll_offset = total_lines - max_display_lines
        else:
            self.scroll_offset = 0

    def _export_config_to_file(self, filepath: str) -> str:
        """config 변수를 config.py 정의 순서대로 내보냅니다."""
        return llm_novel_gui_func.export_config_to_file(filepath)

    def _restore_config_from_file(self, filepath: str) -> str:
        """지정된 파일에서 config 변수를 복구합니다."""
        return llm_novel_gui_func.restore_config_from_file(filepath)

    def _build_episode_full_track_table(self) -> str:
        """episode_full_track 상태를 테이블로 반환합니다."""
        return llm_novel_gui_func.build_episode_full_track_table()

    def _draw_status(self, stdscr: curses.window, episode_info: str = "") -> None:
        height, width = stdscr.getmaxyx()
        if episode_info:
            status_text = f" {episode_info} "
        else:
            status_text = " [Arrow]: Move/Select | [Enter]: Edit | [C]: Reset | [R]: Randomize"
            if self.debug_mode:
                status_text += " | [D]: Progression"
            status_text += " | [Q]: Quit "
            if self.episode_mode:
                status_text = " [N]: Next Episode | [P]: Prev Episode | [ESC]: Back to Menu | [Arrow]: Scroll "

            # Progress 정보 추가 (hash가 있으면)
            if config.plot_hash and not self.episode_mode:
                progress_info = llm_novel_gui_func.get_progress_summary()
                # status_text가 너무 길어지지 않도록 truncation
                if len(status_text) + len(progress_info) < width - 10:
                    status_text += f" | {progress_info}"

        try:
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(height - 1, 0, status_text.ljust(width - 1)[:width-1])
            stdscr.attroff(curses.A_REVERSE)
        except curses.error: pass

    def _show_menu_item_info(self) -> None:
        """현재 선택된 메뉴 항목에 대한 정보를 content_text에 표시합니다."""
        if self.current_selection == 0:
            # reset_flag가 True이면 초기화 메시지 유지
            if self.reset_flag:
                hash_info = f"Hash: {config.plot_hash}" if config.plot_hash else "Hash: 없음"
                self.content_text = (f"전체 설정이 초기화되었습니다.\n"
                                     f"세이브 하지 않으면 기존 설정이 유지됩니다.\n"
                                     f"{hash_info}\n"
                                     f"[Enter]를 눌러 새 플롯을 생성하세요.")
            else:
                plot_result = getattr(config, 'plot_result', "")
                if plot_result:
                    self.content_text = plot_result
                else:
                    self.content_text = "플롯이 아직 생성되지 않았습니다. [Enter]를 눌러 플롯을 생성하세요."
        elif self.current_selection == 1:
            if self.reset_flag:
                self.content_text = "아직 설정되어 있지 않습니다.\n1번 메뉴에서 [Enter]를 눌러 플롯을 생성하세요."
            else:
                try:
                    lv = getattr(config, 'love_value', 0)
                    sheet, _ = character_setup.character_sheet(lv)
                    self.content_text = sheet
                    # ComfyUI 프로세스 정리
                    import subprocess
                    subprocess.run(["pkill", "-f", "ComfyUI"], capture_output=True)
                except Exception as e:
                    self.content_text = f"캐릭터 시트를 불러오는 중 오류 발생:\n{e}"
        elif self.current_selection == 2:
            if self.reset_flag:
                self.content_text = "아직 설정되어 있지 않습니다.\n1번 메뉴에서 [Enter]를 눌러 플롯을 생성하세요."
            else:
                try:
                    self.content_text = character_setup.partner_sheet()
                except Exception as e:
                    self.content_text = f"상대방 시트를 불러오는 중 오류 발생:\n{e}"
        elif self.current_selection == 3:
            if self.reset_flag:
                self.content_text = "아직 설정되어 있지 않습니다.\n1번 메뉴에서 [Enter]를 눌러 플롯을 생성하세요."
            else:
                result_text = getattr(config, 'result_text', "")
                if result_text:
                    self.content_text = result_text
                else:
                    self.content_text = "에피소드가 아직 생성되지 않았습니다. [Enter]를 눌러 에피소드를 생성하세요."
        elif self.current_selection == 4:
            if self.reset_flag:
                self.content_text = "아직 설정되어 있지 않습니다.\n1번 메뉴에서 [Enter]를 눌러 플롯을 생성하세요."
            elif config.episode_content and any(ep.strip() for ep in config.episode_content):
                ep_idx = min(self.current_episode_idx, len(config.episode_content) - 1)
                if config.episode_content[ep_idx] and config.episode_content[ep_idx].strip():
                    self.content_text = f"## EPISODE {ep_idx + 1} ##\n\n{config.episode_content[ep_idx]}"
                else:
                    for i, ep in enumerate(config.episode_content):
                        if ep.strip():
                            self.content_text = f"## EPISODE {i + 1} ##\n\n{ep}"
                            self.current_episode_idx = i
                            break
            else:
                self.content_text = "생성 및 보완 항목입니다. [Enter]를 눌러 생성 및 보완을 실행하세요."
        elif self.current_selection == 5:
            if self.reset_flag:
                self.content_text = "아직 설정되어 있지 않습니다.\n1번 메뉴에서 [Enter]를 눌러 플롯을 생성하세요."
            else:
                self.content_text = self._build_episode_full_track_table()
        elif self.current_selection == 6:
            if self.reset_flag:
                self.content_text = "아직 설정되어 있지 않습니다.\n1번 메뉴에서 [Enter]를 눌러 플롯을 생성하세요."
            else:
                self.content_text = "스토리 내보내기 항목입니다. [Enter]를 눌러 result/에 episode_xx.md로 저장하세요."
        elif self.current_selection == 7:
            self.content_text = "설정 복구 항목입니다. [Enter]를 눌러 파일에서 설정을 복구하세요."
        elif self.current_selection == 8:
            self.content_text = "전체 자동 실행 항목입니다. [Enter]를 눌러 초기화 → 플롯 → 에피소드 → 스토리를 순차적으로 실행하세요."
        elif self.current_selection == 9:
            if self.anima_enb:
                self.content_text = "ANIMA STANDING/EVENT 생성 항목입니다. [Enter]를 눌러 이미지 생성을 시작하세요."
            else:
                self.content_text = "프로그램을 종료합니다."
        elif self.current_selection == 10:
            self.content_text = "프로그램을 종료합니다."
        self.content_selection = 0
        self.scroll_offset = 0

    def _get_variable_name_from_line(self, line_text: str) -> str:
        if ":" not in line_text: return ""
        label = line_text.split(":")[0].strip()
        for lbl, var in self.sheet_mapping:
            if lbl == label:
                return var
        return ""

    def _execute_generate_refine(self, stdscr: curses.window) -> None:
        total_eps = config.total_episodes
        last_info_state = {}
        received_text = ""
        
        def stream_callback(text, info_lines=None):
            nonlocal last_info_state, received_text
            if text: received_text = text
            if info_lines:
                current_ep = info_lines.get("current_episode")
                updated_count = info_lines.get("updated_count", 0)
                status = info_lines.get("status", "")
                new_state = (current_ep, updated_count, status)
                if new_state != last_info_state.get("display"):
                    last_info_state = {"display": new_state, "current_ep": current_ep, "updated_count": updated_count, "status": status}
                    progress_text = f"[생성 진행중] 에피소드 {current_ep}/{total_eps} | 업데이트: {updated_count}/{total_eps} | {status}"
                    if received_text: self.content_text = f"{progress_text}\n\n{received_text}"
                    else: self.content_text = progress_text
                    self._update_auto_scroll(stdscr)
                    stdscr.clear()
                    self._draw_header(stdscr)
                    self._draw_menu(stdscr)
                    self._draw_content(stdscr)
                    self._draw_status(stdscr, f"Generating... {updated_count}/{total_eps}")
                    stdscr.refresh()
        
        final_result = story_gen.episode_summary_gen(callback=stream_callback)
        self.episodes = self._split_episodes(final_result)
        
        self.episode_mode = True
        self.current_episode_idx = 0
        self.scroll_offset = 0
        
        if config.episode_content and config.episode_content[0]:
            self.content_text = f"## EPISODE 1 ##\n\n{config.episode_content[0]}"
        elif self.episodes:
            self.content_text = self.episodes[0]
        else:
            self.content_text = final_result
        
        stdscr.clear()
        self._draw_header(stdscr)
        self._draw_menu(stdscr)
        self._draw_content(stdscr)
        self._draw_status(stdscr)
        stdscr.refresh()
        
        while self.episode_mode:
            stdscr.clear()
            self._draw_header(stdscr)
            self._draw_menu(stdscr)
            self._draw_content(stdscr)
            
            current_ep_display = self.current_episode_idx + 1
            episode_info = f"Episode {current_ep_display}/{total_eps} | N:Next P:Prev E:Edit C:Reset&Regen ESC:Exit"
            self._draw_status(stdscr, episode_info)
            stdscr.refresh()
            
            key = stdscr.getch()
            
            if key in (ord('n'), ord('N')):
                if self.current_episode_idx < total_eps - 1:
                    self.current_episode_idx += 1
                    self.scroll_offset = 0
                    ep_idx = self.current_episode_idx
                    if config.episode_content and config.episode_content[ep_idx]:
                        self.content_text = f"## EPISODE {ep_idx + 1} ##\n\n{config.episode_content[ep_idx]}"
                    elif self.episodes and ep_idx < len(self.episodes):
                        self.content_text = self.episodes[ep_idx]
            elif key in (ord('p'), ord('P')):
                if self.current_episode_idx > 0:
                    self.current_episode_idx -= 1
                    self.scroll_offset = 0
                    ep_idx = self.current_episode_idx
                    if config.episode_content and config.episode_content[ep_idx]:
                        self.content_text = f"## EPISODE {ep_idx + 1} ##\n\n{config.episode_content[ep_idx]}"
                    elif self.episodes and ep_idx < len(self.episodes):
                        self.content_text = self.episodes[ep_idx]
            elif key == curses.KEY_UP:
                self.scroll_offset = max(0, self.scroll_offset - 1)
            elif key == curses.KEY_DOWN:
                wrapped = self._custom_wrap(self.content_text, 128)
                self.scroll_offset = min(len(wrapped) - 1, self.scroll_offset + 1)
            elif key == curses.KEY_PPAGE:  # Page Up
                height, _ = stdscr.getmaxyx()
                page_size = max(height - 6, 10)
                self.scroll_offset = max(0, self.scroll_offset - page_size)
            elif key == curses.KEY_NPAGE:  # Page Down
                wrapped = self._custom_wrap(self.content_text, 128)
                height, _ = stdscr.getmaxyx()
                page_size = max(height - 6, 10)
                self.scroll_offset = min(len(wrapped) - 1, self.scroll_offset + page_size)
            elif key in (ord('c'), ord('C')):
                # Reset episode_content, episode_track, episode_full_track
                for i in range(len(config.episode_content)):
                    config.episode_content[i] = ""
                    config.episode_track[i] = False
                    config.episode_full_content[i] = ""
                    config.episode_full_track[i] = False
                config.messages_history = []
                config.episode_gen_flag = False
                
                # Progress 디렉토리 파일 삭제
                llm_novel_gui_func.clear_progress_directory()
                
                # 직업 및 나이 재설정
                character_setup.job_and_age_init()
                
                # 에피소드 모드 종료하고 1번 플롯 생성 메뉴로 이동
                self.episode_mode = False
                self.current_selection = 0
                self.reset_flag = True
                self.scroll_offset = 0
                self._show_menu_item_info()
                break
            elif key in (ord('e'), ord('E')):
                ep_num = self.current_episode_idx + 1
                current_content = config.episode_content[self.current_episode_idx] if self.current_episode_idx < len(config.episode_content) else ""
                clean_content = current_content.replace('\r\n', '\n').replace('\r', '\n')
                new_content = self._prompt_toolkit_multiline(stdscr, title=f"Edit Episode {ep_num}", initial_text=clean_content)
                if new_content is not None:
                    config.episode_content[self.current_episode_idx] = new_content
                    self.content_text = f"## EPISODE {ep_num} ##\n\n{new_content}"
            elif key == 27:
                self.episode_mode = False
                self.content_text = final_result
                self.scroll_offset = 0
                break
            elif key in (ord('q'), ord('Q')):
                self.episode_mode = False
                break
        
        self.content_selection = 0
        self.scroll_offset = 0

    def _auto_run(self) -> None:
        """curses 없이 콘솔에서 전체 자동 실행 (run_auto_sequence 호출)."""
        import logging
        import datetime

        # 명령줄 inc_flag 값 재적용 (config_export.yaml 로드 시 덮어씌워짐)
        inc_flag_set = False
        for i, arg in enumerate(sys.argv):
            if arg in ("-inc_flag", "--inc_flag") and i + 1 < len(sys.argv):
                try:
                    config.inc_flag = int(sys.argv[i + 1])
                    inc_flag_set = True
                except ValueError:
                    pass
                break
        if not inc_flag_set:
            config.inc_flag = 0

        # 로깅 설정
        log_dir = os.path.join("log")
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"auto_run_{timestamp}.log")
        
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8"),
                logging.StreamHandler(sys.stdout)
            ]
        )
        logger = logging.getLogger("auto_run")
        logger.info("=" * 60)
        logger.info("전체 자동 실행 시작")
        logger.info(f"로그 파일: {log_file}")
        logger.info("=" * 60)

        anima_enb = config.json_value.get("anima_enb", "no")
        anima_enb = anima_enb in ("yes", True, "1")

        def console_callback(step: str, status: str, content_text: str):
            print(f"\n[{status}]\n{content_text}")

        try:
            result = anima_gen_control.run_auto_sequence(
                episode_files=self.episode_files,
                current_file_index=self.current_file_index,
                anima_enb=anima_enb,
                callback=console_callback,
            )
            self.current_file_index = result["current_file_index"]

            if result["success"]:
                logger.info("=" * 60)
                logger.info("전체 자동 실행 완료")
                logger.info("=" * 60)
                print(f"\n{result['content_text']}")
            else:
                logger.error(f"자동 실행 중 오류 발생")
                print(f"\n{result['content_text']}")

        except Exception as e:
            logger.error(f"자동 실행 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()

    def run(self, stdscr: curses.window) -> None:
        curses.curs_set(0)
        
        _, width = stdscr.getmaxyx()
        if width < 192:
            stdscr.clear()
            warning_msg = "경고: 터미널 창 너비가 너무 좁습니다.\n최소 192글자 이상의 너비가 필요합니다."
            try:
                stdscr.addstr(0, 0, warning_msg)
                stdscr.refresh()
                stdscr.getch()
            except curses.error: pass
            return

        stdscr.clear()

        while True:
            stdscr.clear()
            self._draw_header(stdscr)
            self._draw_menu(stdscr)
            self._draw_content(stdscr)
            self._draw_status(stdscr)
            stdscr.refresh()

            key = stdscr.getch()

            # [포커스 이동] RIGHT: CONTENT 영역, LEFT: MENU 영역
            if key == curses.KEY_RIGHT: self.focus = "CONTENT"
            elif key == curses.KEY_LEFT: self.focus = "MENU"
            
            # [MENU 모드] 메뉴 항목 선택 및 단축키 처리
            elif self.focus == "MENU":
                if key == curses.KEY_UP:
                    # [메이 이동] 메뉴 항목 위로 이동
                    self.current_selection = (self.current_selection - 1) % len(self.menu_items)
                    self._show_menu_item_info()
                elif key == curses.KEY_DOWN:
                    # [메뉴 이동] 메뉴 항목 아래로 이동
                    self.current_selection = (self.current_selection + 1) % len(self.menu_items)
                    self._show_menu_item_info()
                elif key in (ord('q'), ord('Q')):
                    # [Q] 프로그램 종료
                    break
                elif key in (ord('c'), ord('C')):
                    # [C] 전체 설정 초기화: config 리로드 + 캐릭터 랜덤 + 테마 재생성
                    saved_jinshugai_id = config.selected_jinshugai_id
                    saved_inc_flag = getattr(config, 'inc_flag', 0)
                    self._reset_config_state()
                    config.selected_jinshugai_id = saved_jinshugai_id
                    config.inc_flag = saved_inc_flag

                    # Progress 디렉토리 파일 삭제 + 초기화 + 새 hash code 생성
                    deleted_count = llm_novel_gui_func.clear_progress_directory()
                    llm_novel_gui_func.reset_progress()
                    new_hash = llm_novel_gui_func.generate_plot_hash()

                    character_setup.random_setup_all()
                    story_gen.theme_gen()
                    lv = getattr(config, 'love_value', 0)
                    sheet, _ = character_setup.character_sheet(lv)
                    prog_msg = self._generate_and_parse_progression()
                    config.episode_gen_flag = False
                    progress_msg = f"progress/ 디렉토리에서 {deleted_count}개 파일 삭제됨" if deleted_count > 0 else ""
                    self.content_text = f"전체 설정이 초기화되었습니다.\n세이브 하지 않으면 기존 설정이 유지됩니다.\n{progress_msg}\nHash: {new_hash}\n{prog_msg}\n"
                    self.reset_flag = True
                    self.content_selection = 0
                    self.scroll_offset = 0
                elif key in (ord('r'), ord('R')):
                    # [R] 캐릭터만 랜덤 재설정 (테마 유지)
                    try:
                        character_setup.random_setup_all()
                        # plot_result 업데이트
                        plot_text = story_gen.generate_plot()
                        prog_msg = self._generate_and_parse_progression()
                        if self.episode_files:
                            current_file = self.episode_files[self.current_file_index]
                            description = current_file.get("description", "")
                            self.content_text = f"스토리: {description}\n\n{plot_text}\n\n{prog_msg}"
                        else:
                            self.content_text = f"{plot_text}\n\n{prog_msg}"
                        self.content_selection = 0
                        self.scroll_offset = 0
                    except Exception as e:
                        self.content_text = f"랜덤 재설정 중 오류 발생:\n{e}"
                elif key in (ord('d'), ord('D')):
                    # [D] 디버그 모드: progression_array 표시 (debug=1일 때만 작동)
                    if self.debug_mode:
                        prog = config.progression_array
                        if prog:
                            lines = ["=== 여주인공 Progression ===\n"]
                            for i, item in enumerate(prog, 1):
                                lines.append(f"Ep.{i:02d}: {item}")
                            self.content_text = "\n".join(lines)
                        else:
                            self.content_text = "Progression 데이터가 없습니다. 먼저 C/R/1번 메뉴를 실행하세요."
                        self.content_selection = 0
                        self.scroll_offset = 0
                elif key in (ord('g'), ord('G')):
                    # [G] Generate & Refine 실행 (에피소드 요약 생성)
                    self._execute_generate_refine(stdscr)
                elif key == 10:  # [Enter] 메뉴 실행
                    if self.current_selection == 7:
                        # [8번] 설정 복구
                        break
                    if self.current_selection == 0:
                        # [1번] 플롯 생성: theme_gen + job_and_age_init + generate_plot
                        try:
                            # theme_auto가 yes인 경우 theme_gen_auto.py 사용
                            use_theme_auto = config.json_value.get("theme_auto", "no") == "yes"
                            _menu1_logger.info("=" * 50)
                            _menu1_logger.info("[1번 메뉴] 플롯 생성 시작")
                            _menu1_logger.info(f"theme_auto={config.json_value.get('theme_auto', 'no')}, archtype_enb={config.json_value.get('archtype_enb', 'no')}")
                            _menu1_logger.info(f"현재 config.job={config.job}, config.age={config.age}, config.name={config.name}")
                            debug_msg = f"[DEBUG] theme_auto: {config.json_value.get('theme_auto', 'no')}\n"
                            
                            if use_theme_auto:
                                debug_msg += "[DEBUG] theme_gen_auto 모드 활성화\n"
                                debug_msg += f"[DEBUG] 호출 전 config.job={config.job}, config.age={config.age}\n"

                                # hash가 없으면 생성
                                if not config.plot_hash:
                                    llm_novel_gui_func.generate_plot_hash()

                                # 오른쪽 윈도우에 준비 메시지 표시
                                self.content_text = (f"[1번] 테마 생성 준비중입니다...\n"
                                                     f"Hash: {config.plot_hash}\n\n"
                                                     f"API 호출 중 (약 1-2분 소요)\n"
                                                     f"잠시 기다려주세요...")
                                self.scroll_offset = 0
                                stdscr.clear()
                                self._draw_header(stdscr)
                                self._draw_menu(stdscr)
                                self._draw_content(stdscr)
                                self._draw_status(stdscr, "테마 생성 준비중...")
                                stdscr.refresh()

                                import theme_gen_auto
                                # cmd_job/cmd_job2 적용을 위해 job_and_age_init 호출
                                character_setup.job_and_age_init()
                                story_info = f"성인용 러브코메디 라이트 노벨"
                                theme_result = theme_gen_auto.theme_gen_auto(
                                    story_info,
                                    num_episodes=config.total_episodes,
                                    log_fn=llm_novel_gui_func.logger.info
                                )
                                # theme_gen_auto 결과로 config 업데이트
                                config.theme_jinshugai = theme_result["jinshugai"]
                                config.theme_events = theme_result.get("events")
                                plot_text = config.plot_result if hasattr(config, 'plot_result') else ""
                                debug_msg += f"[DEBUG] theme_gen_auto 완료 - job={config.job}, age={config.age}\n"
                                debug_msg += f"[DEBUG] theme_jinshugai: {config.theme_jinshugai}\n"
                            else:
                                debug_msg += f"[DEBUG] 호출 전 config.job={config.job}\n"
                                story_gen.theme_gen()
                                character_setup.job_and_age_init()
                                # body_dic 초기화 + archetype_setup 적용
                                character_setup.character_init(config.sex, config.json_value)
                                character_setup.archetype_setup(config.json_value)
                                character_setup.personality_init(config.json_value)
                                debug_msg += f"[DEBUG] archetype_setup 완료 - hair_color={config.hair_color}, personality={config.personality_real}\n"
                                plot_text = story_gen.generate_plot()
                                
                                # theme_agent가 yes인 경우 테마 업데이트
                                use_theme_agent = config.json_value.get("theme_agent", "no") == "yes"
                                debug_msg += f"[DEBUG] theme_agent: {config.json_value.get('theme_agent', 'no')}\n"
                                if use_theme_agent:
                                    import theme_gen as theme_gen_module
                                    story_info = f"""
스토리: {plot_text.split('\n')[0] if '\n' in plot_text else plot_text[:100]}
테마: {getattr(config, 'plot', '')}
주인공({config.name}, {getattr(config, 'age', '')}세)과 상대방({config.name2}, {getattr(config, 'age2', '')}세)의 이야기입니다.
관계 설정 및 직업({getattr(config, 'job', '')} / {getattr(config, 'job2', '')})을 바탕으로 스토리가 전개됩니다.
"""
                                    theme_result = theme_gen_module.generate_updated_theme(
                                        story_info,
                                        num_episodes=config.total_episodes,
                                        log_fn=llm_novel_gui_func.logger.info
                                    )
                                    config.plot = theme_result["theme"]
                                    config.theme_breeds = theme_result["breeds"]
                                    config.theme_jinshugai = theme_result["jinshugai"]
                                    config.theme_events = theme_result["events"]
                                    config.plot_result = plot_text + f"\n\n[업데이트된 테마]\n{theme_result['theme']}"
                                    debug_msg += f"[DEBUG] 테마 업데이트 완료\n\n{theme_result['theme']}\n"
                                    plot_text += f"\n\n[업데이트된 테마]\n{theme_result['theme']}"
                            
                            # config_export.yaml 저장 (1번 플롯 생성 후)
                            export_path = os.path.join("data", "config_export.yaml")
                            self._export_config_to_file(export_path)
                            llm_novel_gui_func.logger.info(f"config_export.yaml 저장 완료 (1번 플롯 생성 후): {export_path}")

                            # theme_auto 모드이면 progress 저장
                            if use_theme_auto:
                                # 1번 완료 처리 (flag + progress 저장 + theme 변수 YAML 저장)
                                llm_novel_gui_func.complete_theme_auto()
                                debug_msg += f"\n[Progress] Hash: {config.plot_hash} | 1번 완료 저장됨\n"
                                debug_msg += f"progress/theme_{config.plot_hash}.yaml\n"
                                debug_msg += f"progress/progress_{config.plot_hash}.json\n"

                            prog_msg = self._generate_and_parse_progression()
                            _menu1_logger.info(f"최종 config.job={config.job}, config.age={config.age}, config.name={config.name}")
                            _menu1_logger.info(f"config.job2={config.job2}, config.age2={config.age2}, config.name2={config.name2}")
                            _menu1_logger.info(f"config.hair_color={config.hair_color}, config.personality_real={config.personality_real}")
                            _menu1_logger.info("[1번 메뉴] 플롯 생성 완료")
                            _menu1_logger.info("=" * 50)
                            if self.episode_files:
                                current_file = self.episode_files[self.current_file_index]
                                description = current_file.get("description", "")
                                self.content_text = f"스토리: {description}\n\n{plot_text}\n\n{debug_msg}\n{prog_msg}"
                            else:
                                self.content_text = f"{plot_text}\n\n{debug_msg}\n{prog_msg}"
                            self.reset_flag = False
                            self.content_selection = 0
                            self.scroll_offset = 0
                        except Exception as e:
                            self.content_text = f"플롯 생성 중 오류 발생:\n{e}"
                    elif self.current_selection == 1:
                        # [2번] 소설 주인공 설정: character_sheet 표시
                        try:
                            lv = getattr(config, 'love_value', 0)
                            sheet, _ = character_setup.character_sheet(lv)
                            self.content_text = sheet
                            self.content_selection = 0
                            self.scroll_offset = 0
                        except Exception as e:
                            self.content_text = f"캐릭터 시트를 불러오는 중 오류 발생:\n{e}"
                    elif self.current_selection == 2:
                        # [3번] 상대방 설정: partner_sheet 표시
                        try:
                            self.content_text = character_setup.partner_sheet()
                            self.content_selection = 0
                            self.scroll_offset = 0
                        except Exception as e:
                            self.content_text = f"상대방 시트를 불러오는 중 오류 발생:\n{e}"
                    elif self.current_selection == 3:
                        # [4번] 에피소드 생성: progression + episode_gen
                        try:
                            # 여주인공 progression 재초기화
                            prog_msg = self._generate_and_parse_progression()

                            # extended 모드 체크
                            use_extended = config.json_value.get("extended", "no") == "yes"

                            if use_extended:
                                # [extended 모드] plot_gen 호출 후 episode parsing
                                import random as rand
                                # jinshugai_templates가 있으면 첫 번째 템플릿 ID를 사용 (불일치 방지)
                                jinshugai_list = getattr(config, 'theme_jinshugai', None)
                                if jinshugai_list and len(jinshugai_list) > 0:
                                    template_id = jinshugai_list[0].get('id', rand.randint(1, 10))
                                else:
                                    template_id = rand.randint(1, 10)
                                theme_msg = getattr(config, 'plot', '')
                                total_eps = config.total_episodes
                                template_name = plot_gen.TEMPLATES[template_id]['name']

                                # 호출 전 왼쪽 윈도우에 메시지 표시
                                self.content_text = f"[Extended] plot_gen 호출 중...\n\n템플릿: {template_id}. {template_name}\n에피소드: {total_eps}개\n테마: {theme_msg}\n\nAPI 응답을 기다리는 중 (약 1-2분 소요)"
                                self.content_selection = 0
                                self.scroll_offset = 0

                                # callback: 각 API 호출 단계에서 status 바 업데이트
                                def plot_callback(status_msg: str):
                                    self.content_text = f"[Extended] plot_gen 호출 중...\n\n템플릿: {template_id}. {template_name}\n에피소드: {total_eps}개\n테마: {theme_msg}\n\n{status_msg}"
                                    stdscr.clear()
                                    self._draw_header(stdscr)
                                    self._draw_menu(stdscr)
                                    self._draw_content(stdscr)
                                    self._draw_status(stdscr, status_msg)
                                    stdscr.refresh()

                                # stdout 캡처 (plot_gen의 print 출력 방지)
                                old_stdout = sys.stdout
                                sys.stdout = io.StringIO()
                                try:
                                    # plot_gen 호출
                                    plot_result = plot_gen.plot_gen_extended(
                                        template_id=template_id,
                                        total_episodes=total_eps,
                                        theme_msg=theme_msg,
                                        breeds_data=getattr(config, 'theme_breeds', None),
                                        jinshugai_templates=getattr(config, 'theme_jinshugai', None),
                                        progression_events=getattr(config, 'theme_events', None),
                                        callback=plot_callback
                                    )
                                finally:
                                    sys.stdout = old_stdout

                                # 결과 파싱: ##EP{n}, EP{n}, **EP{n** 등 다양한 헤더 형식 지원
                                ep_header_pattern = re.compile(r'(?:##\s*)?(?:\*\*)?EP(?:ISODE)?\s*(\d+)(?:\*\*)?\s*[:#]?\s*(.*)', re.IGNORECASE)
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
                                        rest = match.group(2).strip().rstrip('*').rstrip('#').strip()
                                        current_ep_lines = [rest] if rest else []
                                    elif current_ep_num is not None and stripped:
                                        current_ep_lines.append(stripped)
                                if current_ep_num is not None and current_ep_lines:
                                    episodes_parsed_dict[current_ep_num] = "\n".join(current_ep_lines).strip()
                                
                                # 순서대로 리스트로 변환
                                episodes_parsed = []
                                for i in range(1, total_eps + 1):
                                    episodes_parsed.append(episodes_parsed_dict.get(i, ""))

                                # config.episode_content에 정확히 인가
                                for i in range(len(config.episode_content)):
                                    if i < len(episodes_parsed):
                                        config.episode_content[i] = episodes_parsed[i]
                                    else:
                                        config.episode_content[i] = ""

                                # config.result_text 설정 (표시용)
                                result_lines = ["=== 생성된 에피소드 리스트 (Extended) ==="]
                                result_lines.append(f"템플릿: {plot_gen.TEMPLATES[template_id]['name']}")
                                result_lines.append(f"총 {len(episodes_parsed)}개 에피소드 생성")
                                result_lines.append("")
                                for idx, ep in enumerate(episodes_parsed):
                                    result_lines.append(f"Episode {idx + 1}: {ep}")
                                result_lines.append("")
                                result_lines.append("[RIGHT] → CONTENT 포커스 → [DOWN] 스크롤로 전체 확인")
                                config.result_text = "\n".join(result_lines)
                                config.episode_gen_flag = True

                                # 에피소드 내용과 캐릭터 시트를 progress 디렉토리에 저장
                                plot_hash = getattr(config, 'plot_hash', '')
                                if plot_hash:
                                    saved_ep_files = llm_novel_gui_func.save_episodes_and_sheets_to_progress(plot_hash)
                                    if saved_ep_files:
                                        result_lines.append("")
                                        result_lines.append(f"[저장] progress/ep1~ep{len(saved_ep_files)}_{{plot_hash}}.txt")
                                        config.result_text = "\n".join(result_lines)

                                self.content_text = config.result_text + f"\n\n{prog_msg}"
                            else:
                                ep_gen = story_gen.episode_gen

                                # episode_files 리스트를 순환하며 에피소드 재생성
                                if self.episode_files:
                                    self.current_file_index = (self.current_file_index + 1) % len(self.episode_files)
                                    current_file = self.episode_files[self.current_file_index]
                                    filename = current_file.get("filename", "")
                                    description = current_file.get("description", "")
                                    if filename:
                                        self.content_text = f"[에피소드 파일: {description} ({filename})]\n\n" + ep_gen(filename_override=filename)
                                    else:
                                        self.content_text = ep_gen()
                                else:
                                    self.content_text = ep_gen()
                                self.content_text += f"\n\n{prog_msg}"
                            self.content_selection = 0
                            self.scroll_offset = 0
                        except Exception as e:
                            self.content_text = f"에피소드 생성 중 오류 발생:\n{e}"
                    elif self.current_selection == 4:
                        try:
                            total_eps = config.total_episodes
                            if not config.episode_gen_flag:
                                self.content_text = "에피소드가 생성되지 않았습니다. 먼저 4번 메뉴에서 에피소드를 생성하세요."
                                self.content_selection = 0
                                self.scroll_offset = 0
                            else:
                                has_content = config.episode_content and any(ep.strip() for ep in config.episode_content)

                                if not has_content:
                                    last_info_state = {}
                                    received_text = ""
                                    
                                    def stream_callback(text, info_lines=None):
                                        nonlocal last_info_state, received_text
                                        if text: received_text = text
                                        if info_lines:
                                            current_ep = info_lines.get("current_episode")
                                            updated_count = info_lines.get("updated_count", 0)
                                            status = info_lines.get("status", "")
                                            new_state = (current_ep, updated_count, status)
                                            if new_state != last_info_state.get("display"):
                                                last_info_state = {"display": new_state, "current_ep": current_ep, "updated_count": updated_count, "status": status}
                                                progress_text = f"[생성 진행중] 에피소드 {current_ep}/{total_eps} | 업데이트: {updated_count}/{total_eps} | {status}"
                                                if received_text: self.content_text = f"{progress_text}\n\n{received_text}"
                                                else: self.content_text = progress_text
                                                self._update_auto_scroll(stdscr)
                                                stdscr.clear()
                                                self._draw_header(stdscr)
                                                self._draw_menu(stdscr)
                                                self._draw_content(stdscr)
                                                self._draw_status(stdscr, f"Generating... {updated_count}/{total_eps}")
                                                stdscr.refresh()
                                    
                                    final_result = story_gen.episode_summary_gen(callback=stream_callback)
                                    self.episodes = self._split_episodes(final_result)
                                    
                                    if config.episode_content and config.episode_content[0]:
                                        self.content_text = f"## EPISODE 1 ##\n\n{config.episode_content[0]}"
                                    elif self.episodes:
                                        self.content_text = self.episodes[0]
                                    else:
                                        self.content_text = final_result
                                else:
                                    self.episodes = [ep for ep in config.episode_content if ep.strip()]
                                    self.content_text = f"## EPISODE 1 ##\n\n{config.episode_content[0]}"
                            
                            # [에피소드 모드 진입] 에피소드 탐색/편집 모드
                            self.episode_mode = True
                            self.current_episode_idx = 0
                            self.scroll_offset = 0
                            
                            stdscr.clear()
                            self._draw_header(stdscr)
                            self._draw_menu(stdscr)
                            self._draw_content(stdscr)
                            self._draw_status(stdscr)
                            stdscr.refresh()
                            
                            # [에피소드 모드 루프] 에피소드 탐색 및 편집
                            while self.episode_mode:
                                stdscr.clear()
                                self._draw_header(stdscr)
                                self._draw_menu(stdscr)
                                self._draw_content(stdscr)
                                
                                current_ep_display = self.current_episode_idx + 1
                                episode_info = f"Episode {current_ep_display}/{total_eps} | N:Next P:Prev ESC:Exit"
                                self._draw_status(stdscr, episode_info)
                                stdscr.refresh()
                                
                                key = stdscr.getch()
                                
                                if key in (ord('n'), ord('N')):
                                    # [N] 다음 에피소드로 이동
                                    if self.current_episode_idx < total_eps - 1:
                                        self.current_episode_idx += 1
                                        self.scroll_offset = 0
                                        ep_idx = self.current_episode_idx
                                        if config.episode_content and config.episode_content[ep_idx]:
                                            self.content_text = f"## EPISODE {ep_idx + 1} ##\n\n{config.episode_content[ep_idx]}"
                                        elif self.episodes and ep_idx < len(self.episodes):
                                            self.content_text = self.episodes[ep_idx]
                                elif key in (ord('p'), ord('P')):
                                    # [P] 이전 에피소드로 이동
                                    if self.current_episode_idx > 0:
                                        self.current_episode_idx -= 1
                                        self.scroll_offset = 0
                                        ep_idx = self.current_episode_idx
                                        if config.episode_content and config.episode_content[ep_idx]:
                                            self.content_text = f"## EPISODE {ep_idx + 1} ##\n\n{config.episode_content[ep_idx]}"
                                        elif self.episodes and ep_idx < len(self.episodes):
                                            self.content_text = self.episodes[ep_idx]
                                elif key == curses.KEY_UP:
                                    # [UP] 스크롤 위로
                                    self.scroll_offset = max(0, self.scroll_offset - 1)
                                elif key == curses.KEY_DOWN:
                                    # [DOWN] 스크롤 아래로 (마지막 줄까지 스크롤 가능)
                                    wrapped = self._custom_wrap(self.content_text, 128)
                                    self.scroll_offset = min(len(wrapped) - 1, self.scroll_offset + 1)
                                elif key == curses.KEY_PPAGE:  # Page Up
                                    height, _ = stdscr.getmaxyx()
                                    page_size = max(height - 6, 10)
                                    self.scroll_offset = max(0, self.scroll_offset - page_size)
                                elif key == curses.KEY_NPAGE:  # Page Down
                                    wrapped = self._custom_wrap(self.content_text, 128)
                                    height, _ = stdscr.getmaxyx()
                                    page_size = max(height - 6, 10)
                                    self.scroll_offset = min(len(wrapped) - 1, self.scroll_offset + page_size)
                                elif key == 27:
                                    # [ESC] 에피소드 모드 종료, 메인 결과 화면으로 복귀
                                    self.episode_mode = False
                                    self.content_text = final_result
                                    self.scroll_offset = 0
                                    break
                                elif key in (ord('q'), ord('Q')):
                                    # [Q] 에피소드 모드 종료 (결과 화면 없이)
                                    self.episode_mode = False
                                    break
                            
                            self.content_selection = 0
                            self.scroll_offset = 0
                        except Exception as e:
                            self.content_text = f"에피소드 보완 중 오류 발생:\n{e}"
                    elif self.current_selection == 4:
                        # [5번] 생성 및 보완: episode_summary_gen 호출 → 에피소드 모드 진입
                        try:
                            total_eps = config.total_episodes
                            if not config.episode_gen_flag:
                                self.content_text = "에피소드가 생성되지 않았습니다. 먼저 4번 메뉴에서 에피소드를 생성하세요."
                                self.content_selection = 0
                                self.scroll_offset = 0
                            else:
                                # 에피소드 요약이 이미 있는 경우 스킵
                                has_content = config.episode_content and any(ep.strip() for ep in config.episode_content)
                                if not has_content:
                                    last_info_state = {}
                                    received_text = ""
                                    
                                    def stream_callback(text, info_lines=None):
                                        nonlocal last_info_state, received_text
                                        if text: received_text = text
                                        if info_lines:
                                            current_ep = info_lines.get("current_episode")
                                            updated_count = info_lines.get("updated_count", 0)
                                            status = info_lines.get("status", "")
                                            new_state = (current_ep, updated_count, status)
                                            if new_state != last_info_state.get("display"):
                                                last_info_state = {"display": new_state, "current_ep": current_ep, "updated_count": updated_count, "status": status}
                                                progress_text = f"[생성 진행중] 에피소드 {current_ep}/{total_eps} | 업데이트: {updated_count}/{total_eps} | {status}"
                                                if received_text: self.content_text = f"{progress_text}\n\n{received_text}"
                                                else: self.content_text = progress_text
                                                self._update_auto_scroll(stdscr)
                                                stdscr.clear()
                                                self._draw_header(stdscr)
                                                self._draw_menu(stdscr)
                                                self._draw_content(stdscr)
                                                self._draw_status(stdscr, f"Generating... {updated_count}/{total_eps}")
                                                stdscr.refresh()
                                    
                                    final_result = story_gen.episode_summary_gen(callback=stream_callback)
                                    self.episodes = self._split_episodes(final_result)
                                    
                                    if config.episode_content and config.episode_content[0]:
                                        self.content_text = f"## EPISODE 1 ##\n\n{config.episode_content[0]}"
                                    elif self.episodes:
                                        self.content_text = self.episodes[0]
                                    else:
                                        self.content_text = final_result
                                else:
                                    self.episodes = [ep for ep in config.episode_content if ep.strip()]
                                    self.content_text = f"## EPISODE 1 ##\n\n{config.episode_content[0]}"
                            
                            # [에피소드 모드 진입]
                            self.episode_mode = True
                            self.current_episode_idx = 0
                            self.scroll_offset = 0
                            
                            stdscr.clear()
                            self._draw_header(stdscr)
                            self._draw_menu(stdscr)
                            self._draw_content(stdscr)
                            self._draw_status(stdscr)
                            stdscr.refresh()
                            
                            # [에피소드 모드 루프]
                            while self.episode_mode:
                                stdscr.clear()
                                self._draw_header(stdscr)
                                self._draw_menu(stdscr)
                                self._draw_content(stdscr)
                                
                                current_ep_display = self.current_episode_idx + 1
                                episode_info = f"Episode {current_ep_display}/{total_eps} | N:Next P:Prev Enter/E:Edit C:Reset&Regen ESC:Exit"
                                self._draw_status(stdscr, episode_info)
                                stdscr.refresh()
                                
                                key = stdscr.getch()
                                
                                if key in (ord('n'), ord('N')):
                                    # [N] 다음 에피소드로 이동
                                    if self.current_episode_idx < total_eps - 1:
                                        self.current_episode_idx += 1
                                        self.scroll_offset = 0
                                        ep_idx = self.current_episode_idx
                                        if config.episode_content and config.episode_content[ep_idx]:
                                            self.content_text = f"## EPISODE {ep_idx + 1} ##\n\n{config.episode_content[ep_idx]}"
                                        elif self.episodes and ep_idx < len(self.episodes):
                                            self.content_text = self.episodes[ep_idx]
                                elif key in (ord('p'), ord('P')):
                                    # [P] 이전 에피소드로 이동
                                    if self.current_episode_idx > 0:
                                        self.current_episode_idx -= 1
                                        self.scroll_offset = 0
                                        ep_idx = self.current_episode_idx
                                        if config.episode_content and config.episode_content[ep_idx]:
                                            self.content_text = f"## EPISODE {ep_idx + 1} ##\n\n{config.episode_content[ep_idx]}"
                                        elif self.episodes and ep_idx < len(self.episodes):
                                            self.content_text = self.episodes[ep_idx]
                                elif key == curses.KEY_UP:
                                    # [UP] 스크롤 위로
                                    self.scroll_offset = max(0, self.scroll_offset - 1)
                                elif key == curses.KEY_DOWN:
                                    # [DOWN] 스크롤 아래로 (마지막 줄까지 스크롤 가능)
                                    wrapped = self._custom_wrap(self.content_text, 128)
                                    self.scroll_offset = min(len(wrapped) - 1, self.scroll_offset + 1)
                                elif key == curses.KEY_PPAGE:  # Page Up
                                    height, _ = stdscr.getmaxyx()
                                    page_size = max(height - 6, 10)
                                    self.scroll_offset = max(0, self.scroll_offset - page_size)
                                elif key == curses.KEY_NPAGE:  # Page Down
                                    wrapped = self._custom_wrap(self.content_text, 128)
                                    height, _ = stdscr.getmaxyx()
                                    page_size = max(height - 6, 10)
                                    self.scroll_offset = min(len(wrapped) - 1, self.scroll_offset + page_size)
                                elif key in (ord('c'), ord('C')):
                                    # [C] 에피소드 초기화 + 재생성
                                    for i in range(len(config.episode_content)):
                                        config.episode_content[i] = ""
                                        config.episode_track[i] = False
                                        config.episode_full_content[i] = ""
                                        config.episode_full_track[i] = False
                                    config.messages_history = []
                                    config.episode_gen_flag = False
                                    
                                    # Progress 디렉토리 파일 삭제
                                    llm_novel_gui_func.clear_progress_directory()
                                    
                                    # 직업 및 나이 재설정
                                    character_setup.job_and_age_init()
                                    
                                    # 에피소드 모드 종료하고 1번 플롯 생성 메뉴로 이동
                                    self.episode_mode = False
                                    self.current_selection = 0
                                    self.reset_flag = True
                                    self.scroll_offset = 0
                                    self._show_menu_item_info()
                                    break
                                elif key in (ord('e'), ord('E'), 10):
                                    # [E 또는 Enter] 현재 에피소드 편집
                                    ep_num = self.current_episode_idx + 1
                                    current_content = config.episode_content[self.current_episode_idx] if self.current_episode_idx < len(config.episode_content) else ""
                                    clean_content = current_content.replace('\r\n', '\n').replace('\r', '\n')
                                    new_content = self._prompt_toolkit_multiline(stdscr, title=f"Edit Episode {ep_num}", initial_text=clean_content)
                                    if new_content is not None:
                                        config.episode_content[self.current_episode_idx] = new_content
                                        self.content_text = f"## EPISODE {ep_num} ##\n\n{new_content}"
                                elif key == 27:
                                    # [ESC] 에피소드 모드 종료
                                    self.episode_mode = False
                                    self.content_text = final_result
                                    self.scroll_offset = 0
                                    break
                                elif key in (ord('q'), ord('Q')):
                                    # [Q] 에피소드 모드 종료
                                    self.episode_mode = False
                                    break
                            
                            self.content_selection = 0
                            self.scroll_offset = 0
                        except Exception as e:
                            self.content_text = f"에피소드 보완 중 오류 발생:\n{e}"
                    elif self.current_selection == 5:
                        # [6번] 스토리 생성: 에피소드 번호 입력 후 full_episode_gen 호출
                        curses.def_prog_mode()
                        curses.endwin()
                        try:
                            print("[스토리 생성]")
                            print("에피소드 번호를 입력하세요 (0 = 전체 생성)")
                            print(f"에피소드 범위: 1~{config.total_episodes}")
                            print("* 컨트롤(Ctrl+C): 취소\n")
                            user_input = prompt("에피소드 번호 (0=전체): ", default="0")
                            ep_num_input = int(user_input.strip())
                        except KeyboardInterrupt:
                            self.content_text = "스토리 생성 취소됨."
                            curses.reset_prog_mode()
                            stdscr.clear()
                            stdscr.refresh()
                            self.content_selection = 0
                            self.scroll_offset = 0
                            continue
                        except Exception as e:
                            self.content_text = f"입력 오류:\n{e}"
                            curses.reset_prog_mode()
                            stdscr.clear()
                            stdscr.refresh()
                            self.content_selection = 0
                            self.scroll_offset = 0
                            continue
                        finally:
                            curses.reset_prog_mode()
                        
                        try:
                            total_eps = config.total_episodes
                            last_info_state = {}
                            received_text = ""
                            
                            def stream_callback(text, info_lines=None):
                                nonlocal last_info_state, received_text
                                if text: received_text = text
                                if info_lines:
                                    current_ep = info_lines.get("current_episode")
                                    updated_count = info_lines.get("updated_count", 0)
                                    status = info_lines.get("status", "")
                                    new_state = (current_ep, updated_count, status)
                                    if new_state != last_info_state.get("display"):
                                        last_info_state = {"display": new_state, "current_ep": current_ep, "updated_count": updated_count, "status": status}
                                        progress_text = f"[스토리 생성중] 에피소드 {current_ep}/{total_eps} | 업데이트: {updated_count}/{total_eps} | {status}"
                                        if received_text: self.content_text = f"{progress_text}\n\n{received_text}"
                                        else: self.content_text = progress_text
                                        self._update_auto_scroll(stdscr)
                                        stdscr.clear()
                                        self._draw_header(stdscr)
                                        self._draw_menu(stdscr)
                                        self._draw_content(stdscr)
                                        self._draw_status(stdscr, f"Generating Story... {updated_count}/{total_eps}")
                                        stdscr.refresh()
                            
                            ep_num_call = ep_num_input if 1 <= ep_num_input <= config.total_episodes else 0
                            final_result = full_episode_gen.full_episode_gen(ep_num=ep_num_call, callback=stream_callback)
                            self.episodes = self._split_episodes(final_result)
                            
                            self.episode_mode = True
                            self.current_episode_idx = 0
                            self.scroll_offset = 0
                            
                            # 완료 메시지
                            if ep_num_call == 0:
                                completion_msg = f"에피소드 1~{config.total_episodes} 작성이 완료되었습니다."
                            else:
                                completion_msg = f"에피소드 {ep_num_call} 작성이 완료되었습니다."
                            
                            track_table = self._build_episode_full_track_table()
                            
                            #if config.episode_content and config.episode_content[0]:
                            #    self.content_text = f"{completion_msg}\n\n{track_table}\n\n## EPISODE 1 ##\n\n{config.episode_content[0]}"
                            #elif self.episodes:
                            #    self.content_text = f"{completion_msg}\n\n{track_table}\n\n{self.episodes[0]}"
                            #else:
                            #    self.content_text = f"{completion_msg}\n\n{track_table}\n\n{final_result}"
                            
                            stdscr.clear()
                            self._draw_header(stdscr)
                            self._draw_menu(stdscr)
                            self._draw_content(stdscr)
                            self._draw_status(stdscr)
                            stdscr.refresh()
                            
                            while self.episode_mode:
                                stdscr.clear()
                                self._draw_header(stdscr)
                                self._draw_menu(stdscr)
                                self._draw_content(stdscr)
                                
                                current_ep_display = self.current_episode_idx + 1
                                episode_info = f"Episode {current_ep_display}/{total_eps} | N:Next P:Prev E:Edit C:Reset&Regen ESC:Exit"
                                self._draw_status(stdscr, episode_info)
                                stdscr.refresh()
                                
                                key = stdscr.getch()
                                
                                if key in (ord('n'), ord('N')):
                                    if self.current_episode_idx < total_eps - 1:
                                        self.current_episode_idx += 1
                                        self.scroll_offset = 0
                                        ep_idx = self.current_episode_idx
                                        if config.episode_content and config.episode_content[ep_idx]:
                                            self.content_text = f"## EPISODE {ep_idx + 1} ##\n\n{config.episode_content[ep_idx]}"
                                        elif self.episodes and ep_idx < len(self.episodes):
                                            self.content_text = self.episodes[ep_idx]
                                elif key in (ord('p'), ord('P')):
                                    if self.current_episode_idx > 0:
                                        self.current_episode_idx -= 1
                                        self.scroll_offset = 0
                                        ep_idx = self.current_episode_idx
                                        if config.episode_content and config.episode_content[ep_idx]:
                                            self.content_text = f"## EPISODE {ep_idx + 1} ##\n\n{config.episode_content[ep_idx]}"
                                        elif self.episodes and ep_idx < len(self.episodes):
                                            self.content_text = self.episodes[ep_idx]
                                elif key == curses.KEY_UP:
                                    self.scroll_offset = max(0, self.scroll_offset - 1)
                                elif key == curses.KEY_DOWN:
                                    wrapped = self._custom_wrap(self.content_text, 128)
                                    self.scroll_offset = min(len(wrapped) - 1, self.scroll_offset + 1)
                                elif key == curses.KEY_PPAGE:  # Page Up
                                    height, _ = stdscr.getmaxyx()
                                    page_size = max(height - 6, 10)
                                    self.scroll_offset = max(0, self.scroll_offset - page_size)
                                elif key == curses.KEY_NPAGE:  # Page Down
                                    wrapped = self._custom_wrap(self.content_text, 128)
                                    height, _ = stdscr.getmaxyx()
                                    page_size = max(height - 6, 10)
                                    self.scroll_offset = min(len(wrapped) - 1, self.scroll_offset + page_size)
                                elif key in (ord('c'), ord('C')):
                                    # Reset episode_content, episode_track, episode_full_track
                                    for i in range(len(config.episode_content)):
                                        config.episode_content[i] = ""
                                        config.episode_track[i] = False
                                        config.episode_full_content[i] = ""
                                        config.episode_full_track[i] = False
                                    config.messages_history = []
                                    config.episode_gen_flag = False
                                    
                                    # Progress 디렉토리 파일 삭제
                                    llm_novel_gui_func.clear_progress_directory()
                                    
                                    # 직업 및 나이 재설정
                                    character_setup.job_and_age_init()
                                    
                                    # 에피소드 모드 종료하고 1번 플롯 생성 메뉴로 이동
                                    self.episode_mode = False
                                    self.current_selection = 0
                                    self.reset_flag = True
                                    self.scroll_offset = 0
                                    self._show_menu_item_info()
                                    break
                                elif key in (ord('e'), ord('E')):
                                    ep_num = self.current_episode_idx + 1
                                    current_content = config.episode_content[self.current_episode_idx] if self.current_episode_idx < len(config.episode_content) else ""
                                    clean_content = current_content.replace('\r\n', '\n').replace('\r', '\n')
                                    new_content = self._prompt_toolkit_multiline(stdscr, title=f"Edit Episode {ep_num}", initial_text=clean_content)
                                    if new_content is not None:
                                        config.episode_content[self.current_episode_idx] = new_content
                                        self.content_text = f"## EPISODE {ep_num} ##\n\n{new_content}"
                                elif key == 27:
                                    self.episode_mode = False
                                    self.content_text = final_result
                                    self.scroll_offset = 0
                                    break
                                elif key in (ord('q'), ord('Q')):
                                    self.episode_mode = False
                                    break
                            
                            self.content_selection = 0
                            self.scroll_offset = 0
                        except Exception as e:
                            self.content_text = f"스토리 생성 중 오류 발생:\n{e}"
                    elif self.current_selection == 6:
                        # 7번: 설정 내보내기 (Export Config)
                        try:
                            export_path = os.path.join("data", "config_export.yaml")
                            result = self._export_config_to_file(export_path)
                            self.content_text = result
                        except Exception as e:
                            self.content_text = f"설정 내보내기 중 오류 발생:\n{e}"
                        self.content_selection = 0
                        self.scroll_offset = 0
                    elif self.current_selection == 7:
                        # 8번: 설정 복구 (Restore Config)
                        curses.def_prog_mode()
                        curses.endwin()
                        try:
                            print("[설정 복구]")
                            print("복구할 파일 경로를 입력하세요.")
                            print("* 엔터(Enter): 복구 | * 컨트롤(Ctrl+C): 취소\n")
                            filepath = prompt("파일 경로: ", default="data/config_export.yaml")
                            result = self._restore_config_from_file(filepath)
                            self.content_text = result
                        except KeyboardInterrupt:
                            self.content_text = "복구 취소됨."
                        finally:
                            curses.reset_prog_mode()
                            stdscr.clear()
                            stdscr.refresh()
                        self.content_selection = 0
                        self.scroll_offset = 0
                    elif self.current_selection == 8:
                        # 9번: 전체 자동 실행 (anima_gen_control.run_auto_sequence 호출)
                        # 명령줄 inc_flag 값 재적용
                        inc_flag_set = False
                        for i, arg in enumerate(sys.argv):
                            if arg in ("-inc_flag", "--inc_flag") and i + 1 < len(sys.argv):
                                try:
                                    config.inc_flag = int(sys.argv[i + 1])
                                    inc_flag_set = True
                                except ValueError:
                                    pass
                                break
                        if not inc_flag_set:
                            config.inc_flag = 0

                        def _auto_cb(step: str, status: str, content: str):
                            self.content_text = content
                            self._update_auto_scroll(stdscr)
                            stdscr.clear()
                            self._draw_header(stdscr)
                            self._draw_menu(stdscr)
                            self._draw_content(stdscr)
                            self._draw_status(stdscr, status)
                            stdscr.refresh()

                        result = anima_gen_control.run_auto_sequence(
                            episode_files=self.episode_files,
                            current_file_index=self.current_file_index,
                            anima_enb=self.anima_enb,
                            callback=_auto_cb,
                        )
                        self.current_file_index = result["current_file_index"]
                        self.content_text = result["content_text"]
                        self.content_selection = 0
                        self.scroll_offset = 0
                    elif self.current_selection == 9:
                        # 10번: ANIMA STANDING/EVENT 생성
                        # 에피소드 번호 입력 (6번과 동일한 방식)
                        curses.def_prog_mode()
                        curses.endwin()
                        try:
                            print("[ANIMA STANDING/EVENT 생성]")
                            print("에피소드 번호를 입력하세요 (0 = 전체 생성)")
                            print(f"에피소드 범위: 1~{config.total_episodes}")
                            print("* 컨트롤(Ctrl+C): 취소\n")
                            user_input = prompt("에피소드 번호 (0=전체): ", default="0")
                            ep_num_input = int(user_input.strip())
                        except KeyboardInterrupt:
                            self.content_text = "ANIMA 생성 취소됨."
                            curses.reset_prog_mode()
                            stdscr.clear()
                            stdscr.refresh()
                            self.content_selection = 0
                            self.scroll_offset = 0
                            continue
                        except Exception as e:
                            self.content_text = f"입력 오류:\n{e}"
                            curses.reset_prog_mode()
                            stdscr.clear()
                            stdscr.refresh()
                            self.content_selection = 0
                            self.scroll_offset = 0
                            continue
                        finally:
                            curses.reset_prog_mode()

                        try:
                            total_eps = config.total_episodes
                            ep_num_call = ep_num_input if 1 <= ep_num_input <= config.total_episodes else 0

                            # OpenAI 클라이언트 생성
                            client = openAPI_control.get_openai_client()

                            # ANIMA 초기화 (포즈 딕셔너리, 아티스트 태그)
                            anima_gen.anima_setup(config.json_value)

                            # 불필요한 llama, ComfyUI 프로세스 종료 후 ComfyUI 재실행, ANIMA 생성 시작
                            import subprocess
                            subprocess.run(["pkill", "llama"], capture_output=True)

                            # 처리할 에피소드 목록
                            if ep_num_call == 0:
                                episodes_to_process = list(range(total_eps))
                            else:
                                episodes_to_process = [ep_num_call - 1]

                            results = []
                            for ep_idx in episodes_to_process:
                                ep_num = ep_idx + 1
                                self.content_text = f"[ANIMA STANDING/EVENT]\n\n에피소드 {ep_num} 처리 중..."
                                stdscr.clear()
                                self._draw_header(stdscr)
                                self._draw_menu(stdscr)
                                self._draw_content(stdscr)
                                self._draw_status(stdscr, f"ANIMA 생성 중 (EP{ep_num})...")
                                stdscr.refresh()

                                # 1. init_anima_tags 호출 (누락 필드 검사 포함)
                                init_result = anima_gen.init_anima_tags(ep_idx, client, config.json_value)
                                if isinstance(init_result, dict):
                                    status = init_result["status"]
                                    if status == "missing":
                                        missing = ", ".join(init_result["fields"])
                                        results.append(f"EP{ep_num}: 필수 값 누락 ({missing})")
                                        continue
                                    elif status == "no_episode":
                                        results.append(f"EP{ep_num}: 에피소드 내용 없음")
                                        continue
                                    elif status == "error":
                                        results.append(f"EP{ep_num}: rp_call 오류 ({init_result.get('message', '')})")
                                        continue
                                    elif status == "ok":
                                        # 디버깅용: 설정된 값 표시
                                        fields = init_result["fields"]
                                        debug_str = "\n  ".join(f"{k}={v}" for k, v in fields.items())
                                        results.append(f"EP{ep_num}: OK\n  {debug_str}")
                                    else:
                                        results.append(f"EP{ep_num}: 알 수 없는 상태 ({status})")
                                        continue
                                else:
                                    results.append(f"EP{ep_num}: init_anima_tags 실패")
                                    continue

                                # 2. anima_gen_standing 호출
                                standing_result = anima_gen.anima_gen_standing(
                                    episode=ep_idx,
                                    messages_history_rp=config.messages_history,
                                    json_value=config.json_value,
                                    client_rp=client,
                                    sex=config.sex,
                                    name=config.name,
                                    name2=config.name2,
                                )

                                # 3. anima_gen_simple 호출 (기-승-전-결 4회)
                                for step_num in range(1, 5):
                                    config.episode_step = f"{ep_num}_{step_num}"
                                    simple_result = anima_gen.anima_gen_simple(
                                        episode=ep_idx,
                                        messages_history_rp=config.messages_history,
                                        json_value=config.json_value,
                                        client_rp=client,
                                        sex=config.sex,
                                        name=config.name,
                                        name2=config.name2,
                                    )

                                results.append(f"EP{ep_num}: 완료")

                            # 완료 메시지
                            if ep_num_call == 0:
                                self.content_text = f"[ANIMA STANDING/EVENT]\n\n에피소드 1~{total_eps} ANIMA 이미지 생성이 완료되었습니다.\n\n" + "\n".join(results)
                            else:
                                self.content_text = f"[ANIMA STANDING/EVENT]\n\n에피소드 {ep_num_call} ANIMA 이미지 생성이 완료되었습니다.\n\n" + "\n".join(results)
                            
                            self._draw_header(stdscr)
                            self._draw_menu(stdscr)
                            self._draw_content(stdscr)
                            self._draw_status(stdscr, "ANIMA 생성 완료")
                            stdscr.refresh()
                        except Exception as e:
                            import traceback
                            error_msg = traceback.format_exc()
                            self.content_text = f"ANIMA 생성 중 오류 발생:\n{error_msg}"
                        self.content_selection = 0
                        self.scroll_offset = 0
                    else:
                        self.content_text = f"{self.menu_items[self.current_selection]} 항목이 선택되었습니다."

            elif self.focus == "CONTENT":
                wrapped_lines = self._custom_wrap(self.content_text, 128)
                height, _ = stdscr.getmaxyx()
                page_size = max(height - 6, 10)  # 한 페이지당 스크롤 줄 수
                if key == curses.KEY_UP:
                    self.content_selection = max(0, self.content_selection - 1)
                    if self.content_selection < self.scroll_offset:
                        self.scroll_offset = self.content_selection
                elif key == curses.KEY_DOWN:
                    self.content_selection = min(len(wrapped_lines) - 1, self.content_selection + 1)
                    max_visible = height - 5
                    if self.content_selection >= self.scroll_offset + max_visible:
                        self.scroll_offset += 1
                elif key == curses.KEY_PPAGE:  # Page Up
                    self.content_selection = max(0, self.content_selection - page_size)
                    self.scroll_offset = max(0, self.scroll_offset - page_size)
                elif key == curses.KEY_NPAGE:  # Page Down
                    self.content_selection = min(len(wrapped_lines) - 1, self.content_selection + page_size)
                    max_visible = height - 5
                    if self.content_selection >= self.scroll_offset + max_visible:
                        self.scroll_offset = min(len(wrapped_lines) - max_visible, self.content_selection - max_visible + 1)
                elif key == 27:
                    self.focus = "MENU"
                elif key in (ord('g'), ord('G')):
                    self._execute_generate_refine(stdscr)
                elif key in (ord('n'), ord('N')):
                    if self.current_selection == 4 and config.episode_content:
                        total_eps = config.total_episodes
                        if self.current_episode_idx < total_eps - 1:
                            self.current_episode_idx += 1
                            self.scroll_offset = 0
                            ep_idx = self.current_episode_idx
                            if config.episode_content[ep_idx] and config.episode_content[ep_idx].strip():
                                self.content_text = f"## EPISODE {ep_idx + 1} ##\n\n{config.episode_content[ep_idx]}"
                                lines = self.content_text.split('\n')
                elif key in (ord('p'), ord('P')):
                    if self.current_selection == 4 and config.episode_content:
                        if self.current_episode_idx > 0:
                            self.current_episode_idx -= 1
                            self.scroll_offset = 0
                            ep_idx = self.current_episode_idx
                            if config.episode_content[ep_idx] and config.episode_content[ep_idx].strip():
                                self.content_text = f"## EPISODE {ep_idx + 1} ##\n\n{config.episode_content[ep_idx]}"
                                lines = self.content_text.split('\n')
                elif key == 10:
                    lines = self.content_text.split('\n')
                    if self.content_selection < len(lines):
                        line_text = lines[self.content_selection]
                        var_name = self._get_variable_name_from_line(line_text)
                        
                        if var_name:
                            current_val = str(getattr(config, var_name, ""))
                            new_val = self._edit_value(stdscr, var_name, current_val)
                            
                            if new_val is not None:
                                target_module = config
                                if config.json_value["extended"] == "yes":
                                    target_module = config
                                
                                try:
                                    if new_val.isdigit():
                                        setattr(target_module, var_name, int(new_val))
                                    else:
                                        setattr(target_module, var_name, new_val)
                                except Exception:
                                    setattr(target_module, var_name, new_val)
                                
                                lv = getattr(config, 'love_value', 0)
                                sheet, _ = character_setup.character_sheet(lv)
                                self.content_text = sheet
                                self.content_selection = min(self.content_selection, len(self.content_text.split('\n')) - 1)

def main() -> None:
    setup.default_setup()

    # -id 인자 파싱 (jinshugai_id)
    cmd_jinshugai_id = None
    for i, arg in enumerate(sys.argv):
        if arg in ("-id", "--id") and i + 1 < len(sys.argv):
            try:
                cmd_jinshugai_id = int(sys.argv[i + 1])
            except ValueError:
                pass
            break

    # -inc_flag 인자 파싱
    cmd_inc_flag = None
    for i, arg in enumerate(sys.argv):
        if arg in ("-inc_flag", "--inc_flag") and i + 1 < len(sys.argv):
            try:
                cmd_inc_flag = int(sys.argv[i + 1])
            except ValueError:
                pass
            break

    # -job 인자 파싱 (주인공 직업 강제 설정)
    cmd_job = None
    for i, arg in enumerate(sys.argv):
        if arg in ("-job", "--job") and i + 1 < len(sys.argv):
            try:
                cmd_job = int(sys.argv[i + 1])
            except ValueError:
                pass
            break

    # -job2 인자 파싱 (상대방 직업 강제 설정)
    cmd_job2 = None
    for i, arg in enumerate(sys.argv):
        if arg in ("-job2", "--job2") and i + 1 < len(sys.argv):
            try:
                cmd_job2 = int(sys.argv[i + 1])
            except ValueError:
                pass
            break

    auto_mode = len(sys.argv) > 1 and sys.argv[1] in ("auto", "--auto", "-a")

    # config_export.yaml 로드로 덮어씌워진 명령행 인자 재적용
    if cmd_jinshugai_id is not None:
        config.selected_jinshugai_id = cmd_jinshugai_id
    if cmd_inc_flag is not None:
        config.inc_flag = cmd_inc_flag
    else:
        config.inc_flag = 0  # 인자 없으면 기본값 0 강제 적용
    if cmd_job is not None:
        config.cmd_job = cmd_job
    if cmd_job2 is not None:
        config.cmd_job2 = cmd_job2

    gui = LLMNovelGUI()

    if auto_mode:
        gui._auto_run()
    else:
        curses.wrapper(gui.run)

if __name__ == "__main__":
    main()
