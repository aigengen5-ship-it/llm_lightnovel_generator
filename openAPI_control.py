"""
OpenAI API 호출 공통 모듈

theme_gen_auto.py, full_episode_gen.py, plot_gen.py, anima_gen.py, story_gen.py에서
사용하는 API 호출 함수들을 통합 관리합니다.

함수 목록:
- get_openai_client()          : Main LLM 클라이언트 생성
- call_openai_api()            : 스트리밍 응답 (story_gen용)
- call_openai_for_plot()       : 비스트리밍 응답 (plot_gen용)
- openAI_response()            : ANIMA용 간단한 호출
"""

import os
import time
import random as rand
from openai import OpenAI, APITimeoutError, APIStatusError, APIConnectionError

import config


# =====================================================================
# 모델 id 결정
# =====================================================================

# plot.json 의 mainLLM 값 → 서버가 서빙하는 모델 id 매핑 (기존 동작)
LLM_MODEL_MAP = {"gemma": "gemma-4-31B-it", "qwen": "Qwen/Qwen3.8-27B"}


def resolve_model() -> str:
    """chat.completions 에 보낼 모델 id 를 결정한다 (plot.json 기준).

    1) `model_main` : 지정하면 그대로 사용. 서버의 `/v1/models` id 와 일치해야 한다.
       (서버가 다른 id 로 서빙될 때 코드 수정 없이 대응하기 위한 탈출구)
    2) `mainLLM`    : "qwen" → Qwen/Qwen3.8-27B, 그 외 → gemma-4-31B-it (기존 동작 유지)

    참고: plot/variables.json 의 api_settings.model 은 어느 쪽에서도 읽지 않는 죽은 값이다.
    """
    jv = config.get_json_value()
    override = str(jv.get("model_main", "") or "").strip()
    if override:
        return override
    main_llm = str(jv.get("mainLLM", "gemma") or "gemma").strip().lower()
    return LLM_MODEL_MAP.get(main_llm, "gemma-4-31B-it")


def resolve_timeout(default: float = 600.0) -> float:
    """스트리밍(story_gen/full_episode_gen) 호출의 요청 타임아웃(초). plot.json 기준.

    reasoning 모델은 완료 토큰의 70% 이상이 사고에 쓰여 1회 호출에 200초를 넘기는 일이 많다
    (실측: 캐릭터 시트 업데이트 1회 179~216초, completion 4109 중 reasoning 3261).
    기존에는 300초 하드코딩이었다.
    """
    try:
        v = float(config.get_json_value().get("timeout_main", default))
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default


# =====================================================================
# 클라이언트 생성
# =====================================================================

def get_openai_client() -> OpenAI:
    """Main LLM용 OpenAI 클라이언트를 생성하여 반환합니다."""
    api_key = os.environ.get("OPENAI_API_KEY", "gemma-4-31b")
    return OpenAI(
        base_url="http://" + config.get_json_value().get("ip_main", "192.168.1.162") + ":" + config.get_json_value()["port_main"] + "/v1",
        api_key=api_key,
        # [D7] SDK 기본 max_retries=2 를 끈다. 재시도는 아래 call_openai_* 의 루프가 혼자 담당해야
        #      대기 시간이 예측 가능하다(켜두면 요청 1회 자체가 내부 3회로 불어난다).
        max_retries=0,
    )


# =====================================================================
# call_openai_api (스트리밍 응답 - story_gen / full_episode_gen 용)
# =====================================================================

