# 📖 Korean Light Novel Generator (GUI)

> **한국어로 손쉽게 라이트노벨을 창작할 수 있는 오픈소스 GUI 프로그램입니다.**  
> 로컬 LLM을 연동하여 웹소설/라이트노벨의 플롯 구성부터 집필까지 단계별로 지원합니다.

<p align="left">
  <img src="https://img.shields.io/badge/Python-3.x-blue?style=flat-square&logo=python" alt="Python" />
  <img src="https://img.shields.io/badge/License-Open%20Source-green?style=flat-square" alt="License" />
</p>

> ⚠️ **안내**: 본 프로그램 내 생성 및 등장하는 모든 인물 설정은 **성인** 기준입니다.

---

## 📸 미리보기

<div align="center">
  <img width="90%" alt="Light Novel GUI Preview" src="https://github.com/user-attachments/assets/cf872b48-42b4-4401-b888-31b67e2e167c" />
</div>

---

## ⚙️ 시작하기 (Quick Start)

### 1. 로컬 LLM 환경 설정 (`plot.json`)
`plot.json` 파일을 열어 본인이 사용 중인 로컬 LLM 환경(IP, 포트, 모델명)에 맞게 수정합니다.

```json
{
  "ip_main": "gx10-a5a3",
  "port_main": "8000",
  "mainLLM": "gemma",
  "ip_agent": "gx10-a5a3",
  "port_agent": "8000"
}
```

---

### 2. 가상환경 생성 및 의존성 설치

```bash
# 1) 파이썬 가상환경(venv) 생성
python3 -m venv ./venv

# 2) 가상환경 활성화
source venv/bin/activate

# 3) 필수 패키지 설치
pip install -r requirement.txt
```

---

### 3. 프로그램 실행

아래 명령어를 입력하여 프로그램을 구동합니다.  
*(※ `-job` 및 `-job2` 옵션값은 필요에 따라 변경 가능합니다.)*

```bash
./run_main.sh -id 1 -job 4 -job2 1
```

---

## 🧭 추천 작업 워크플로우

GUI에서 작업 순서는 목적에 따라 다음과 같이 진행할 수 있습니다.

- **전체 자동 실행**: 중간 과정 확인 없이 바로 완성본을 생성하려면 **`10번`**을 즉시 실행하세요.
- **단계별 검토 및 생성**:
  ```text
  [0번] ➡️ [1번] ➡️ [2번] ➡️ [5번] ➡️ [7번]
  ```

---

## 💬 피드백 & 기여

현재 초기 개발 단계로 예상치 못한 버그가 발생할 수 있습니다.  
버그 제보나 기능 제안은 언제든지 **[Issues](https://github.com/)**를 통해 남겨주시면 큰 도움이 됩니다!

---

## ☕ Support

프로젝트가 마음에 드셨거나 개발자에게 힘을 보태주고 싶으시다면 커피 한 잔 부탁드립니다! 🙇‍♂️

<a href="https://buymeacoffee.com/aigengen5" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="45" width="162">
</a>

### ✨ 다음 수정 예정.
1. **등장인물 추가**: 하렘물/삼각관계 id를 추가할 예정이며, 이 경우 등장인물은 기존 2명에서 3명으로 확장될 예정입니다.
