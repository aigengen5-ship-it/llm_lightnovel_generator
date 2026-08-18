안녕하세요. 한국어로 라이트노벨을 쓸 수 있는 간단한 GUI 프로그램입니다.

셋업은 아래와 같이 해 주시면 됩니다.

1. plot.json을 열어서 아래 항목을 현재 사용중인 로컬 LLM에 맞춰주세요.

"ip_main": "gx10-a5a3",
"port_main": "8000",
"mainLLM": "gemma",
"ip_agent": "gx10-a5a3",
"port_agent": "8000",


3. 디렉토리에서 파이썬 virtual 환경을 만들어 주세요.


python3 -m venv ./venv

4. virtual환경을 활성화 시켜 주세요.


source venv/bin/activate

5. 필수 요소를 인스톨해 주세요


pip install -r requirement.txt

6. 아래 명령을 이용하여 실행시켜 주세요.
(job/job2는 취향에 맞게 수정하시면 됩니다)

./run_main.sh -id 1 -job 4 -job2 1

<img width="2830" height="1394" alt="image" src="https://github.com/user-attachments/assets/cf872b48-42b4-4401-b888-31b67e2e167c" />


7. 임시) 현재 실행 순서는 아래와 같습니다.

1번 -> 2번 -> 5번 -> 7번.

초기 개발환경이므로 버그가 많을 것입니다. feedback 주시면 감사드립니다.

......혹시 불쌍한 중생에게 커피라도 사주실 분은 아래 링크 클릭이라도...TT
https://buymeacoffee.com/aigengen5
