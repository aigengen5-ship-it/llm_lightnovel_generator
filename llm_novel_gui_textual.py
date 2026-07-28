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
from persona import generate_ultimate_heroine_progression
import llm_novel_gui_func
import theme_gen_auto

from textual import work
from textual.app import App, ComposeResult
from textual.screen import ModalScreen
from textual.containers import Horizontal, Vertical
from textual.widgets import OptionList, Static, TextArea, Label, Button
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

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-container"):
            with Vertical(id="left-pane"):
                yield OptionList(
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
                    Option("Q. 프로그램 종료 (Quit)", id="quit"),
                    id="menu"
                )
                yield Static("메뉴를 선택해주세요.", id="description")
            
            yield TextArea("시스템 준비 중...", id="editor")
        
        yield Label("상태: 준비됨 | [Arrow]: 메뉴 이동 | [Enter]: 실행 | [Ctrl+Q]: 종료", id="status-bar")

    def action_quit(self) -> None:
        """Textual 기본 Ctrl+Q 동작 가로채기"""
        self._show_quit_dialog()

    def _show_quit_dialog(self) -> None:
        self.push_screen(QuitConfirmScreen(), lambda confirmed: self.exit() if confirmed else None)

    def on_mount(self) -> None:
        self.query_one("#menu").border_title = "메뉴 (Menu)"
        self.query_one("#description").border_title = "설명 (Description)"
        self.query_one("#editor").border_title = "에디터 (Editor)"

        self.query_one("#menu", OptionList).focus()
        self._interrupt_flag = False

        # CLI 인자 파싱 간결화
        cmd_args = {"id": None, "inc_flag": None, "job": None, "job2": None}
        for i, arg in enumerate(sys.argv[:-1]):
            if arg in ("-id", "--id"): cmd_args["id"] = int(sys.argv[i+1])
            elif arg in ("-inc_flag", "--inc_flag"): cmd_args["inc_flag"] = int(sys.argv[i+1])
            elif arg in ("-job", "--job"): cmd_args["job"] = int(sys.argv[i+1])
            elif arg in ("-job2", "--job2"): cmd_args["job2"] = int(sys.argv[i+1])

        if cmd_args["id"] is not None: config.selected_jinshugai_id = cmd_args["id"]
        config.inc_flag = cmd_args["inc_flag"] if cmd_args["inc_flag"] is not None else 0
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
        now = datetime.datetime.now().strftime("%H:%M:%S")
        final_status = f"상태: [{now}] {status_msg}" if status_msg else "상태: 완료"
        
        self._update_ui(editor_text=editor_text, status_text=final_status, readonly=readonly)
        self.query_one("#menu", OptionList).focus()

    @work(thread=True, exclusive=True, group="_animate_status")
    def _animate_status(self, base_text: str) -> None:
        import time
        while True:
            for dots in [".", "..", "...", "....", "....."]:
                self.call_from_thread(self._update_ui, status_text=f"{base_text}{dots}")
                time.sleep(0.3)

    def _start_llm_animation(self, base_text: str = "상태: LLM 동작중") -> None:
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
            character_setup.random_setup_all()
            prog_msg = self._generate_and_parse_progression()
            init_msg = f"시스템 준비 완료. 메뉴에서 항목을 선택하세요.\n\n{prog_msg}"
            if config.selected_jinshugai_id is not None:
                init_msg = f"[진수개 ID 지정됨: {config.selected_jinshugai_id}]\n\n" + init_msg
            self.call_from_thread(self._update_ui, editor_text=init_msg, status_text="상태: 준비 완료", readonly=True)
        except Exception as e:
            self.call_from_thread(self._update_ui, editor_text=f"초기화 오류: {e}", status_text="상태: 초기화 오류")

    # -------------------------------------------------------------------------
    # 이벤트 핸들러
    # -------------------------------------------------------------------------
    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        desc = self.query_one("#description", Static)
        status = self.query_one("#status-bar", Label)
        option_id = event.option.id

        descriptions = {
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

        worker_map = {
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
        }
        if option_id in worker_map:
            worker_map[option_id]()

    # -------------------------------------------------------------------------
    # 백그라운드 워커 메서드들 (완료 시 _finish_worker 일괄 사용)
    # -------------------------------------------------------------------------
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

            debug_msg = f"[Step1 완료]\n주인공: {config.name} ({config.age}세, {config.job})\n상대방: {config.name2} ({config.age2}세, {config.job2})\n관계: {config.relationship}\n첫 이벤트: {config.first_event}\n두 번째 이벤트: {config.second_event}\n저항 이유: {config.resistance_reason}\n타락 이유: {config.corruption_reason}\n\n[테마 생성 완료]\n"
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
        def episode_callback(response_text: str, info: dict):
            msg = f"[에피소드 {info.get('current_episode', 0)}/{info.get('total_episodes', 0)}] {info.get('status', '')}"
            progress_log.append(msg)
            txt = f"[5번] 에피소드 생성 진행 중...\n\n{msg}\n\n{response_text[:500]}...\n\n[최근 로그]\n" + "\n".join(progress_log[-10:])
            self.call_from_thread(self._update_ui, editor_text=txt, status_text=f"상태: 에피소드 생성 - {msg}")

        try:
            prog_msg = self._generate_and_parse_progression()
            use_extended = config.json_value.get("extended", "no") == "yes"

            if use_extended:
                jinshugai_list = getattr(config, 'theme_jinshugai', None)
                template_id = jinshugai_list[0].get('id', rand.randint(1, 10)) if jinshugai_list else rand.randint(1, 10)
                total_eps = config.total_episodes

                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                try:
                    plot_result = plot_gen.plot_gen_extended(
                        template_id=template_id,
                        total_episodes=total_eps,
                        theme_msg=getattr(config, 'plot', ''),
                        breeds_data=getattr(config, 'theme_breeds', None),
                        jinshugai_templates=getattr(config, 'theme_jinshugai', None),
                        progression_events=getattr(config, 'theme_events', None),
                        callback=episode_callback
                    )
                finally:
                    sys.stdout = old_stdout

                episodes = llm_novel_gui_func.split_episodes(plot_result)
                for i in range(total_eps):
                    config.episode_content[i] = episodes[i] if i < len(episodes) else ""
                    config.episode_track[i] = True
                config.episode_gen_flag = True

                self.call_from_thread(self._finish_worker, editor_text=f"{plot_result}\n\n{prog_msg}", status_msg="에피소드 생성 완료 (extended) | [E]: 편집 모드", readonly=False)
            else:
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                try:
                    result_text = story_gen.episode_gen()
                finally:
                    sys.stdout = old_stdout

                config.result_text = result_text
                episodes = llm_novel_gui_func.split_episodes(result_text)
                total_eps = config.total_episodes
                for i in range(total_eps):
                    config.episode_content[i] = episodes[i] if i < len(episodes) else ""
                    config.episode_track[i] = True
                config.episode_gen_flag = True

                self.call_from_thread(self._finish_worker, editor_text=f"{result_text}\n\n{prog_msg}", status_msg="에피소드 생성 완료 | [E]: 편집 모드", readonly=False)
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
            final_result = story_gen.episode_summary_gen(callback=refine_callback)
            episodes = llm_novel_gui_func.split_episodes(final_result)
            out_txt = f"## EPISODE 1 ##\n\n{config.episode_content[0]}" if (config.episode_content and config.episode_content[0]) else (episodes[0] if episodes else final_result)

            self.call_from_thread(self._finish_worker, editor_text=out_txt, status_msg=f"생성 및 보완 완료 ({len(episodes)}개) | [E]: 편집 모드", readonly=False)
        except Exception as e:
            self.call_from_thread(self._finish_worker, editor_text=f"생성 및 보완 중 오류: {e}", status_msg="오류 발생")

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_generate_story(self) -> None:
        self.call_from_thread(self._start_llm_animation, "상태: 스토리 생성 중")
        progress_log = []
        def story_callback(response_text: str, info: dict):
            msg = f"[에피소드 {info.get('current_episode', 0)}/{info.get('total_episodes', 0)}] {info.get('status', '')}"
            progress_log.append(msg)
            txt = f"[7번] 스토리 생성 진행 중...\n\n{msg}\n\n{response_text[:800]}...\n\n[최근 로그]\n" + "\n".join(progress_log[-10:])
            self.call_from_thread(self._update_ui, editor_text=txt, status_text=f"상태: 스토리 생성 - {msg}")

        try:
            import full_episode_gen
            result = full_episode_gen.full_episode_gen(ep_num=0, callback=story_callback)
            table = llm_novel_gui_func.build_episode_full_track_table()
            out_txt = f"{table}\n\n[최근 로그]\n" + "\n".join(progress_log[-20:])

            self.call_from_thread(self._finish_worker, editor_text=out_txt, status_msg="스토리 생성 완료 | [E]: 편집 모드", readonly=False)
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
            anima_enb = config.json_value.get("anima_enb", "no") in ("yes", True, "1")
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
