#!/bin/bash
# =============================================================================
# [D3] 프로젝트 실행용 Python 해석기 자동 선택
#
# requirements.txt 요구: openai / prompt_toolkit / PyYAML(yaml) / textual
# 이 머신에서는 ../venv 가 torch/rocm 전용 복사본이라 위 패키지 전무,
# PATH 에도 `python` 이 없는 환경이 확인되었다(= run_main.sh 가 그 자체로 실패).
# 그래서 "요구 모듈이 실제로 import 되는" 해석기를 후보 순서대로_probe_하여 고른다.
#
# 후보 순서 (앞이 우선):
#   1) $PYTHON            사용자가 명시적으로 지정한 경로
#   2) ../venv/bin/python3 기존 관례 (정상 머신이면 여기서 통과 → 기존 동작과 동일)
#   3) $HOME/AI/.venv/bin/python3  이 체크아웃에서 실제로 요구 패키지를 갖춘 venv
#   4) python3 / python   PATH 의 시스템 파이썬
#
# 사용: run_main.sh / run_auto.sh 에서
#         source "$(dirname "$0")/select_python.sh"
#       후 $PYTHON_BIN 을 해석기로 사용한다.
# =============================================================================

PY_REQUIRE='import openai, yaml, textual, prompt_toolkit'
PYTHON_BIN=""
PYTHON_PROBE_LOG=""

for _cand in "${PYTHON:-}" "../venv/bin/python3" "../venv/bin/python" \
             "$HOME/AI/.venv/bin/python3" "$(command -v python3 2>/dev/null)" \
             "$(command -v python 2>/dev/null)"; do
    [ -n "$_cand" ] || continue
    # 실행 가능 파일이거나 PATH 상의 명령이어야 한다
    if [ ! -x "$_cand" ] && ! command -v "$_cand" >/dev/null 2>&1; then
        PYTHON_PROBE_LOG="${PYTHON_PROBE_LOG}  x ${_cand} (실행 불가)\n"
        continue
    fi
    if "$_cand" -c "$PY_REQUIRE" >/dev/null 2>&1; then
        PYTHON_BIN="$_cand"
        PYTHON_PROBE_LOG="${PYTHON_PROBE_LOG}  O ${_cand} (요구 모듈 충족)\n"
        break
    fi
    _missing=$("$_cand" -c "$PY_REQUIRE" 2>&1 | grep -oE "No module named '[^']+'" | head -1)
    PYTHON_PROBE_LOG="${PYTHON_PROBE_LOG}  x ${_cand} (${_missing:-요구 모듈 일부 누락})\n"
done
unset _cand _missing

if [ -z "$PYTHON_BIN" ]; then
    echo "[select_python] requirements.txt 의 openai/prompt_toolkit/PyYAML/textual 을 갖춘 Python 을 찾지 못했습니다."
    echo "[select_python] 시도한 후보:"
    echo -e "$PYTHON_PROBE_LOG"
    echo "[select_python] 대안: PYTHON=/path/to/python ./run_main.sh 로 직접 지정하세요."
    exit 1
fi

export PYTHON_BIN
