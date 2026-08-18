import os
import sys
import config
import character_setup
import story_gen
import plot_gen
import importlib
import random as rand
import io
import datetime
import subprocess
from persona import generate_ultimate_heroine_progression
import llm_novel_gui_func
import theme_gen_auto
import anima_gen
import openAPI_control

from textual import work
from textual.app import App, ComposeResult
from textual.screen import ModalScreen
from textual.containers import Horizontal, Vertical
from textual.widgets import OptionList, Static, TextArea, Label, Button, Input
from textual.widgets.option_list import Option

# 로거 초기화
llm_novel_gui_func.init_logger(log_file=os.path.join("log", "gui_func_textual.log"))


# =============================================================================
# 1. 종료 확인 모달 팝업 스크린
# =============================================================================
class QuitConfirmScreen(ModalScreen[bool]):
    """종료 확인 팝업 스크린"""
    CSS = """
    QuitConfirmScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    
    #quit-container {
        width: 50;
        height: 9;
        padding: 1 2;
        border: round #ffff00;
        background: $surface;
    }
    
    #quit-message {
        width: 100%;
        height: 3;
        content-align: center middle;
        color: white;
    }
    
    #quit-buttons {
        width: 100%;
        height: 3;
        align-horizontal: center;
    }
    
    Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="quit-container"):
            yield Static("프로그램을 종료하시겠습니까?\n\n[b]y[/b]: Yes  [b]n[/b]: No  [b]Esc[/b]: Cancel", id="quit-message")
            with Horizontal(id="quit-buttons"):
                yield Button("Yes", id="quit-yes", variant="error")
                yield Button("No", id="quit-no", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "quit-yes")

    def on_key(self, event) -> None:
        if event.key == "y":
            self.dismiss(True)
        elif event.key in ("n", "escape"):
            self.dismiss(False)


# =============================================================================
# 3. 스토리 생성 에피소드 선택 모달
# =============================================================================
class EpisodeSelectScreen(ModalScreen[int]):
    """스토리 생성 시 에피소드 범위 선택 모달 (int: ep_num 반환)"""
    CSS = """
    EpisodeSelectScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    
    #ep-container {
        width: 62;
        height: 17;
        padding: 1 2;
        border: round #00ff00;
        background: $surface;
    }
    
    #ep-title {
        width: 100%;
        height: 2;
        content-align: center middle;
        color: #00ff00;
        text-style: bold;
    }
    
    #ep-status {
        width: 100%;
        height: 4;
        padding: 0 1;
        color: white;
    }
    
    #ep-input-row {
        width: 100%;
        height: 3;
        align-horizontal: center;
    }
    
    #ep-input-label {
        width: 12;
        height: 3;
        content-align: right middle;
        color: #ffff00;
    }
    
    #ep-input {
        width: 15;
        height: 3; /* 테두리 포함 3줄 높이 부여 (입력 텍스트 표시 해결) */
        border: round #00bfff;
        background: $surface;
        color: #ffffff;
    }
    
    #ep-input:focus {
        border: round #00ff00;
        background: #002200;
        color: #00ff00;
    }
    
    #ep-input-hint {
        width: 22;
        height: 3;
        content-align: left middle;
        color: #888888;
    }
    
    #ep-buttons {
        width: 100%;
        height: 3;
        align-horizontal: center;
    }
    
    #ep-help {
        width: 100%;
        height: 1;
        content-align: center middle;
        color: #888888;
    }
    
    Button {
        margin: 0 1;
    }
    """

    def __init__(self, total_episodes: int, episode_full_track: list) -> None:
        super().__init__()
        self.total_episodes = total_episodes
        self.episode_full_track = episode_full_track

    def compose(self) -> ComposeResult:
        # 생성된 에피소드 상태 표시
        status_lines = []
        for i in range(self.total_episodes):
            ep_num = i + 1
            status = "✅" if self.episode_full_track[i] else "⬜"
            status_lines.append(f"{status} EP {ep_num}")
            if (i + 1) % 4 == 0 and i < self.total_episodes - 1:
                status_lines.append("")  # 4개마다 줄바꿈

        completed = sum(1 for t in self.episode_full_track if t)
        incomplete = self.total_episodes - completed
        status_text = f"생성 완료: {completed}개 | 미생성: {incomplete}개\n\n" + "  ".join(status_lines)

        with Vertical(id="ep-container"):
            yield Static("📖 스토리 생성 - 에피소드 범위 선택", id="ep-title")
            yield Static(status_text, id="ep-status")
            with Horizontal(id="ep-input-row"):
                yield Static("EP 번호:", id="ep-input-label")
                yield Input(placeholder=f"1~{self.total_episodes}", id="ep-input")
                yield Static(f"(숫자 입력 후 Enter)", id="ep-input-hint")
            with Horizontal(id="ep-buttons"):
                yield Button("전체 재생성", id="ep-all", variant="primary")
                yield Button("이어서 생성", id="ep-continue", variant="default")
                yield Button("선택 EP 생성", id="ep-single", variant="success")
                yield Button("취소", id="ep-cancel", variant="error")
            yield Static("[1]: 전체 | [2]: 이어서 | [3]: 선택 EP | [Esc]: 취소", id="ep-help")

    def on_mount(self) -> None:
        self.query_one("#ep-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ep-all":
            self.dismiss(0)
        elif event.button.id == "ep-continue":
            self.dismiss(-1)
        elif event.button.id == "ep-single":
            value = self.query_one("#ep-input", Input).value.strip()
            if value and value.isdigit():
                ep_num = int(value)
                if 1 <= ep_num <= self.total_episodes:
                    self.dismiss(ep_num)
        elif event.button.id == "ep-cancel":
            self.dismiss(None)

    def on_key(self, event) -> None:
        input_widget = self.query_one("#ep-input", Input)
        if input_widget.has_focus:
            if event.key == "escape":
                self.dismiss(None)
            return

        if event.key == "1":
            self.dismiss(0)
        elif event.key == "2":
            self.dismiss(-1)
        elif event.key in ("3", "i"):
            input_widget.focus()
        elif event.key == "escape":
            self.dismiss(None)

    def on_input_changed(self, event: Input.Changed) -> None:
        # 깔끔한 숫자 전용 필터링
        digits = "".join(c for c in event.value if c.isdigit())
        if digits and int(digits) > self.total_episodes:
            digits = str(self.total_episodes)
        if event.value != digits:
            event.input.value = digits

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value and value.isdigit():
            ep_num = int(value)
            if 1 <= ep_num <= self.total_episodes:
                self.dismiss(ep_num)


# =============================================================================
# 4. ANIMA 생성 에피소드 선택 모달
# =============================================================================
class AnimaEpisodeSelectScreen(ModalScreen[int]):
    """ANIMA 생성 시 에피소드 선택 모달 (int: ep_num 반환, 0=전체)"""
    CSS = """
    AnimaEpisodeSelectScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    
    #anima-container {
        width: 58;
        height: 14;
        padding: 1 2;
        border: round #ff00ff;
        background: $surface;
    }
    
    #anima-title {
        width: 100%;
        height: 2;
        content-align: center middle;
        color: #ff00ff;
        text-style: bold;
    }
    
    #anima-info {
        width: 100%;
        height: 3;
        padding: 0 1;
        color: white;
    }
    
    #anima-input-row {
        width: 100%;
        height: 3;
        align-horizontal: center;
    }
    
    #anima-input-label {
        width: 12;
        height: 3;
        content-align: right middle;
        color: #ffff00;
    }
    
    #anima-input {
        width: 15;
        height: 3; /* 테두리 포함 3줄 높이 부여 (입력 텍스트 표시 해결) */
        border: round #ff00ff;
        background: $surface;
        color: #ffffff;
    }
    
    #anima-input:focus {
        border: round #00ff00;
        background: #002200;
        color: #00ff00;
    }
    
    #anima-input-hint {
        width: 20;
        height: 3;
        content-align: left middle;
        color: #888888;
    }
    
    #anima-buttons {
        width: 100%;
        height: 3;
        align-horizontal: center;
    }
    
    #anima-help {
        width: 100%;
        height: 1;
        content-align: center middle;
        color: #888888;
    }
    
    Button {
        margin: 0 1;
    }
    """

    def __init__(self, total_episodes: int) -> None:
        super().__init__()
        self.total_episodes = total_episodes

    def compose(self) -> ComposeResult:
        with Vertical(id="anima-container"):
            yield Static("🎨 ANIMA STANDING/EVENT 생성", id="anima-title")
            yield Static(f"에피소드 범위: 1~{self.total_episodes}\n0 = 전체 에피소드 생성", id="anima-info")
            with Horizontal(id="anima-input-row"):
                yield Static("EP 번호:", id="anima-input-label")
                yield Input(placeholder="0 (전체)", id="anima-input")
                yield Static("(숫자 입력 후 Enter)", id="anima-input-hint")
            with Horizontal(id="anima-buttons"):
                yield Button("전체 생성 (0)", id="anima-all", variant="primary")
                yield Button("선택 EP 생성", id="anima-single", variant="success")
                yield Button("취소", id="anima-cancel", variant="error")
            yield Static("[1]: 전체 | [2]: 선택 EP | [Esc]: 취소", id="anima-help")

    def on_mount(self) -> None:
        self.query_one("#anima-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "anima-all":
            self.dismiss(0)
        elif event.button.id == "anima-single":
            value = self.query_one("#anima-input", Input).value.strip()
            if value and value.isdigit():
                ep_num = int(value)
                if 0 <= ep_num <= self.total_episodes:
                    self.dismiss(ep_num)
        elif event.button.id == "anima-cancel":
            self.dismiss(None)

    def on_key(self, event) -> None:
        input_widget = self.query_one("#anima-input", Input)
        if input_widget.has_focus:
            if event.key == "escape":
                self.dismiss(None)
            return

        if event.key == "1":
            self.dismiss(0)
        elif event.key in ("2", "i"):
            input_widget.focus()
        elif event.key == "escape":
            self.dismiss(None)

    def on_input_changed(self, event: Input.Changed) -> None:
        # 깔끔한 숫자 전용 필터링
        digits = "".join(c for c in event.value if c.isdigit())
        if digits and int(digits) > self.total_episodes:
            digits = str(self.total_episodes)
        if event.value != digits:
            event.input.value = digits

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value and value.isdigit():
            ep_num = int(value)
            if 0 <= ep_num <= self.total_episodes:
                self.dismiss(ep_num)


# =============================================================================
# 2. 메인 TUI 애플리케이션
# =============================================================================
class FourPaneApp(App):
    CSS = """
    #main-container { height: 1fr; }
    #left-pane { width: 30%; height: 100%; }
    #menu { height: 2fr; border: round #00bfff; }
    #description { height: 1fr; border: round #ffaa00; padding: 1; }
    #editor { width: 70%; height: 100%; border: round #00ff00; }
    #status-bar { dock: bottom; height: 1; width: 100%; background: #333333; color: white; padding-left: 1; }
    """

    def _build_menu_options(self) -> list:
        """anima_enb에 따라 메뉴 옵션 동적 생성"""
        options = [
            Option("0. 설정 초기화 (Reset Config)", id="reset_config"),
            Option("1. 플롯 생성 (Step1: 테마)", id="generate_plot"),
            Option("2. 플롯 생성 (Step2: 가이드)", id="generate_guides"),
            Option("3. 소설 주인공 설정 (Protagonist)", id="protagonist_setup"),
            Option("4. 상대방 설정 (Partner)", id="partner_setup"),
            Option("5. 에피소드 생성 (Generate Episode)", id="generate_episode"),
            Option("6. 생성 및 보완 (Generate & Refine)", id="generate_refine"),
            Option("7. 스토리 생성 (Generate Full Story)", id="generate_story"),
            Option("8. 설정 내보내기 (Export Config)", id="export_config"),
            Option("9. 설정 복구 (Restore Config)", id="restore_config"),
            Option("10. 전체 자동 실행 (Auto-Run)", id="auto_run"),
        ]
        if config.get_json_value().get("anima_enb", "no") in ("yes", True, "1"):
            options.append(Option("11. ANIMA STANDING/EVENT 생성", id="anima_gen"))
        options.append(Option("Q. 프로그램 종료 (Quit)", id="quit"))
        return options

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-container"):
            with Vertical(id="left-pane"):
                yield OptionList(*self._build_menu_options(), id="menu")
                yield Static("메뉴를 선택해주세요.", id="description")
            
            yield TextArea("시스템 준비 중...", id="editor")
        
        yield Label("상태: 준비됨 | [Arrow]: 메뉴 이동 | [Enter]: 실행 | [Ctrl+Q]: 종료", id="status-bar")

    def action_quit(self) -> None:
        """Textual 기본 Ctrl+Q 동작 가로채기"""
        self._show_quit_dialog()

    def _show_quit_dialog(self) -> None:
        self.push_screen(QuitConfirmScreen(), lambda confirmed: self.exit() if confirmed else None)

    def _check_existing_episodes(self) -> list:
        """progress/ep{N:02d}_*.txt 또는 result/episode_{N:02d}.md 파일 존재 여부 확인"""
        import glob
        episode_full_track = []
        plot_hash = getattr(config, 'plot_hash', '')
        progress_dir = os.path.join(os.path.dirname(__file__), "progress")
        result_dir = os.path.join(os.path.dirname(__file__), "result")

        for i in range(config.total_episodes):
            ep_num = i + 1
            # progress/ep{N:02d}_{hash}.txt 또는 progress/ep{N:02d}_*.txt 체크
            progress_file = None
            if plot_hash:
                progress_file = os.path.join(progress_dir, f"ep{ep_num:02d}_{plot_hash}.txt")
            if not progress_file or not os.path.exists(progress_file):
                # hash 없이 패턴 매칭
                pattern = os.path.join(progress_dir, f"ep{ep_num:02d}_*.txt")
                matches = glob.glob(pattern)
                progress_file = matches[0] if matches else None

            # result/episode_{N:02d}.md 체크
            result_file = os.path.join(result_dir, f"episode_{ep_num:02d}.md")

            exists = (progress_file and os.path.exists(progress_file)) or os.path.exists(result_file)
            episode_full_track.append(exists)

        return episode_full_track

    def _show_episode_select_dialog(self, episode_full_track: list) -> None:
        """에피소드 선택 모달 표시"""
        self.push_screen(
            EpisodeSelectScreen(config.total_episodes, episode_full_track),
            lambda ep_num: self._start_story_gen(ep_num) if ep_num is not None else None
        )

    def _start_story_gen(self, ep_num: int) -> None:
        """선택된 ep_num으로 스토리 생성 워커 시작"""
        self._worker_generate_story(ep_num=ep_num)

    def on_mount(self) -> None:
        self.query_one("#menu").border_title = "메뉴 (Menu)"
        self.query_one("#description").border_title = "설명 (Description)"
        self.query_one("#editor").border_title = "에디터 (Editor)"

        self.query_one("#menu", OptionList).focus()
        self._interrupt_flag = False
        self._anim_running = False  # 애니메이션 중단 플래그 초기화

        # CLI 인자 파싱 간결화
        cmd_args = {"id": None, "job": None, "job2": None}
        for i, arg in enumerate(sys.argv[:-1]):
            if arg in ("-id", "--id"): cmd_args["id"] = int(sys.argv[i+1])
            elif arg in ("-job", "--job"): cmd_args["job"] = int(sys.argv[i+1])
            elif arg in ("-job2", "--job2"): cmd_args["job2"] = int(sys.argv[i+1])

        if cmd_args["id"] is not None: config.selected_jinshugai_id = cmd_args["id"]
        if cmd_args["job"] is not None: config.cmd_job = cmd_args["job"]
        if cmd_args["job2"] is not None: config.cmd_job2 = cmd_args["job2"]

        self._worker_init()

    # -------------------------------------------------------------------------
    # 스레드 전용 UI 업데이트 & 완료 공통 헬퍼 함수
    # -------------------------------------------------------------------------
    def _update_ui(self, editor_text: str | None = None, status_text: str | None = None, readonly: bool | None = None) -> None:
        """스레드 내부에서 안전하게 UI를 업데이트하는 함수"""
        if editor_text is not None or readonly is not None:
            editor = self.query_one("#editor", TextArea)
            if editor_text is not None: editor.text = editor_text
            if readonly is not None: editor.readonly = readonly
        if status_text is not None:
            self.query_one("#status-bar", Label).update(status_text)

    def _finish_worker(self, editor_text: str | None = None, status_msg: str = "", readonly: bool = True) -> None:
        """워커 완료 시 애니메이션 정지, 타임스탬프 상태창 업데이트 및 메뉴 포커스 처리"""
        self.workers.cancel_group(self, "_animate_status")
        self._anim_running = False  # 애니메이션 중단 플래그
        now = datetime.datetime.now().strftime("%H:%M:%S")
        final_status = f"상태: [{now}] {status_msg}" if status_msg else "상태: 완료"

        self._update_ui(editor_text=editor_text, status_text=final_status, readonly=readonly)
        self.query_one("#menu", OptionList).focus()

    @work(thread=True, exclusive=True, group="_animate_status")
    def _animate_status(self, base_text: str) -> None:
        import time
        while True:
            for dots in [".", "..", "...", "....", "....."]:
                if not getattr(self, "_anim_running", True):
                    return
                self.call_from_thread(self._update_ui, status_text=f"{base_text}{dots}")
                time.sleep(0.3)

    def _start_llm_animation(self, base_text: str = "상태: LLM 동작중") -> None:
        self._anim_running = True  # 애니메이션 시작 플래그
        self._animate_status(base_text)

    def _generate_and_parse_progression(self) -> str:
        total_eps = config.total_episodes
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            result = generate_ultimate_heroine_progression(total_eps)
        finally:
            sys.stdout = old_stdout

        progression_array = [f"{ep['animal_desc']} ({ep['matrix_desc']})" for ep in result["episodes"]]
        config.progression_array = progression_array
        config.persona_result = result
        return result.get("persona_text", f"Progression 생성 완료 (총 {len(progression_array)}개 에피소드)")

    @work(thread=True)
    def _worker_init(self) -> None:
        try:
            # 기존 progress 상태 로드 (plot_hash 복구)
            progress_state = llm_novel_gui_func.load_progress_state()
            if progress_state:
                saved_hash = progress_state.get("plot_hash", "")
                if saved_hash:
                    config.plot_hash = saved_hash

                    # 기존 에피소드 내용 로드 (기/승/전/결)
                    episode_contents = llm_novel_gui_func.load_episodes_from_progress(saved_hash)
                    loaded_count = 0
                    if episode_contents:
                        for i in range(min(len(episode_contents), len(config.episode_content))):
                            if episode_contents[i]:
                                config.episode_content[i] = episode_contents[i]
                                config.episode_track[i] = True
                                loaded_count += 1

                    # 복구 결과 표시
                    restore_msg = f"=== 이전 세션 복구 ===\n"
                    restore_msg += f"Hash: {saved_hash}\n"
                    restore_msg += f"주인공: {progress_state.get('name', 'N/A')} ({progress_state.get('age', 'N/A')}세, {progress_state.get('job', 'N/A')})\n"
                    restore_msg += f"상대방: {progress_state.get('name2', 'N/A')} ({progress_state.get('age2', 'N/A')}세, {progress_state.get('job2', 'N/A')})\n"
                    restore_msg += f"에피소드: {loaded_count}/{len(episode_contents)}개 로드됨\n\n"

                    character_setup.random_setup_all()
                    prog_msg = self._generate_and_parse_progression()
                    init_msg = f"[plot_hash: {config.plot_hash}]\n\n{restore_msg}{prog_msg}"
                    if config.selected_jinshugai_id is not None:
                        init_msg = f"[ID 지정됨: {config.selected_jinshugai_id}]\n\n" + init_msg
                    self.call_from_thread(self._update_ui, editor_text=init_msg, status_text=f"상태: 복구 완료 (에피소드 {loaded_count}개)", readonly=True)
                    return

            # 새 세션
            character_setup.random_setup_all()
            prog_msg = self._generate_and_parse_progression()
            init_msg = f"시스템 준비 완료. 메뉴에서 항목을 선택하세요.\n\n{prog_msg}"
            if config.selected_jinshugai_id is not None:
                init_msg = f"[ID 지정됨: {config.selected_jinshugai_id}]\n\n" + init_msg
            self.call_from_thread(self._update_ui, editor_text=init_msg, status_text="상태: 준비 완료", readonly=True)
        except Exception as e:
            self.call_from_thread(self._update_ui, editor_text=f"초기화 오류: {e}", status_text="상태: 초기화 오류")

    # -------------------------------------------------------------------------
    # 이벤트 핸들러
    # -------------------------------------------------------------------------
    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        desc = self.query_one("#description", Static)
        option_id = event.option.id

        descriptions = {
            "reset_config": "모든 설정을 초기화합니다.\nprogress/ 디렉토리 삭제\n+ 설정값 리셋",
            "generate_plot": "[Step1] 테마 생성 LLM 호출\n직업/나이/관계/트리거 설정\n+ 테마 생성 (약 1-2분)",
            "generate_guides": "[Step2] 가이드 생성 LLM 호출\n기-승-전-결 가이드 생성\n+ Agent Review (약 3-5분)",
            "protagonist_setup": "주인공 캐릭터 시트를 표시합니다.",
            "partner_setup": "상대방(파트너) 캐릭터 시트를 표시합니다.",
            "generate_episode": "progression 재생성 후 에피소드를 생성합니다.",
            "generate_refine": "에피소드 요약을 생성하고 보완합니다.",
            "generate_story": "전체 스토리를 생성하여 저장합니다.",
            "export_config": "현재 설정을 내보냅니다.",
            "restore_config": "파일에서 설정을 복구합니다.",
            "auto_run": "전체 과정을 자동 실행합니다.",
            "anima_gen": "ANIMA STANDING/EVENT 이미지 생성\n에피소드 선택 후 이미지 생성\n(ComfyUI 실행 필요)",
            "quit": "프로그램을 종료합니다.",
        }
        desc.update(descriptions.get(option_id, "메뉴를 선택해주세요."))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if option_id == "quit":
            self._show_quit_dialog()
            return

        self._interrupt_flag = False
        self._update_ui(editor_text="⏳ 작업 시작... 잠시 기다려주세요.", status_text="상태: 작업 시작...", readonly=True)

        # 7번 메뉴: 기존 에피소드가 있으면 모달 표시
        if option_id == "generate_story":
            # progress/ep{N:02d}_{hash}.txt 또는 result/episode_{N:02d}.md 파일 존재 여부 체크
            episode_full_track = self._check_existing_episodes()
            has_existing = any(episode_full_track)
            if has_existing:
                self._show_episode_select_dialog(episode_full_track)
                return

        # 11번 메뉴: ANIMA 생성 - 에피소드 선택 모달
        if option_id == "anima_gen":
            self._show_anima_episode_select_dialog()
            return

        worker_map = {
            "reset_config": self._worker_reset_config,
            "generate_plot": self._worker_generate_plot_step1,
            "generate_guides": self._worker_generate_plot_step2,
            "protagonist_setup": self._worker_protagonist_setup,
            "partner_setup": self._worker_partner_setup,
            "generate_episode": self._worker_generate_episode,
            "generate_refine": self._worker_generate_refine,
            "generate_story": self._worker_generate_story,
            "export_config": self._worker_export_config,
            "restore_config": self._worker_restore_config,
            "auto_run": self._worker_auto_run,
            "anima_gen": self._worker_anima_gen,
        }
        if option_id in worker_map:
            worker_map[option_id]()

    # -------------------------------------------------------------------------
    # 백그라운드 워커 메서드들 (완료 시 _finish_worker 일괄 사용)
    # -------------------------------------------------------------------------
    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_reset_config(self) -> None:
        """0번 메뉴: 설정 초기화"""
        try:
            # progress/ 디렉토리 삭제
            cleared = llm_novel_gui_func.clear_progress_directory()
            # 설정값 리셋
            llm_novel_gui_func.reset_config_state()
            # 에피소드 내용 초기화
            for i in range(config.total_episodes):
                config.episode_content[i] = ""
                config.episode_track[i] = False
                config.episode_full_content[i] = ""
                config.episode_full_track[i] = False

            result_msg = f"=== 설정 초기화 완료 ===\n\n"
            result_msg += f"[인자 값]\n"
            result_msg += f"  selected_jinshugai_id: {config.selected_jinshugai_id}\n"
            result_msg += f"  cmd_job: {getattr(config, 'cmd_job', None)}\n"
            result_msg += f"  cmd_job2: {getattr(config, 'cmd_job2', None)}\n\n"
            result_msg += f"- progress/ 파일 {cleared}개 삭제됨\n"
            result_msg += f"- 설정값 리셋됨\n"
            result_msg += f"- 에피소드 내용 초기화됨\n\n"
            result_msg += f"이제 1번 메뉴부터 다시 시작하세요."

            self.call_from_thread(self._finish_worker, editor_text=result_msg, status_msg="설정 초기화 완료", readonly=True)
        except Exception as e:
            self.call_from_thread(self._finish_worker, editor_text=f"초기화 오류: {e}", status_msg="초기화 오류")

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_generate_plot_step1(self) -> None:
        progress_log = []
        def gui_log(msg: str):
            llm_novel_gui_func.logger.info(msg)
            progress_log.append(msg)
            txt = f"[1번] 플롯 생성 Step1 진행 중...\n\n" + "\n".join(progress_log[-20:])
            self.call_from_thread(self._update_ui, editor_text=txt, status_text=f"상태: Step1 - {msg[:40]}...")

        try:
            if not config.plot_hash:
                llm_novel_gui_func.generate_plot_hash()
            character_setup.job_and_age_init()

            step1_result = theme_gen_auto.theme_gen_auto_step1(
                "성인용 러브코메디 라이트 노벨",
                num_episodes=config.total_episodes,
                log_fn=gui_log
            )
            self._step1_result = step1_result

            debug_msg = f"[Step1 완료]\nID: {config.selected_jinshugai_id or '랜덤'}\n주인공: {config.name} ({config.age}세, {config.job})\n상대방: {config.name2} ({config.age2}세, {config.job2})\n관계: {config.relationship}\n첫 이벤트: {config.first_event}\n두 번째 이벤트: {config.second_event}\n저항 이유: {config.resistance_reason}\n타락 이유: {config.corruption_reason}\n\n[테마 생성 완료]\n"
            final_txt = f"Hash: {config.plot_hash}\n\n{debug_msg}"
            
            # 완료 시 _finish_worker 한 줄로 깔끔하게 처리
            self.call_from_thread(self._finish_worker, editor_text=final_txt, status_msg="Step1 완료! 2번 메뉴로 Step2 실행", readonly=True)
        except Exception as e:
            self.call_from_thread(self._finish_worker, editor_text=f"Step1 중 오류 발생:\n{e}", status_msg="Step1 오류 발생")

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_generate_plot_step2(self) -> None:
        self.call_from_thread(self._start_llm_animation, "상태: 플롯 생성 Step2 중")
        progress_log = []
        def gui_log(msg: str):
            llm_novel_gui_func.logger.info(msg)
            progress_log.append(msg)
            txt = f"[2번] 플롯 생성 Step2 진행 중...\n\n" + "\n".join(progress_log[-20:])
            self.call_from_thread(self._update_ui, editor_text=txt, status_text=f"상태: Step2 - {msg[:40]}...")

        try:
            if not hasattr(self, '_step1_result') or not self._step1_result:
                self.call_from_thread(self._finish_worker, editor_text="먼저 1번 메뉴(Step1)를 실행해주세요.", status_msg="Step1 미실행")
                return

            step2_result = theme_gen_auto.theme_gen_auto_step2(
                "성인용 러브코메디 라이트 노벨",
                self._step1_result,
                num_episodes=config.total_episodes,
                log_fn=gui_log
            )
            llm_novel_gui_func.export_config_to_file(os.path.join("data", "config_export.yaml"))
            llm_novel_gui_func.complete_theme_auto()
            prog_msg = self._generate_and_parse_progression()

            debug_msg = f"[Step2 완료]\n가이드 수: {len(config.corruption_guides)}개\n상대방 가이드 수: {len(config.partner_corruption_guides)}개\n\n[Progress] Hash: {config.plot_hash} | 완료 저장됨\n\n{config.plot_result}\n\n{prog_msg}"
            self.call_from_thread(self._finish_worker, editor_text=debug_msg, status_msg="Step2 완료!", readonly=True)
        except Exception as e:
            self.call_from_thread(self._finish_worker, editor_text=f"Step2 중 오류 발생:\n{e}", status_msg="Step2 오류 발생")

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_protagonist_setup(self) -> None:
        try:
            lv = getattr(config, 'love_value', 0)
            sheet, _ = character_setup.character_sheet(lv)
            self.call_from_thread(self._finish_worker, editor_text=sheet, status_msg="주인공 설정 표시 중 | [E]: 편집 모드 토글", readonly=False)
        except Exception as e:
            self.call_from_thread(self._finish_worker, editor_text=f"캐릭터 시트 오류: {e}", status_msg="오류 발생")

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_partner_setup(self) -> None:
        try:
            sheet = character_setup.partner_sheet()
            self.call_from_thread(self._finish_worker, editor_text=sheet, status_msg="상대방 설정 표시 중", readonly=True)
        except Exception as e:
            self.call_from_thread(self._finish_worker, editor_text=f"상대방 시트 오류: {e}", status_msg="오류 발생")

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_generate_episode(self) -> None:
        self.call_from_thread(self._start_llm_animation, "상태: 에피소드 생성 중")
        progress_log = []
        def episode_callback(response_text: str, info: dict = None):
            if info is None:
                info = {}
            msg = f"[에피소드 {info.get('current_episode', 0)}/{info.get('total_episodes', 0)}] {info.get('status', '')}"
            progress_log.append(msg)
            txt = f"[5번] 에피소드 생성 진행 중...\n\n{msg}\n\n{response_text[:500]}...\n\n[최근 로그]\n" + "\n".join(progress_log[-10:])
            self.call_from_thread(self._update_ui, editor_text=txt, status_text=f"상태: 에피소드 생성 - {msg}")

        try:
            result = llm_novel_gui_func.generate_episodes(callback=episode_callback)
            if result["success"]:
                self.call_from_thread(self._finish_worker, editor_text=f"{result['result_text']}\n\n{result['prog_msg']}", status_msg="에피소드 생성 완료 | [E]: 편집 모드", readonly=False)
            else:
                self.call_from_thread(self._finish_worker, editor_text=f"에피소드 생성 중 오류: {result['result_text']}", status_msg="에피소드 생성 오류")
        except Exception as e:
            self.call_from_thread(self._finish_worker, editor_text=f"에피소드 생성 중 오류: {e}", status_msg="에피소드 생성 오류")

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_generate_refine(self) -> None:
        self.call_from_thread(self._start_llm_animation, "상태: 생성 및 보완 중")
        progress_log = []
        def refine_callback(response_text: str, info: dict):
            msg = f"[에피소드 {info.get('current_episode', 0)}/{info.get('total_episodes', 0)}] {info.get('status', '')}"
            progress_log.append(msg)
            txt = f"[6번] 생성 및 보완 진행 중...\n\n{msg}\n\n{response_text[:500]}...\n\n[최근 로그]\n" + "\n".join(progress_log[-10:])
            self.call_from_thread(self._update_ui, editor_text=txt, status_text=f"상태: 생성 및 보완 - {msg}")

        try:
            result = llm_novel_gui_func.generate_refine(callback=refine_callback)
            if result["success"]:
                self.call_from_thread(self._finish_worker, editor_text=result["out_txt"], status_msg=f"생성 및 보완 완료 ({result['episode_count']}개) | [E]: 편집 모드", readonly=False)
            else:
                self.call_from_thread(self._finish_worker, editor_text=f"생성 및 보완 중 오류: {result['out_txt']}", status_msg="오류 발생")
        except Exception as e:
            self.call_from_thread(self._finish_worker, editor_text=f"생성 및 보완 중 오류: {e}", status_msg="오류 발생")

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_generate_story(self, ep_num: int = 0) -> None:
        self.call_from_thread(self._start_llm_animation, "상태: 스토리 생성 중")
        progress_log = []
        def story_callback(response_text: str, info: dict):
            msg = f"[에피소드 {info.get('current_episode', 0)}/{info.get('total_episodes', 0)}] {info.get('status', '')}"
            progress_log.append(msg)
            txt = f"[7번] 스토리 생성 진행 중...\n\n{msg}\n\n{response_text[:800]}...\n\n[최근 로그]\n" + "\n".join(progress_log[-10:])
            self.call_from_thread(self._update_ui, editor_text=txt, status_text=f"상태: 스토리 생성 - {msg}")

        try:
            result = llm_novel_gui_func.generate_story(ep_num=ep_num, callback=story_callback)
            if result["success"]:
                self.call_from_thread(self._finish_worker, editor_text=result["out_txt"], status_msg="스토리 생성 완료 | [E]: 편집 모드", readonly=False)
            else:
                self.call_from_thread(self._finish_worker, editor_text=f"스토리 생성 중 오류: {result['out_txt']}", status_msg="스토리 생성 오류")
        except Exception as e:
            self.call_from_thread(self._finish_worker, editor_text=f"스토리 생성 중 오류: {e}", status_msg="스토리 생성 오류")

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_export_config(self) -> None:
        try:
            filepath = os.path.join("data", "config_export.yaml")
            result = llm_novel_gui_func.export_config_to_file(filepath)
            self.call_from_thread(self._finish_worker, editor_text=f"{result}\n\n파일: {filepath}", status_msg="설정 내보내기 완료", readonly=True)
        except Exception as e:
            self.call_from_thread(self._finish_worker, editor_text=f"설정 내보내기 오류: {e}", status_msg="오류 발생")

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_restore_config(self) -> None:
        try:
            filepath = os.path.join("data", "config_export.yaml")
            result = llm_novel_gui_func.restore_config_from_file(filepath)
            self.call_from_thread(self._finish_worker, editor_text=f"{result}", status_msg="설정 복구 완료", readonly=True)
        except Exception as e:
            self.call_from_thread(self._finish_worker, editor_text=f"설정 복구 오류: {e}", status_msg="오류 발생")

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_auto_run(self) -> None:
        self.call_from_thread(self._start_llm_animation, "상태: 전체 자동 실행 중")
        try:
            anima_enb = config.get_json_value().get("anima_enb", "no") in ("yes", True, "1")
            episode_files = []
            try:
                import json
                with open(os.path.join("data", "episode_setup.json"), "r", encoding="utf-8") as f:
                    episode_files = json.load(f).get("files", [])
            except Exception:
                pass

            def console_callback(step: str, status_msg: str, content_text: str):
                txt = f"[{status_msg}]\n{content_text}"
                self.call_from_thread(self._update_ui, editor_text=txt, status_text=f"상태: 자동 실행 - {status_msg}")

            result = llm_novel_gui_func.run_auto_sequence(
                episode_files=episode_files,
                current_file_index=0,
                anima_enb=anima_enb,
                callback=console_callback,
            )

            if result["success"]:
                self.call_from_thread(self._finish_worker, editor_text=f"전체 자동 실행 완료!\n\n{result['content_text']}", status_msg="자동 실행 완료", readonly=True)
            else:
                self.call_from_thread(self._finish_worker, editor_text=f"자동 실행 오류:\n{result['content_text']}", status_msg="자동 실행 오류")
        except Exception as e:
            self.call_from_thread(self._finish_worker, editor_text=f"자동 실행 중 오류: {e}", status_msg="자동 실행 오류")

    # -------------------------------------------------------------------------
    # ANIMA 생성 관련 메서드
    # -------------------------------------------------------------------------
    def _show_anima_episode_select_dialog(self) -> None:
        """ANIMA 생성용 에피소드 선택 모달 표시 (0=전체)"""
        self.push_screen(
            AnimaEpisodeSelectScreen(config.total_episodes),
            lambda ep_num: self._worker_anima_gen(ep_num) if ep_num is not None else None
        )

    @work(thread=True, exclusive=True, group="anima_work")
    def _worker_anima_gen(self, ep_num: int = 0) -> None:
        """11번 메뉴: ANIMA STANDING/EVENT 생성"""
        self.call_from_thread(self._start_llm_animation, "상태: ANIMA 생성 중")
        total_eps = config.total_episodes

        try:
            anima_result = llm_novel_gui_func.run_anima_gen(
                total_episodes=total_eps,
                ep_num=ep_num,
                callback=lambda step, status_msg, content_text: self.call_from_thread(
                    self._update_ui, status_text=status_msg)
            )

            if anima_result["success"]:
                results = anima_result["results"]
                if ep_num == 0:
                    out_txt = f"[ANIMA STANDING/EVENT]\n\n에피소드 1~{total_eps} ANIMA 이미지 생성이 완료되었습니다.\n\n" + "\n".join(results)
                else:
                    out_txt = f"[ANIMA STANDING/EVENT]\n\n에피소드 {ep_num} ANIMA 이미지 생성이 완료되었습니다.\n\n" + "\n".join(results)
                self.call_from_thread(self._finish_worker, editor_text=out_txt, status_msg="ANIMA 생성 완료", readonly=True)
            else:
                error_msg = "\n".join(anima_result["progress_log"][-3:])
                self.call_from_thread(self._finish_worker, editor_text=f"ANIMA 생성 중 오류 발생:\n{error_msg}", status_msg="ANIMA 생성 오류")
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            self.call_from_thread(self._finish_worker, editor_text=f"ANIMA 생성 중 오류 발생:\n{error_msg}", status_msg="ANIMA 생성 오류")

    # -------------------------------------------------------------------------
    # 키 및 포커스 이벤트
    # -------------------------------------------------------------------------
    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self.query_one("#status-bar", Label).update(f"상태: 텍스트 입력 중... (현재 글자 수: {len(event.text_area.text)})")

    def on_key(self, event) -> None:
        editor = self.query_one("#editor", TextArea)
        status = self.query_one("#status-bar", Label)

        if event.key in ("tab", "shift_tab"):
            event.prevent_default()
            return

        if event.key == "ctrl+q":
            self._show_quit_dialog()
            return

        if event.key in ("e", "E"):
            if self.focused == editor:
                return
            editor.readonly = not editor.readonly
            mode_str = "읽기 전용 모드" if editor.readonly else "편집 모드 | [E]: 편집 종료"
            status.update(f"상태: {mode_str} (현재 글자 수: {len(editor.text)})")
            editor.focus()


if __name__ == "__main__":
    app = FourPaneApp()
    app.run()
