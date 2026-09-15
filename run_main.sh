#!/bin/bash
cd "$(dirname "$0")"
rm -f *.log
rm -f log/*.*

# [D3] 실행용 Python 자동 선택 (../venv 가 요구 패키지를 갖추지 못한 환경에서도 동작)
#   기존 관례(../venv)가 정상이면 거기서 통과하므로 동작이 그대로다.
source "$(dirname "$0")/select_python.sh"

# 인자 파싱
JINSHUGAI_ID=""
INC_FLAG=""
JOB=""
JOB2=""
CHR_NUM3=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -id)
            JINSHUGAI_ID="$2"
            shift 2
            ;;
        -inc_flag)
            INC_FLAG="$2"
            shift 2
            ;;
        -job)
            JOB="$2"
            shift 2
            ;;
        -job2)
            JOB2="$2"
            shift 2
            ;;
        -chr_num3)
            CHR_NUM3="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

CMD="$PYTHON_BIN llm_novel_gui_textual.py"
if [ -n "$JINSHUGAI_ID" ]; then
    CMD="$CMD -id $JINSHUGAI_ID"
fi
if [ -n "$INC_FLAG" ]; then
    CMD="$CMD -inc_flag $INC_FLAG"
fi
if [ -n "$JOB" ]; then
    CMD="$CMD -job $JOB"
fi
if [ -n "$JOB2" ]; then
    CMD="$CMD -job2 $JOB2"
fi
# [Phase C] 3인자 스위치 (1 = 서브 캐릭터 사용 / 미지정 또는 0 = 기존 2인 모드)
if [ -n "$CHR_NUM3" ]; then
    CMD="$CMD -chr_num3 $CHR_NUM3"
fi

$CMD
