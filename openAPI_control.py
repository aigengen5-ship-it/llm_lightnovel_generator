"""
OpenAI API 호출 공통 모듈

theme_gen_auto.py, full_episode_gen.py, plot_gen.py, anima_gen.py, story_gen.py에서
사용하는 API 호출 함수들을 통합 관리합니다.

함수 목록:
- get_openai_client()          : Main LLM 클라이언트 생성
- get_openai_client_agent()    : Agent LLM 클라이언트 생성
- call_openai_api()            : 스트리밍 응답 (story_gen용)
- call_openai_for_plot()       : 비스트리밍 응답 (plot_gen용)
- call_openai_for_client()     : Agent용 (llama_server 재시동 포함)
- openAI_response()            : ANIMA용 간단한 호출
"""

import os
import time
import random as rand
from openai import OpenAI, APITimeoutError, APIStatusError

import config

# 현재 활성 agent 추적 (agent 변경 시에만 llama 재시동)
_current_active_agent: str | None = None


# =====================================================================
# 클라이언트 생성
# =====================================================================

def get_openai_client() -> OpenAI:
    """Main LLM용 OpenAI 클라이언트를 생성하여 반환합니다."""
    api_key = os.environ.get("OPENAI_API_KEY", "gemma-4-31b")
    return OpenAI(
        base_url="http://" + config.json_value.get("ip_main", "192.168.1.162") + ":" + config.json_value["port_main"] + "/v1",
        api_key=api_key
    )


def get_openai_client_agent() -> OpenAI:
    """Agent LLM용 OpenAI 클라이언트를 생성하여 반환합니다."""
    api_key = os.environ.get("OPENAI_API_KEY", "gemma-4-31b")
    return OpenAI(
        base_url=f"http://{config.json_value.get('ip_agent', '127.0.0.1')}:{config.json_value.get('port_agent', '8081')}/v1",
        api_key=api_key
    )


# =====================================================================
# call_openai_api (스트리밍 응답 - story_gen / full_episode_gen 용)
# =====================================================================

