#!/bin/bash
rm -f *.log
rm -f log/*.*

# 인자 파싱
JINSHUGAI_ID=""
INC_FLAG=""
JOB=""
JOB2=""
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
        *)
            shift
            ;;
    esac
done

CMD="python llm_novel_gui_textual.py"
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

$CMD
