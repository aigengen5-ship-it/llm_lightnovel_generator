#!/bin/bash
rm *.log
source ../venv/bin/activate
cd "$(dirname "$0")"
nohup python3 llm_novel_gui.py --auto > auto_run.log 2>&1 &
echo "PID: $!"