def call_openai_api(prompt_text: str, callback=None, info_lines=None, log_fn=None) -> str:
    """OpenAI API를 호출하여 스트리밍 응답을 반환하고 전체 응답 텍스트를 반환합니다.

    Args:
        prompt_text: 보낼 프롬프트 텍스트.
        callback: 스트리밍 중 호출될 콜백 함수 (text, info_lines).
        info_lines: 콜백에 전달할 추가 정보 딕셔너리.
        log_fn: (msg: str) -> None 형태로 로깅 함수를 전달합니다. (토큰 사용량 등)

    Returns:
        전체 응답 텍스트.
    """
    client = get_openai_client()

    config.messages_history.append({"role": "user", "content": prompt_text})

    temp = 0.9 + rand.randint(0, 1) / 10.0
    top_p = 0.95
    repeat_penalty = 1.15
    top_k = 64

    max_try = 0
    timeout_check = 0

    while timeout_check == 0:
        try:
            response = client.chat.completions.create(
                model=resolve_model(),
                stream_options={"include": True} if config.stream_enb else None,
                messages=config.messages_history,
                temperature=temp,
                top_p=top_p,
                stream=config.stream_enb,
                timeout=resolve_timeout(),
                extra_body={"repeat_penalty": repeat_penalty, "top_k": top_k}
            )
            timeout_check = 1
        except APITimeoutError:
            print("서버 응답 시간이 초과되었습니다. 다시 시도합니다")
            if log_fn:
                log_fn(f"[TIMEOUT] 서버 응답 시간 초과. 재시도 ({max_try + 1}/3)")
            timeout_check = 0
            max_try += 1
            time.sleep(10)
            if max_try > 3:
                print("서버 죽음")
                exit()
        except APIConnectionError as e:
            # [D5] 서버 다운/접속 거부는 APITimeoutError와 다른 계층(APIConnectionError)이라
            #      기존 코드에서는 무처리 크래시했다. 타임아웃과 동일하게 재시도 후 종료.
            print(f"서버 연결 실패: {e}. 다시 시도합니다 ({max_try + 1}/3)")
            if log_fn:
                log_fn(f"[CONN_ERROR] 서버 연결 실패. 재시도 ({max_try + 1}/3): {e}")
            timeout_check = 0
            max_try += 1
            time.sleep(10)
            if max_try > 3:
                print("서버 죽음")
                exit()
        except APIStatusError as e:
            print(f"API 에러 ({e.status_code}): {e.message}")
            if log_fn:
                log_fn(f"[API_ERROR] {e.status_code}: {e.message}")
            timeout_check = 0
            max_try += 1
            time.sleep(5)
            if max_try > 3:
                print("서버 죽음")
                exit()

    # 스트리밍 처리
    if config.stream_enb:
        full_response = ""
        for chunk in response:
            if log_fn and chunk.usage:
                log_fn(f"[TOKEN] Prompt: {chunk.usage.prompt_tokens}, "
                       f"Completion: {chunk.usage.completion_tokens}, "
                       f"Total: {chunk.usage.total_tokens}")
            if chunk.choices and chunk.choices[0].delta.content:
                delta = chunk.choices[0].delta.content
                full_response += delta
                if callback:
                    callback(delta, info_lines)
        config.messages_history.append({"role": "assistant", "content": full_response})
        return full_response
    else:
        result = response.choices[0].message.content or ""
        config.messages_history.append({"role": "assistant", "content": result})
        return result


# =====================================================================
# call_openai_for_plot (비스트리밍 - plot_gen 용)
# =====================================================================