def call_openai_api(prompt_text: str, callback=None, info_lines=None) -> str:
    """OpenAI API를 호출하여 스트리밍 응답을 반환하고 전체 응답 텍스트를 반환합니다.

    Args:
        prompt_text: 보낼 프롬프트 텍스트.
        callback: 스트리밍 중 호출될 콜백 함수 (text, info_lines).
        info_lines: 콜백에 전달할 추가 정보 딕셔너리.

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
                model="gemma-4-31B-it",
                stream_options={"include": True} if config.stream_enb else None,
                messages=config.messages_history,
                temperature=temp,
                top_p=top_p,
                stream=config.stream_enb,
                timeout=300.0,
                extra_body={"repeat_penalty": repeat_penalty, "top_k": top_k}
            )
            timeout_check = 1
        except APITimeoutError:
            print("서버 응답 시간이 초과되었습니다. 다시 시도합니다")
            timeout_check = 0
            max_try += 1
            time.sleep(10)
            if max_try > 3:
                print("서버 죽음")
                exit()
        except APIStatusError as e:
            print(f"API 에러 ({e.status_code}): {e.message}")
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
            if chunk.choices and chunk.choices[0].delta.content:
                delta = chunk.choices[0].delta.content
                full_response += delta
                if callback:
                    callback(delta, info_lines)
        config.messages_history.append({"role": "assistant", "content": full_response})
        return full_response
    else:
        result = response.choices[0].message.content
        config.messages_history.append({"role": "assistant", "content": result})
        return result


# =====================================================================
# call_openai_for_plot (비스트리밍 - plot_gen 용)
# =====================================================================

def call_openai_for_plot(prompt_text: str, system_prompt: str = None, messages: list = None, log_fn=None) -> str:
    """OpenAI API를 호출하여 플롯 생성 응답을 반환합니다.
    messages가 제공되면 대화 이력을 유지합니다.
    log_fn: (msg: str) -> None 형태로 로깅 함수를 전달합니다.
    """
    client = get_openai_client()

    if system_prompt is None:
        system_prompt = config.system_prompt

    if messages is None:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ]
    else:
        messages.append({"role": "user", "content": prompt_text})

    temp = 0.9 + rand.randint(0, 1) / 10.0
    top_p = 0.95
    repeat_penalty = 1.15
    top_k = 64

    if log_fn:
        log_fn(f"[PLOT_PROMPT] temp={temp:.2f}\n{prompt_text}")

    max_try = 0
    timeout_check = 0

    while timeout_check == 0:
        try:
            response = client.chat.completions.create(
                model="gemma-4-31B-it",
                messages=messages,
                temperature=temp,
                top_p=top_p,
                stream=False,
                timeout=400.0,
                extra_body={"repeat_penalty": repeat_penalty, "top_k": top_k}
            )
            timeout_check = 1
        except APITimeoutError:
            print(f"서버 응답 시간이 초과되었습니다. 다시 시도합니다 ({max_try + 1}/3)")
            timeout_check = 0
            max_try += 1
            time.sleep(10)
            if max_try > 3:
                return "서버 응답 실패"

    result = response.choices[0].message.content.strip()
    messages.append({"role": "assistant", "content": result})

    if log_fn:
        log_fn(f"[PLOT_RESULT]\n{result}")

    return result


def call_openai_for_client(prompt_text: str, system_prompt: str = None, messages: list = None, log_fn=None, agent=None) -> str:
    """에이전트용 OpenAI API를 호출하여 응답을 반환합니다.
    (plot.json의 ip_agent, port_agent, agent 항목 참조)
    - agent가 'meromero'이면 G4-MeroMero-31B 모델 사용 (temp=1.0, gemma 변형)
    - agent가 'qwen'이면 qwen3-32B 모델 사용 (temp=0.5)
    messages가 제공되면 대화 이력을 유지합니다.
    log_fn: (msg: str) -> None 형태로 로깅 함수를 전달합니다.
    agent: 직접 지정된 에이전트 이름. None이면 config.json_value의 agent 사용.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "gemma-4-31b")
    if agent is None:
        agent_type = config.json_value.get("agent", "qwen").strip().lower()
    else:
        agent_type = agent.strip().lower()

    # agent 타입에 따라 모델과 temperature 설정
    model_map = {
        "gemma": "gemma-4-31B-it",
        "meromero": "gemma-4-31B-it",
        "qwen": "qwen3-32B",
        "qwen3": "qwen3-32B",
        "qwen35": "qwen3-27b",
        "localhost": "gemma-4-31B-it",
    }
    model = model_map.get(agent_type, agent_type)
    temp = 1.0 if agent_type == "meromero" else 0.5 if agent_type.startswith("qwen") else 0.8
    client = get_openai_client_agent()

    if system_prompt is None:
        system_prompt = (
            "You are an expert love-comedy light novel editor and critic specializing in cosmic horror "
            "Provide detailed feedback on plot consistency, theme integration, character relationships, "
            "and episode flow. Always answer in Korean."
        )

    if messages is None:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ]
    else:
        messages.append({"role": "user", "content": prompt_text})

    top_p = 0.95
    repeat_penalty = 1.1
    top_k = 64

    if log_fn:
        log_fn(f"[CLIENT_PROMPT] model={model}, temp={temp:.2f}\n{prompt_text}")

    max_try = 0
    timeout_check = 0

    while timeout_check == 0:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temp,
                top_p=top_p,
                stream=False,
                timeout=300.0,
                extra_body={"repeat_penalty": repeat_penalty, "top_k": top_k}
            )
            timeout_check = 1
        except (APITimeoutError, Exception) as e:
            print(f"에이전트 서버 응답 시간 초과/에러: {e}. 재시도 ({max_try + 1}/3)")
            timeout_check = 0
            max_try += 1
            time.sleep(10)
            if max_try > 3:
                return "에이전트 서버 응답 실패"

    result = response.choices[0].message.content.strip()
    messages.append({"role": "assistant", "content": result})

    if log_fn:
        log_fn(f"[CLIENT_RESULT]\n{result}")

    return result


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
        full_response = response.choices[0].message.content
    except Exception as e:
        if call_label:
            print(f"  [에러] {call_label}: {e}")
        raise

    messages_history = messages + [{"role": "assistant", "content": full_response}]
    return messages_history, full_response
