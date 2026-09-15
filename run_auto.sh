#!/bin/bash
cd "$(dirname "$0")"
rm -f *.log

# [D3] 실행용 Python 자동 선택 — 기존 `source ../venv/bin/activate` 대체.
#   ../venv 가 요구 모듈(openai/prompt_toolkit/PyYAML/textual)을 갖추면 거기서 선택되어
#   기존 동작과 동일하고, 그렇지 않은 환경에서는 실패하지 않고 동작하는 해석기를 찾는다.
source "$(dirname "$0")/select_python.sh"

# [Phase C] 3인자 스위치 (-chr_num3) — 미지정/0 = 기존 2인 모드
#   사용법: ./run_auto.sh -chr_num3 1     또는     CHR_NUM3=1 ./run_auto.sh
CHR_NUM3="${CHR_NUM3:-}"
while [[ $# -gt 0 ]]; do
    case $1 in
        -chr_num3)
            CHR_NUM3="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

CMD="$PYTHON_BIN llm_novel_gui.py --auto"
if [ -n "$CHR_NUM3" ]; then
    CMD="$CMD -chr_num3 $CHR_NUM3"
fi

nohup $CMD > auto_run.log 2>&1 &
echo "PID: $!"