def call_openai_for_plot(prompt_text: str, system_prompt: str = None, messages: list = None, log_fn=None,
                         temperature: float = None, timeout: float = None,
                         repeat_penalty: float = None, max_retries: int = None,
                         retry_delay: float = None) -> tuple:
    """OpenAI API를 호출하여 플롯 생성 응답을 반환합니다.
    messages가 제공되면 대화 이력을 유지합니다 (원본 리스트는 변형되지 않음).
    log_fn: (msg: str) -> None 형태로 로깅 함수를 전달합니다.
    temperature: 지정 시 해당 값 사용 (기본: 0.9 + rand)
    timeout: 지정 시 해당 값 사용 (기본: 400.0)
    repeat_penalty: 지정 시 해당 값 사용 (기본: 1.15)
    max_retries: 재시도 횟수 (기본: 3)
    retry_delay: 재시도 대기 시간 (기본: 10)

    Returns:
        (result: str, messages: list) — 업데이트된 messages 리스트를 함께 반환
    """
    client = get_openai_client()

    # mainLLM 설정 확인 (plot.json)
    main_llm = config.get_json_value().get("mainLLM", "gemma").strip().lower()

    if system_prompt is None:
        system_prompt = config.system_prompt

    if messages is None:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ]
    else:
        messages = list(messages)  # 원본 리스트 변형 방지
        messages.append({"role": "user", "content": prompt_text})

    if temperature is None:
        temperature = 0.9 + rand.randint(0, 1) / 10.0
    if timeout is None:
        timeout = 400.0
    if max_retries is None:
        max_retries = 3
    if retry_delay is None:
        retry_delay = 10

    top_p = 0.95

    # 모델별 파라미터 설정
    # [모델 결정 통합] 모델 id 는 resolve_model() 가 정하고, 아래 분기는 파라미터 조합만 결정한다
    model = resolve_model()

    if main_llm == "qwen":
        extra_body = {
            "chat_template_kwargs": {
                "enable_thinking": True,
                "preserve_thinking": True,
            },
        }
        reasoning_effort = "medium"
        if log_fn:
            log_fn(f"[PLOT_PROMPT] model={model}, reasoning={reasoning_effort}, temp={temperature:.2f}\n{prompt_text}")
    else:
        if repeat_penalty is None:
            repeat_penalty = 1.15
        top_k = 64
        extra_body = {"repeat_penalty": repeat_penalty, "top_k": top_k}
        reasoning_effort = None
        if log_fn:
            log_fn(f"[PLOT_PROMPT] model={model}, temp={temperature:.2f}\n{prompt_text}")

    max_try = 0
    timeout_check = 0

    while timeout_check == 0:
        try:
            create_kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "top_p": top_p,
                "stream": False,
                "timeout": timeout,
                "extra_body": extra_body,
            }
            if reasoning_effort:
                create_kwargs["reasoning_effort"] = reasoning_effort

            response = client.chat.completions.create(**create_kwargs)
            timeout_check = 1
        except APITimeoutError:
            print(f"서버 응답 시간이 초과되었습니다. 다시 시도합니다 ({max_try + 1}/{max_retries})")
            if log_fn:
                log_fn(f"[TIMEOUT] 서버 응답 시간 초과. 재시도 ({max_try + 1}/{max_retries})")
            timeout_check = 0
            max_try += 1
            time.sleep(retry_delay)
            if max_try > max_retries:
                if log_fn:
                    log_fn(f"[ERROR] 서버 응답 실패 ({max_retries}회 재시도 후)")
                return "서버 응답 실패", messages

        except APIConnectionError as e:
            # [D5] 접속 거부/서버 다운도 타임아웃과 동일하게 처리하여 호출부로 넘긴다
            #      (호출부는 "서버 응답 실패"를 받아 기존 상태 유지를 유지한다).
            print(f"서버 연결 실패: {e}. 다시 시도합니다 ({max_try + 1}/{max_retries})")
            if log_fn:
                log_fn(f"[CONN_ERROR] 서버 연결 실패. 재시도 ({max_try + 1}/{max_retries}): {e}")
            timeout_check = 0
            max_try += 1
            time.sleep(retry_delay)
            if max_try > max_retries:
                if log_fn:
                    log_fn(f"[ERROR] 서버 연결 실패 ({max_retries}회 재시도 후)")
                return "서버 응답 실패", messages

        except APIStatusError as e:
            # [D6] 모델명 오탈자/미서빙(404) 같은 4xx 는 재시도로 복구되지 않는다.
            #      그대로 올리되, 원인을 한 눈에 볼 있게 서버 메시지/모델/주소를 로그에 남긴다.
            msg = (f"[API_ERROR] HTTP {e.status_code} (model={model}, base_url="
                   f"{str(client.base_url)}): {getattr(e, 'message', e)}")
            print(msg)
            if log_fn:
                log_fn(msg)
            raise

    result = (response.choices[0].message.content or "").strip()
    messages.append({"role": "assistant", "content": result})

    if log_fn:
        log_fn(f"[PLOT_RESULT]\n{result}")

    return result, messages


# =====================================================================
# openAI_response (ANIMA용 간단한 호출)
# =====================================================================

def openAI_response(json_value, client, messages_history, user_input, op_mode, chat1, call_label=""):
    """OpenAI API 호출 함수 (ANIMA용).

    Args:
        json_value: 설정 JSON
        client: OpenAI 클라이언트
        messages_history: 메시지 히스토리
        user_input: 사용자 입력
        op_mode: 운영 모드 (미사용 유지)
        chat1: 채팅 모드 (미사용 유지)
        call_label: API 호출 라벨 (로깅용)

    Returns:
        (messages_history, full_response)
    """
    model_map = {
        "gemma": "gemma-4-31B-it",
        "qwen35": "qwen3-27b",
    }
    raw_model = json_value.get("anima_agent", "gemma")
    model = model_map.get(raw_model, raw_model)

    messages = messages_history + [{"role": "user", "content": user_input}]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7
        )
        full_response = response.choices[0].message.content or ""
    except Exception as e:
        if call_label:
            print(f"  [에러] {call_label}: {e}")
        raise

    messages_history = messages + [{"role": "assistant", "content": full_response}]
    return messages_history, full_response
