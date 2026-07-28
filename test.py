import os
import sys
import config
import character_setup
import story_gen
import plot_gen
import importlib
import random as rand
import io
from persona import generate_ultimate_heroine_progression
import llm_novel_gui_func
import theme_gen_auto

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import OptionList, Static, TextArea, Label
from textual.widgets.option_list import Option

# 로거 초기화
llm_novel_gui_func.init_logger(log_file=os.path.join("log", "gui_func_textual.log"))

class FourPaneApp(App):
    # CSS를 통한 화면 레이아웃 및 4개의 윈도우(패널) 디자인 설정
    CSS = """
    #main-container {
        height: 1fr; /* 상태바를 제외한 나머지 화면 전체 사용 */
    }
    
    #left-pane {
        width: 30%; /* 왼쪽 30% 영역 차지 */
        height: 100%;
    }
    
    #menu {
        height: 2fr; /* 왼쪽 영역의 2/3 차지 */
        border: round #00bfff; /* 파란색 테두리 */
    }
    
    #description {
        height: 1fr; /* 왼쪽 영역의 1/3 차지 */
        border: round #ffaa00; /* 주황색 테두리 */
        padding: 1;
    }
    
    #editor {
        width: 70%; /* 오른쪽 70% 영역 차지 */
        height: 100%;
        border: round #00ff00; /* 초록색 테두리 */
    }
    
    #status-bar {
        dock: bottom; /* 화면 가장 아래에 고정 */
        height: 1;
        width: 100%;
        background: #333333;
        color: white;
        padding-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        # 메인 영역 (좌/우 분할)
        with Horizontal(id="main-container"):
            # 왼쪽 영역 (위/아래 분할)
            with Vertical(id="left-pane"):
                # 1) 왼쪽 위: 메뉴 선택 (키보드 커서 입력 지원)
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
                # 2) 왼쪽 아래: 메뉴 설명 출력용 텍스트
                yield Static("메뉴를 선택해주세요.", id="description")
            
            # 3) 오른쪽: 텍스트 출력 및 수정이 가능한 텍스트 에디터
            yield TextArea("시스템 준비 중...", id="editor")
        
        # 4) 가장 아래: 현재 상태 표시
        yield Label("상태: 준비됨 | [Arrow]: 메뉴 이동 | [Enter]: 실행 | [Ctrl+C]: 중단 | [Ctrl+Q]: 종료", id="status-bar")

    def on_mount(self) -> None:
        # 앱이 실행될 때 각 윈도우에 제목(Title)을 달아줍니다.
        self.query_one("#menu").border_title = "메뉴 (Menu)"
        self.query_one("#description").border_title = "설명 (Description)"
        self.query_one("#editor").border_title = "에디터 (Editor)"

        # 포커스 고정
        menu = self.query_one("#menu", OptionList)
        menu.focus()

        # 중단 플래그 초기화
        self._interrupt_flag = False

        # 명령줄 인자 파싱
        cmd_jinshugai_id = None
        for i, arg in enumerate(sys.argv):
            if arg in ("-id", "--id") and i + 1 < len(sys.argv):
                try:
                    cmd_jinshugai_id = int(sys.argv[i + 1])
                except ValueError:
                    pass
                break

        cmd_inc_flag = None
        for i, arg in enumerate(sys.argv):
            if arg in ("-inc_flag", "--inc_flag") and i + 1 < len(sys.argv):
                try:
                    cmd_inc_flag = int(sys.argv[i + 1])
                except ValueError:
                    pass
                break

        cmd_job = None
        for i, arg in enumerate(sys.argv):
            if arg in ("-job", "--job") and i + 1 < len(sys.argv):
                try:
                    cmd_job = int(sys.argv[i + 1])
                except ValueError:
                    pass
                break

        cmd_job2 = None
        for i, arg in enumerate(sys.argv):
            if arg in ("-job2", "--job2") and i + 1 < len(sys.argv):
                try:
                    cmd_job2 = int(sys.argv[i + 1])
                except ValueError:
                    pass
                break

        if cmd_jinshugai_id is not None:
            config.selected_jinshugai_id = cmd_jinshugai_id
        if cmd_inc_flag is not None:
            config.inc_flag = cmd_inc_flag
        else:
            config.inc_flag = 0
        if cmd_job is not None:
            config.cmd_job = cmd_job
        if cmd_job2 is not None:
            config.cmd_job2 = cmd_job2

        # 초기화 작업을 스레드 워커로 호출하여 GUI 렌더링 블로킹 방지
        self._worker_init()

    # -------------------------------------------------------------------------
    # 스레드 전용 UI 업데이트 헬퍼 함수
    # -------------------------------------------------------------------------
    def _update_ui(self, editor_text: str | None = None, status_text: str | None = None, readonly: bool | None = None) -> None:
        """스레드 내부에서 call_from_thread로 안전하게 UI를 업데이트하는 함수"""
        if editor_text is not None:
            editor = self.query_one("#editor", TextArea)
            editor.text = editor_text
            if readonly is not None:
                editor.readonly = readonly
        if status_text is not None:
            status = self.query_one("#status-bar", Label)
            status.update(status_text)

    def _focus_menu(self) -> None:
        """포커스를 왼쪽 메뉴(OptionList)로 이동"""
        self.query_one("#menu", OptionList).focus()

    def _generate_and_parse_progression(self) -> str:
        """generate_ultimate_heroine_progression 호출 후 config.progression_array 저장."""
        total_eps = config.total_episodes
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()
        try:
            result = generate_ultimate_heroine_progression(total_eps)
        finally:
            sys.stdout = old_stdout

        progression_array = []
        for ep in result["episodes"]:
            desc = f"{ep['animal_desc']} ({ep['matrix_desc']})"
            progression_array.append(desc)

        config.progression_array = progression_array
        config.persona_result = result
        return f"Progression 생성 완료 (총 {len(progression_array)}개 에피소드)"

    @work(thread=True)
    def _worker_init(self) -> None:
        """초기화 작업 워커"""
        try:
            character_setup.random_setup_all()
            prog_msg = self._generate_and_parse_progression()
            init_msg = "시스템 준비 완료. 메뉴에서 항목을 선택하세요."
            if config.selected_jinshugai_id is not None:
                init_msg += f"\n\n[진수개 ID 지정됨: {config.selected_jinshugai_id}]"
            init_msg += f"\n\n{prog_msg}"
            
            self.call_from_thread(self._update_ui, editor_text=init_msg, status_text="상태: 준비 완료", readonly=True)
        except Exception as e:
            self.call_from_thread(self._update_ui, editor_text=f"초기화 오류: {e}", status_text="상태: 초기화 오류")

    # -------------------------------------------------------------------------
    # 이벤트 핸들러
    # -------------------------------------------------------------------------
    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """메뉴 커서 이동 이벤트"""
        desc = self.query_one("#description", Static)
        status = self.query_one("#status-bar", Label)
        option_id = event.option.id

        descriptions = {
            "generate_plot": "[Step1] 테마 생성 LLM 호출\n직업/나이/관계/트리거 설정\n+ 테마 생성 (약 1-2분)",
            "generate_guides": "[Step2] 가이드 생성 LLM 호출\n기-승-전-결 가이드 생성\n+ Agent Review (약 3-5분)",
            "protagonist_setup": "주인공 캐릭터 시트를\n표시합니다.",
            "partner_setup": "상대방(파트너) 캐릭터 시트를\n표시합니다.",
            "generate_episode": "progression 재생성 후\n에피소드를 생성합니다.\n\n[extended=yes]일 경우\nplot_gen_extended 모드.",
            "generate_refine": "에피소드 요약을 생성하고\n보완합니다.",
            "generate_story": "전체 스토리를 생성하여\nresult/episode_XX.md로 저장.",
            "export_config": "현재 설정을\ndata/config_export.yaml로\n내보냅니다.",
            "restore_config": "파일에서 설정을\n복구합니다.",
            "auto_run": "초기화 → 플롯 → 에피소드 → 스토리를\n순차적으로 자동 실행합니다.",
            "quit": "프로그램을\n즉시 종료합니다.",
        }
        desc.update(descriptions.get(option_id, "메뉴를 선택해주세요."))
        status.update(f"상태: 메뉴 탐색 중 - '{event.option.prompt}'")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """메뉴 선택 이벤트 -> @work 백그라운드 스레드로 전달"""
        option_id = event.option.id

        if option_id == "quit":
            self.exit()
            return

        # 중단 플래그 리셋 및 작업 시작 표시
        self._interrupt_flag = False
        self._update_ui(editor_text="⏳ 작업 시작... 잠시 기다려주세요.", status_text="상태: 작업 시작...", readonly=True)

        # 메뉴 아이디별 스레드 워커 분기
        if option_id == "generate_plot":
            self._worker_generate_plot_step1()
        elif option_id == "generate_guides":
            self._worker_generate_plot_step2()
        elif option_id == "protagonist_setup":
            self._worker_protagonist_setup()
        elif option_id == "partner_setup":
            self._worker_partner_setup()
        elif option_id == "generate_episode":
            self._worker_generate_episode()
        elif option_id == "generate_refine":
            self._worker_generate_refine()
        elif option_id == "generate_story":
            self._worker_generate_story()
        elif option_id == "export_config":
            self._worker_export_config()
        elif option_id == "restore_config":
            self._worker_restore_config()
        elif option_id == "auto_run":
            self._worker_auto_run()

    # -------------------------------------------------------------------------
    # @work 백그라운드 워커 메서드들 (메인 이벤트 루프 블로킹 차단)
    # -------------------------------------------------------------------------

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_generate_plot_step1(self) -> None:
        """1번 메뉴: 플롯 생성 Step1 백그라운드 스레드"""
        self.call_from_thread(self._update_ui, status_text="상태: 플롯 생성 Step1 중... [Ctrl+C]: 중단 | [Ctrl+Q]: 종료")
        progress_log = []

        def gui_log(msg: str):
            llm_novel_gui_func.logger.info(msg)
            progress_log.append(msg)
            if self._interrupt_flag:
                txt = f"[1번] 중단 요청됨!\n\n" + "\n".join(progress_log[-20:])
                self.call_from_thread(self._update_ui, editor_text=txt, status_text="상태: 중단됨!")
                return
            txt = f"[1번] 플롯 생성 Step1 진행 중...\n\n" + "\n".join(progress_log[-20:])
            st = f"상태: Step1 진행 중 - {msg[:40]}..."
            self.call_from_thread(self._update_ui, editor_text=txt, status_text=st)

        try:
            if not config.plot_hash:
                llm_novel_gui_func.generate_plot_hash()

            init_txt = f"[1번] 테마 생성 준비중...\nHash: {config.plot_hash}\n\nAPI 호출 중 (약 1-2분 소요)\n잠시 기다려주세요..."
            self.call_from_thread(self._update_ui, editor_text=init_txt, status_text="상태: 테마 생성 중...")

            character_setup.job_and_age_init()
            story_info = "성인용 러브코메디 라이트 노벨"

            step1_result = theme_gen_auto.theme_gen_auto_step1(
                story_info,
                num_episodes=config.total_episodes,
                log_fn=gui_log
            )

            self._step1_result = step1_result

            debug_msg = f"[Step1 완료]\n"
            debug_msg += f"주인공: {config.name} ({config.age}세, {config.job})\n"
            debug_msg += f"상대방: {config.name2} ({config.age2}세, {config.job2})\n"
            debug_msg += f"관계: {config.relationship}\n"
            debug_msg += f"첫 이벤트: {config.first_event}\n"
            debug_msg += f"두 번째 이벤트: {config.second_event}\n"
            debug_msg += f"저항 이유: {config.resistance_reason}\n"
            debug_msg += f"타락 이유: {config.corruption_reason}\n"
            debug_msg += f"\n[테마 생성 완료]\n"

            final_txt = f"Hash: {config.plot_hash}\n\n{debug_msg}"
            self.call_from_thread(self._update_ui, editor_text=final_txt, status_text="상태: Step1 완료 | 2번 메뉴로 Step2 실행", readonly=True)
            self.call_from_thread(self._focus_menu)

        except Exception as e:
            self.call_from_thread(self._update_ui, editor_text=f"Step1 중 오류 발생:\n{e}", status_text="상태: Step1 오류")
            self.call_from_thread(self._focus_menu)

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_generate_plot_step2(self) -> None:
        """2번 메뉴: 플롯 생성 Step2 백그라운드 스레드"""
        self.call_from_thread(self._update_ui, status_text="상태: 플롯 생성 Step2 중... [Ctrl+C]: 중단 | [Ctrl+Q]: 종료")
        progress_log = []

        def gui_log(msg: str):
            llm_novel_gui_func.logger.info(msg)
            progress_log.append(msg)
            if self._interrupt_flag:
                txt = f"[2번] 중단 요청됨!\n\n" + "\n".join(progress_log[-20:])
                self.call_from_thread(self._update_ui, editor_text=txt, status_text="상태: 중단됨!")
                return
            txt = f"[2번] 플롯 생성 Step2 진행 중...\n\n" + "\n".join(progress_log[-20:])
            st = f"상태: Step2 진행 중 - {msg[:40]}..."
            self.call_from_thread(self._update_ui, editor_text=txt, status_text=st)

        try:
            if not hasattr(self, '_step1_result') or not self._step1_result:
                self.call_from_thread(self._update_ui, editor_text="먼저 1번 메뉴(Step1)를 실행해주세요.", status_text="상태: Step1 미실행")
                self.call_from_thread(self._focus_menu)
                return

            story_info = "성인용 러브코메디 라이트 노벨"
            step1_result = self._step1_result

            step2_result = theme_gen_auto.theme_gen_auto_step2(
                story_info,
                step1_result,
                num_episodes=config.total_episodes,
                log_fn=gui_log
            )

            export_path = os.path.join("data", "config_export.yaml")
            llm_novel_gui_func.export_config_to_file(export_path)
            llm_novel_gui_func.logger.info(f"config_export.yaml 저장 완료 (Step2 후): {export_path}")

            llm_novel_gui_func.complete_theme_auto()
            prog_msg = self._generate_and_parse_progression()

            debug_msg = f"[Step2 완료]\n"
            debug_msg += f"가이드 수: {len(config.corruption_guides)}개\n"
            debug_msg += f"상대방 가이드 수: {len(config.partner_corruption_guides)}개\n"
            debug_msg += f"\n[Progress] Hash: {config.plot_hash} | 완료 저장됨\n"
            debug_msg += f"progress/theme_{config.plot_hash}.yaml\n"
            debug_msg += f"progress/progress_{config.plot_hash}.json\n\n"
            debug_msg += f"{config.plot_result}\n\n{prog_msg}"

            self.call_from_thread(self._update_ui, editor_text=debug_msg, status_text="상태: Step2 완료!", readonly=True)
            self.call_from_thread(self._focus_menu)

        except Exception as e:
            self.call_from_thread(self._update_ui, editor_text=f"Step2 중 오류 발생:\n{e}", status_text="상태: Step2 오류")
            self.call_from_thread(self._focus_menu)

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_protagonist_setup(self) -> None:
        """3번 메뉴: 소설 주인공 설정"""
        try:
            lv = getattr(config, 'love_value', 0)
            sheet, _ = character_setup.character_sheet(lv)
            self.call_from_thread(self._update_ui, editor_text=sheet, status_text="상태: 주인공 설정 표시 중 | [E]: 편집 모드 토글", readonly=False)
        except Exception as e:
            self.call_from_thread(self._update_ui, editor_text=f"캐릭터 시트 오류: {e}", status_text="상태: 오류")
        self.call_from_thread(self._focus_menu)

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_partner_setup(self) -> None:
        """4번 메뉴: 상대방 설정"""
        try:
            sheet = character_setup.partner_sheet()
            self.call_from_thread(self._update_ui, editor_text=sheet, status_text="상태: 상대방 설정 표시 중", readonly=True)
        except Exception as e:
            self.call_from_thread(self._update_ui, editor_text=f"상대방 시트 오류: {e}", status_text="상태: 오류")
        self.call_from_thread(self._focus_menu)

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_generate_episode(self) -> None:
        """5번 메뉴: 에피소드 생성 백그라운드 스레드"""
        self.call_from_thread(self._update_ui, status_text="상태: 에피소드 생성 중... [Ctrl+C]: 중단 | [Ctrl+Q]: 종료")
        progress_log = []

        def episode_callback(response_text: str, info: dict):
            total = info.get("total_episodes", 0)
            current = info.get("current_episode", 0)
            ep_status = info.get("status", "")
            msg = f"[에피소드 {current}/{total}] {ep_status}"
            progress_log.append(msg)

            if self._interrupt_flag:
                txt = f"[5번] 중단 요청됨!\n\n진행: {current}/{total}\n\n{response_text[:500]}...\n\n[최근 로그]\n" + "\n".join(progress_log[-10:])
                self.call_from_thread(self._update_ui, editor_text=txt, status_text="상태: 중단됨!")
                return

            txt = f"[5번] 에피소드 생성 진행 중...\n\n진행: {current}/{total} ({ep_status})\n\n{response_text[:500]}...\n\n[최근 로그]\n" + "\n".join(progress_log[-10:])
            self.call_from_thread(self._update_ui, editor_text=txt, status_text=f"상태: 에피소드 생성 - {msg}")

        try:
            prog_msg = self._generate_and_parse_progression()
            use_extended = config.json_value.get("extended", "no") == "yes"

            if use_extended:
                jinshugai_list = getattr(config, 'theme_jinshugai', None)
                if jinshugai_list and len(jinshugai_list) > 0:
                    template_id = jinshugai_list[0].get('id', rand.randint(1, 10))
                else:
                    template_id = rand.randint(1, 10)
                theme_msg = getattr(config, 'plot', '')
                total_eps = config.total_episodes
                template_name = plot_gen.TEMPLATES[template_id]['name']

                init_txt = f"[5번] [Extended] plot_gen_extended 호출 중...\n\n템플릿: {template_id}. {template_name}\n에피소드: {total_eps}개\n테마: {theme_msg}\n\nAPI 응답 대기 중 (약 1-2분)"
                self.call_from_thread(self._update_ui, editor_text=init_txt, status_text="상태: plot_gen_extended 호출 중...")

                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                try:
                    plot_result = plot_gen.plot_gen_extended(
                        template_id=template_id,
                        total_episodes=total_eps,
                        theme_msg=theme_msg,
                        breeds_data=getattr(config, 'theme_breeds', None),
                        jinshugai_templates=getattr(config, 'theme_jinshugai', None),
                        progression_events=getattr(config, 'theme_events', None),
                        callback=episode_callback
                    )
                finally:
                    sys.stdout = old_stdout

                episodes = llm_novel_gui_func.split_episodes(plot_result)
                for i in range(total_eps):
                    if i < len(episodes):
                        config.episode_content[i] = episodes[i]
                    else:
                        config.episode_content[i] = ""
                    config.episode_track[i] = True

                config.episode_gen_flag = True
                self.call_from_thread(self._update_ui, editor_text=f"{plot_result}\n\n{prog_msg}", status_text="상태: 에피소드 생성 완료 (extended) | [E]: 편집 모드 토글", readonly=False)
            else:
                self.call_from_thread(self._update_ui, editor_text="[5번] episode_gen 호출 중...\nAPI 응답 대기 중 (약 1-2분)", status_text="상태: episode_gen 호출 중...")

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
                    if i < len(episodes):
                        config.episode_content[i] = episodes[i]
                    else:
                        config.episode_content[i] = ""
                    config.episode_track[i] = True

                config.episode_gen_flag = True
                self.call_from_thread(self._update_ui, editor_text=f"{result_text}\n\n{prog_msg}", status_text="상태: 에피소드 생성 완료 | [E]: 편집 모드 토글", readonly=False)

        except Exception as e:
            self.call_from_thread(self._update_ui, editor_text=f"에피소드 생성 중 오류: {e}", status_text="상태: 오류")
        self.call_from_thread(self._focus_menu)

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_generate_refine(self) -> None:
        """6번 메뉴: 생성 및 보완 백그라운드 스레드"""
        self.call_from_thread(self._update_ui, status_text="상태: 생성 및 보완 중... [Ctrl+C]: 중단 | [Ctrl+Q]: 종료")
        progress_log = []

        def refine_callback(response_text: str, info: dict):
            total = info.get("total_episodes", 0)
            current = info.get("current_episode", 0)
            ep_status = info.get("status", "")
            msg = f"[에피소드 {current}/{total}] {ep_status}"
            progress_log.append(msg)

            if self._interrupt_flag:
                txt = f"[6번] 중단 요청됨!\n\n진행: {current}/{total}\n\n{response_text[:500]}...\n\n[최근 로그]\n" + "\n".join(progress_log[-10:])
                self.call_from_thread(self._update_ui, editor_text=txt, status_text="상태: 중단됨!")
                return

            txt = f"[6번] 생성 및 보완 진행 중...\n\n진행: {current}/{total} ({ep_status})\n\n{response_text[:500]}...\n\n[최근 로그]\n" + "\n".join(progress_log[-10:])
            self.call_from_thread(self._update_ui, editor_text=txt, status_text=f"상태: 생성 및 보완 - {msg}")

        try:
            final_result = story_gen.episode_summary_gen(callback=refine_callback)
            episodes = llm_novel_gui_func.split_episodes(final_result)

            if config.episode_content and config.episode_content[0]:
                out_txt = f"## EPISODE 1 ##\n\n{config.episode_content[0]}"
            elif episodes:
                out_txt = episodes[0]
            else:
                out_txt = final_result

            self.call_from_thread(self._update_ui, editor_text=out_txt, status_text=f"상태: 생성 및 보완 완료 ({len(episodes)}개 에피소드) | [E]: 편집 모드 토글", readonly=False)
        except Exception as e:
            self.call_from_thread(self._update_ui, editor_text=f"생성 및 보완 중 오류: {e}", status_text="상태: 오류")
        self.call_from_thread(self._focus_menu)

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_generate_story(self) -> None:
        """7번 메뉴: 스토리 생성 백그라운드 스레드"""
        self.call_from_thread(self._update_ui, status_text="상태: 스토리 생성 중... [Ctrl+C]: 중단 | [Ctrl+Q]: 종료")
        progress_log = []

        def story_callback(response_text: str, info: dict):
            total = info.get("total_episodes", 0)
            current = info.get("current_episode", 0)
            ep_status = info.get("status", "")
            msg = f"[에피소드 {current}/{total}] {ep_status}"
            progress_log.append(msg)

            if self._interrupt_flag:
                txt = f"[7번] 중단 요청됨!\n\n진행: {current}/{total}\n\n{response_text[:800]}...\n\n[최근 로그]\n" + "\n".join(progress_log[-10:])
                self.call_from_thread(self._update_ui, editor_text=txt, status_text="상태: 중단됨!")
                return

            txt = f"[7번] 스토리 생성 진행 중...\n\n진행: {current}/{total} ({ep_status})\n\n{response_text[:800]}...\n\n[최근 로그]\n" + "\n".join(progress_log[-10:])
            self.call_from_thread(self._update_ui, editor_text=txt, status_text=f"상태: 스토리 생성 - {msg}")

        try:
            import full_episode_gen
            result = full_episode_gen.full_episode_gen(ep_num=0, callback=story_callback)

            table = llm_novel_gui_func.build_episode_full_track_table()
            out_txt = f"{table}\n\n[최근 로그]\n" + "\n".join(progress_log[-20:])
            self.call_from_thread(self._update_ui, editor_text=out_txt, status_text="상태: 스토리 생성 완료 | [E]: 편집 모드 토글", readonly=False)
        except Exception as e:
            self.call_from_thread(self._update_ui, editor_text=f"스토리 생성 중 오류: {e}", status_text="상태: 오류")
        self.call_from_thread(self._focus_menu)

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_export_config(self) -> None:
        """8번 메뉴: 설정 내보내기"""
        try:
            filepath = os.path.join("data", "config_export.yaml")
            result = llm_novel_gui_func.export_config_to_file(filepath)
            self.call_from_thread(self._update_ui, editor_text=f"{result}\n\n파일: {filepath}", status_text="상태: 설정 내보내기 완료", readonly=True)
        except Exception as e:
            self.call_from_thread(self._update_ui, editor_text=f"설정 내보내기 오류: {e}", status_text="상태: 오류")
        self.call_from_thread(self._focus_menu)

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_restore_config(self) -> None:
        """9번 메뉴: 설정 복구"""
        try:
            filepath = os.path.join("data", "config_export.yaml")
            result = llm_novel_gui_func.restore_config_from_file(filepath)
            self.call_from_thread(self._update_ui, editor_text=f"{result}", status_text="상태: 설정 복구 완료", readonly=True)
        except Exception as e:
            self.call_from_thread(self._update_ui, editor_text=f"설정 복구 오류: {e}", status_text="상태: 오류")
        self.call_from_thread(self._focus_menu)

    @work(thread=True, exclusive=True, group="llm_work")
    def _worker_auto_run(self) -> None:
        """10번 메뉴: 전체 자동 실행 백그라운드 스레드"""
        self.call_from_thread(self._update_ui, status_text="상태: 전체 자동 실행 중... [Ctrl+C]: 중단 | [Ctrl+Q]: 종료")

        try:
            import anima_gen_control
            anima_enb = config.json_value.get("anima_enb", "no")
            anima_enb = anima_enb in ("yes", True, "1")

            episode_files = []
            episode_json_path = os.path.join("data", "episode_setup.json")
            try:
                import json
                with open(episode_json_path, "r", encoding="utf-8") as f:
                    episode_data = json.load(f)
                episode_files = episode_data.get("files", [])
            except Exception:
                pass

            def console_callback(step: str, status_msg: str, content_text: str):
                if self._interrupt_flag:
                    txt = f"[10번] 중단 요청됨!\n\n[{status_msg}]\n{content_text}"
                    self.call_from_thread(self._update_ui, editor_text=txt, status_text="상태: 중단됨!")
                    return
                txt = f"[{status_msg}]\n{content_text}"
                self.call_from_thread(self._update_ui, editor_text=txt, status_text=f"상태: 자동 실행 - {status_msg}")

            result = anima_gen_control.run_auto_sequence(
                episode_files=episode_files,
                current_file_index=0,
                anima_enb=anima_enb,
                callback=console_callback,
            )

            if result["success"]:
                self.call_from_thread(self._update_ui, editor_text=f"전체 자동 실행 완료!\n\n{result['content_text']}", status_text="상태: 자동 실행 완료", readonly=True)
            else:
                self.call_from_thread(self._update_ui, editor_text=f"자동 실행 오류:\n{result['content_text']}", status_text="상태: 자동 실행 오류")
        except Exception as e:
            self.call_from_thread(self._update_ui, editor_text=f"자동 실행 중 오류: {e}", status_text="상태: 오류")
        self.call_from_thread(self._focus_menu)

    # -------------------------------------------------------------------------
    # 사용자 키 및 포커스 이벤트
    # -------------------------------------------------------------------------
    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """오른쪽 텍스트 에디터에서 글자를 타이핑할 때 발생하는 이벤트"""
        status = self.query_one("#status-bar", Label)
        status.update(f"상태: 텍스트 입력 중... (현재 글자 수: {len(event.text_area.text)})")

    def on_focus(self, event) -> None:
        """포커스 변경 알림 처리"""
        menu = self.query_one("#menu", OptionList)
        editor = self.query_one("#editor", TextArea)

        if event.id == "editor":
            status = self.query_one("#status-bar", Label)
            status.update(f"상태: 텍스트 입력 중... (현재 글자 수: {len(editor.text)})")

        if event.id == "menu":
            status = self.query_one("#status-bar", Label)
            highlighted = menu.highlighted
            if highlighted is not None:
                option = menu.get_option_at_index(highlighted)
                if option:
                    status.update(f"상태: 메뉴 탐색 중 - '{option.prompt}'")

    def on_key(self, event) -> None:
        """키 입력 처리: [E] 편집 모드 토글, [TAB] 방지, [Ctrl+C] 중단, [Ctrl+Q] 즉시 종료"""
        editor = self.query_one("#editor", TextArea)
        status = self.query_one("#status-bar", Label)

        # TAB 이동 방지
        if event.key in ("tab", "shift_tab"):
            event.prevent_default()
            return

        # Ctrl+C: 진행 중인 워커 그룹 취소 및 중단 플래그 설정
        if event.key == "ctrl+c":
            self._interrupt_flag = True
            self.workers.cancel_group(self, "llm_work") # Textual 워커 그룹 즉시 중단
            status.update("상태: 중단 요청 중...")
            return

        # Ctrl+Q: 프로그램 강제 종료
        if event.key == "ctrl+q":
            status.update("상태: 종료 중...")
            self.exit()
            return

        # E키를 누르면 편집 모드 토글 (읽기 전용 / 편집 가능)
        if event.key in ("e", "E"):
            # 에디터에 포커스가 주어져 입력 중일 때는 E키 토글 방지
            if self.focused == editor:
                return
            editor.readonly = not editor.readonly
            if editor.readonly:
                status.update(f"상태: 읽기 전용 모드 (현재 글자 수: {len(editor.text)})")
            else:
                status.update(f"상태: 편집 모드 (현재 글자 수: {len(editor.text)}) | [E]: 편집 종료")
            editor.focus()

if __name__ == "__main__":
    app = FourPaneApp()
    app.run()
