import random

# ==========================================
# 🌟 흐름 제어 모듈 (Flow Control)
# ==========================================
# 입력: id, 기본 호감도, 에피소드 개수
# 출력: 각 에피소드별 {m, l, a, o, i, s, d} 값 (0-5)
# ==========================================

# ID별 변화 곡선 정의
# 각 값: (초기값, 최종값, 변화 시작 에피소드 비율, 변화 끝 에피소드 비율)
# 변화 시작/끝 비율: 0.0(초반) ~ 1.0(결말)
FLOW_CURVES = {
    # ID 1: 순애와 타락 (일상)
    1: {
        "m": (4.5, 3.0, 0.3, 0.9),   # 도덕성: 서서히 ↓
        "l": (0.0, 3.0, 0.4, 0.9),   # 음란도: 나중에 ↑
        "a": (0.0, 5.0, 0.0, 0.7),   # 호감도: 먼저 ↑
        "o": (0.5, 3.0, 0.3, 0.8),   # 복종도: 중간에 ↑
        "i": (4.0, 2.0, 0.4, 0.9),   # 지성: 약간 ↓
        "s": (4.5, 1.0, 0.3, 0.8),   # 수치심: 서서히 ↓
        "d": (2.5, 3.0, 0.2, 0.7),   # 주도권: 약간 ↑
    },
    # ID 2: 동반 타락 (구원 실패형)
    2: {
        "m": (4.5, 1.0, 0.2, 0.8),   # 도덕성: 함께 ↓
        "l": (0.0, 4.5, 0.2, 0.8),   # 음란도: 함께 ↑
        "a": (0.0, 5.0, 0.0, 0.7),   # 호감도: 함께 ↑
        "o": (0.5, 3.5, 0.3, 0.9),   # 복종도: 함께 ↑
        "i": (4.0, 1.5, 0.3, 0.9),   # 지성: 함께 ↓
        "s": (4.5, 1.0, 0.2, 0.8),   # 수치심: 함께 ↓
        "d": (2.5, 3.5, 0.2, 0.8),   # 주도권: 약간 ↑
    },
    # ID 3: 밀실 감금 타락
    3: {
        "m": (4.5, 0.5, 0.1, 0.7),   # 도덕성: 급격히 ↓
        "l": (0.0, 5.0, 0.1, 0.7),   # 음란도: 급격히 ↑
        "a": (0.0, 4.5, 0.1, 0.6),   # 호감도: 급격히 ↑
        "o": (0.5, 4.0, 0.2, 0.8),   # 복종도: 급격히 ↑
        "i": (4.0, 1.0, 0.2, 0.8),   # 지성: 급격히 ↓
        "s": (4.5, 0.5, 0.1, 0.7),   # 수치심: 급격히 ↓
        "d": (2.5, 1.5, 0.2, 0.7),   # 주도권: ↓
    },
    # ID 4: 고립 생존 타락
    4: {
        "m": (4.5, 1.0, 0.2, 0.8),   # 도덕성: 같이 ↓
        "l": (0.0, 4.5, 0.2, 0.8),   # 음란도: 같이 ↑
        "a": (0.0, 4.5, 0.1, 0.7),   # 호감도: 같이 ↑
        "o": (0.5, 4.0, 0.3, 0.9),   # 복종도: ↑
        "i": (4.0, 2.0, 0.3, 0.9),   # 지성: 서서히 ↓
        "s": (4.5, 1.5, 0.2, 0.8),   # 수치심: ↓
        "d": (2.5, 4.0, 0.2, 0.8),   # 주도권: ↑
    },
    # ID 5: 굴복 및 조교 타락 (마인드 브레이크)
    5: {
        "m": (4.5, 0.5, 0.2, 0.7),   # 도덕성: 급격히 ↓
        "l": (0.0, 5.0, 0.1, 0.6),   # 음란도: 먼저 급격히 ↑
        "a": (0.0, 4.0, 0.3, 0.8),   # 호감도: 나중에 ↑
        "o": (0.5, 4.5, 0.3, 0.9),   # 복종도: ↑
        "i": (4.0, 1.0, 0.3, 0.8),   # 지성: ↓
        "s": (4.5, 0.5, 0.2, 0.7),   # 수치심: 급격히 ↓
        "d": (2.5, 1.0, 0.3, 0.8),   # 주도권: ↓
    },
    # ID 6: 블러디핑크 사악 타락 (아이템 중독)
    6: {
        "m": (4.5, 1.0, 0.2, 0.8),   # 도덕성: ↓
        "l": (0.0, 5.0, 0.1, 0.5),   # 음란도: 매우 급격히 ↑
        "a": (0.0, 3.5, 0.2, 0.7),   # 호감도: 중간에 ↑
        "o": (0.5, 3.5, 0.3, 0.8),   # 복종도: ↑
        "i": (4.0, 1.0, 0.1, 0.6),   # 지성: 먼저 ↓
        "s": (4.5, 1.0, 0.2, 0.7),   # 수치심: ↓
        "d": (2.5, 4.5, 0.2, 0.8),   # 주도권: ↑ (자발적)
    },
    # ID 7: 잠입 수사 타락
    7: {
        "m": (4.5, 0.0, 0.3, 0.8),   # 도덕성: 나중에 ↓
        "l": (0.0, 5.0, 0.1, 0.6),   # 음란도: 먼저 ↑
        "a": (0.0, 5.0, 0.3, 0.8),   # 호감도: 나중에 ↑
        "o": (0.5, 5.0, 0.3, 0.9),   # 복종도: ↑
        "i": (4.5, 2.5, 0.3, 0.8),   # 지성: 약간 ↓
        "s": (4.5, 0.0, 0.2, 0.7),   # 수치심: ↓
        "d": (3.5, 0.0, 0.1, 0.7),   # 주도권: ↑ (잠입 중 적극적)
    },
    # ID 8: 일상 침식 타락 (서서히 끓는 물)
    8: {
        "m": (4.5, 1.5, 0.1, 0.9),   # 도덕성: 서서히 ↓
        "l": (0.0, 4.0, 0.1, 0.9),   # 음란도: 서서히 ↑
        "a": (0.0, 4.5, 0.0, 0.8),   # 호감도: 서서히 ↑
        "o": (0.5, 3.5, 0.2, 0.9),   # 복종도: 서서히 ↑
        "i": (4.0, 2.0, 0.2, 0.9),   # 지성: 서서히 ↓
        "s": (4.5, 1.5, 0.1, 0.8),   # 수치심: 서서히 ↓
        "d": (2.5, 2.0, 0.3, 0.8),   # 주도권: 약간 ↓
    },
    # ID 9: 권력 역전 타락 (하극상)
    9: {
        "m": (4.5, 1.5, 0.3, 0.8),   # 도덕성: ↓
        "l": (0.0, 4.0, 0.3, 0.8),   # 음란도: ↑
        "a": (0.0, 4.5, 0.2, 0.7),   # 호감도: ↑
        "o": (0.5, 4.0, 0.4, 0.9),   # 복종도: ↑ (역전 후)
        "i": (4.0, 2.5, 0.3, 0.8),   # 지성: 약간 ↓
        "s": (4.5, 1.5, 0.2, 0.7),   # 수치심: ↓
        "d": (2.5, 5.0, 0.1, 0.5),   # 주도권: 먼저 ↑
    },
    # ID 10: 코즈믹 호러 종교 타락
    10: {
        "m": (4.5, 1.0, 0.2, 0.8),   # 도덕성: ↓
        "l": (0.0, 4.5, 0.2, 0.8),   # 음란도: ↑
        "a": (0.0, 4.0, 0.2, 0.7),   # 호감도: ↑
        "o": (0.5, 4.5, 0.3, 0.9),   # 복종도: ↑
        "i": (4.0, 1.0, 0.1, 0.5),   # 지성: 먼저 ↓
        "s": (4.5, 1.0, 0.2, 0.7),   # 수치심: ↓
        "d": (2.5, 1.5, 0.3, 0.8),   # 주도권: ↓
    },
    # ID 11: 군중 공개 타락
    11: {
        "m": (4.5, 1.5, 0.3, 0.8),   # 도덕성: ↓
        "l": (0.0, 4.5, 0.2, 0.8),   # 음란도: ↑
        "a": (0.0, 4.0, 0.2, 0.7),   # 호감도: ↑
        "o": (0.5, 3.5, 0.3, 0.9),   # 복종도: ↑
        "i": (4.0, 2.5, 0.3, 0.8),   # 지성: 약간 ↓
        "s": (4.5, 0.5, 0.1, 0.5),   # 수치심: 먼저 ↓
        "d": (2.5, 4.0, 0.2, 0.8),   # 주도권: ↑
    },
}


def _clamp(value, min_val=0.0, max_val=5.0):
    """값을 0~5 범위로 제한"""
    return max(min_val, min(max_val, value))


def _interpolate(start, end, progress):
    """선형 보간 (progress: 0.0~1.0)"""
    return start + (end - start) * progress


def generate_flow_curve(flow_id, base_affection, num_episodes):
    """
    흐름 제어 곡선 생성

    Args:
        flow_id: 흐름 ID (1~11)
        base_affection: 기본 호감도 (0~3)
        num_episodes: 에피소드 개수

    Returns:
        list[dict]: 각 에피소드별 {m, l, a, o, i, s, d} 값 (0-5, round 후 int)
    """
    if flow_id not in FLOW_CURVES:
        raise ValueError(f"유효하지 않은 flow_id: {flow_id} (1~11 범위여야 함)")

    curves = FLOW_CURVES[flow_id]
    episodes = []

    for i in range(num_episodes):
        # 진행 비율 (0.0 ~ 1.0)
        if num_episodes <= 1:
            t = 1.0
        else:
            t = i / (num_episodes - 1)

        episode_data = {}
        for key in ["m", "l", "a", "o", "i", "s", "d"]:
            start_val, end_val, start_ratio, end_ratio = curves[key]

            # 호감도(a)는 기본 호감도를 초기값으로 사용
            if key == "a":
                start_val = base_affection

            # 변화 구간 계산
            if t <= start_ratio:
                # 변화 시작 전: 초기값
                value = start_val
            elif t >= end_ratio:
                # 변화 종료 후: 최종값
                value = end_val
            else:
                # 변화 중: 선형 보간
                progress = (t - start_ratio) / (end_ratio - start_ratio)
                value = _interpolate(start_val, end_val, progress)

            # 랜덤 변동 추가 (±0.5, 모든 에피소드 적용)
            random_variation = random.uniform(-0.5, 0.5)
            value += random_variation

            # 0~5 범위로 제한 후 반올림
            value = _clamp(value)
            episode_data[key] = round(value)

        episodes.append(episode_data)

    return episodes


# 스탯 한글 이름 매핑
_STAT_NAME_KO = {
    "m": "도덕성",
    "l": "음란도",
    "a": "호감도",
    "o": "복종도",
    "i": "지성",
    "s": "수치심",
    "d": "주도권",
}


def generate_flow_episode_status(episodes):
    """
    에피소드별 현재 상태 및 전 에피소드 대비 변화량 설명 생성 (라이트 노벨 문장 스타일)

    Args:
        episodes: generate_flow_curve 반환값 (list of dict with m,l,a,o,i,s,d)

    Returns:
        list[str]: 각 에피소드별 상태 설명 문장
    """
    if not episodes:
        return []

    # 스탯별 상태/변화 묘사를 위한 내부 헬퍼
    def _get_level(val, current_val, low_is_target=False):
        abs_val = abs(val)
        if low_is_target:
            if current_val == 0: return "완전히"
            elif current_val == 1: return "거의"
        else:
            if current_val == 5: return "완전히"
            elif current_val == 4: return "거의"
        
        if abs_val >= 4: return "매우"
        elif abs_val >= 3: return "꽤"
        elif abs_val >= 2: return "조금"
        elif abs_val >= 1: return "살짝"
        return ""

    def _describe_state(key, val):
        mapping = {
            "m": {0: "완전히 사악하게 행동한다", 1: "많이 사악하다", 2: "가끔씩은 살짝 사악하게 행동한다.", 3: "사악한 생각이 들어도 착하게 행동한다. ", 4: "완전히 착하다", 5: "고결하다"},
            "l": {0: "순결하다", 1: "순진하다", 2: "호기심이 생겼다 ", 3: "음란하다", 4: "색욕에 빠져들다", 5: "음탕하다"},
            "a": {0: "냉담하다", 1: "무관심하다", 2: "호감 있는", 3: "다정하다", 4: "사랑한다.", 5: "맹목적으로 좋아한다."},
            "o": {0: "적대적이다", 1: "반항적이다", 2: "마지못해 따른다", 3: "순종적이다", 4: "충실하다", 5: "완벽히 굴복하다"},
            "i": {0: "본능만 남아있다", 1: "이성보다 쾌감을 우선한다", 2: "이성적 판단이 흔들린다.", 3: "평범하다", 4: "명석하다", 5: "영리하다"},
            "s": {0: "부끄러움 없이 음란한 행동을 요구한다", 1: "부끄러워 하면서도 음란하게 행동한다", 2: "말로는 수줍어하지만 표정은 관심이 있다", 3: "평범하게 수줍어한다.", 4: "부끄러움이 많다", 5: "극도로 수줍어한다"},
            "d": {0: "매우 수동적이다", 1: "약간 수동적이다", 2: "소극적이다", 3: "평범하다", 4: "주도적이다", 5: "관계를 지배하려고 한다."},
        }
        return mapping[key][val]

    def _describe_change(key, delta, current_val):
        # target_low: True면 값이 작아질수록 긍정/강화 (m, i, s)
        target_low = key in ['m', 'i', 's']
        level = _get_level(delta, current_val, low_is_target=target_low)
        
        phrases = {
            "m": {1: "고결해졌다", -1: "사악해졌다"},
            "l": {1: "음란해졌다", -1: "순수해졌다"},
            "a": {1: "호감이 생겼다", -1: "냉담해졌다"},
            "o": {1: "순종적으로 변했다", -1: "저항하기 시작했다"},
            "i": {1: "명석해졌다", -1: "멍청해졌다"},
            "s": {1: "수치심을 느낀다", -1: "부끄러움을 잊었다"},
            "d": {1: "적극적으로 변했다", -1: "수동적으로 변했다"},
        }
        dir_key = 1 if delta > 0 else -1
        return f"{level} {phrases[key][dir_key]}"

    status_list = []
    for idx, ep in enumerate(episodes):
        # 1. 현재 상태 묘사 (character sheet 스타일, 모든 스탯 출력)
        state_lines = [f"[EP{idx+1}]"]
        for key in ["m", "l", "a", "o", "i", "s", "d"]:
            val = ep[key]
            state_desc = _describe_state(key, val)
            state_lines.append(f"  {_STAT_NAME_KO[key]}: {state_desc}")
        
        current_desc = "\n".join(state_lines)
        
        # 2. 변화 묘사 (EP2부터)
        if idx > 0:
            prev_ep = episodes[idx-1]
            change_parts = []
            for key in ["m", "l", "a", "o", "i", "s", "d"]:
                delta = ep[key] - prev_ep[key]
                if delta != 0:
                    change_parts.append(_describe_change(key, delta, ep[key]))
            
            if change_parts:
                change_desc = "\n  → " + ", ".join(change_parts)
            else:
                change_desc = "\n  → 특별한 심경의 변화는 없습니다."
            
            full_text = current_desc + change_desc
        else:
            full_text = current_desc
            
        status_list.append(full_text)

    return status_list


def print_flow_curve(episodes):
    """흐름 곡선을 텍스트로 출력 (디버깅용)"""
    print("=" * 80)
    print("🌟 [흐름 제어 곡선] 🌟")
    print("=" * 80)
    print(f"{'EP':>4} | {'m':>3} | {'l':>3} | {'a':>3} | {'o':>3} | {'i':>3} | {'s':>3} | {'d':>3}")
    print("-" * 60)
    for i, ep in enumerate(episodes):
        print(f"{i+1:>4} | {ep['m']:>3} | {ep['l']:>3} | {ep['a']:>3} | "
              f"{ep['o']:>3} | {ep['i']:>3} | {ep['s']:>3} | {ep['d']:>3}")
    print("=" * 80)


def generate_flow_description(flow_stats, step_name, num_episodes):
    """
    flow_stats를 기반으로 단계별 캐릭터 변화 설명 생성
    
    Args:
        flow_stats: generate_flow_curve 반환값 (list of dict)
        step_name: '기-승', '전', '결'
        num_episodes: 총 에피소드 수
    
    Returns:
        str: 캐릭터 변화 설명
    """
    if not flow_stats:
        return ""
    
    # 단계별 에피소드 범위 계산
    if step_name == '기-승':
        start_ep = 0
        end_ep = max(start_ep + 1, int(num_episodes * 0.4))
    elif step_name == '전':
        start_ep = int(num_episodes * 0.4)
        end_ep = max(start_ep + 1, int(num_episodes * 0.8))
    else:  # 결
        start_ep = int(num_episodes * 0.8)
        end_ep = num_episodes
    
    # 해당 단계의 시작과 끝 에피소드
    stage_start = flow_stats[start_ep]
    stage_end = flow_stats[min(end_ep - 1, len(flow_stats) - 1)]
    
    # 단계 내 변화 분석
    changes = {}
    for key in ['m', 'l', 'a', 'o', 'i', 's', 'd']:
        changes[key] = stage_end.get(key, 0) - stage_start.get(key, 0)
    
    # 변화 정도에 따른 표현
    def _get_level(val, current_val, low_is_target=False):
        """변화 값과 현재 값에 따른 정도 표현
        
        Args:
            val: 변화량
            current_val: 현재값 (0~5)
            low_is_target: True면 0에 가까울수록 좋음 (m, i, s), False면 5에 가까울수록 좋음 (l, a, o, d)
        """
        abs_val = abs(val)
        
        # 현재값의 절대값이 우선
        if low_is_target:
            # 0에 가까울수록 좋음 (m, i, s)
            if current_val == 0:
                return "완전히"
            elif current_val == 1:
                return "거의"
        else:
            # 5에 가까울수록 좋음 (l, a, o, d)
            if current_val == 5:
                return "완전히"
            elif current_val == 4:
                return "거의"
        
        if abs_val >= 4:
            return "매우"
        elif abs_val >= 3:
            return "꽤"
        elif abs_val >= 2:
            return "조금"
        elif abs_val >= 1:
            return "살짝"
        return ""
    
    # 설명 생성
    desc_parts = []
    
    # 음란도 변화 (5에 가까울수록 좋음)
    if changes['l'] > 0:
        level = _get_level(changes['l'], stage_end.get('l', 0), low_is_target=False)
        desc_parts.append(f"{level} 음란해졌다")
    elif changes['l'] < -1:
        level = _get_level(changes['l'], stage_end.get('l', 0), low_is_target=True)
        desc_parts.append(f"{level} 순수해졌다")
    
    # 호감도 변화 (5에 가까울수록 좋음)
    if changes['a'] > 0:
        level = _get_level(changes['a'], stage_end.get('a', 0), low_is_target=False)
        desc_parts.append(f"{level} 호감이 생겼다")
    elif changes['a'] < -1:
        level = _get_level(changes['a'], stage_end.get('a', 0), low_is_target=True)
        desc_parts.append(f"{level} 냉담해졌다")
    
    # 도덕성 변화 (0에 가까울수록 좋음)
    if changes['m'] < 0:
        level = _get_level(changes['m'], stage_end.get('m', 0), low_is_target=True)
        desc_parts.append(f"{level} 사악해졌다")
    elif changes['m'] > 1:
        level = _get_level(changes['m'], stage_end.get('m', 0), low_is_target=False)
        desc_parts.append(f"{level} 고결해졌다")
    
    # 복종도 변화 (5에 가까울수록 좋음)
    if changes['o'] > 0:
        level = _get_level(changes['o'], stage_end.get('o', 0), low_is_target=False)
        desc_parts.append(f"{level} 순종적으로 변했다.")
    elif changes['o'] < -1:
        level = _get_level(changes['o'], stage_end.get('o', 0), low_is_target=True)
        desc_parts.append(f"{level} 저항한다.")
    
    # 지성 변화 (0에 가까울수록 좋음)
    if changes['i'] < 0:
        level = _get_level(changes['i'], stage_end.get('i', 0), low_is_target=True)
        desc_parts.append(f"{level} 멍청해졌다")
    elif changes['i'] > 1:
        level = _get_level(changes['i'], stage_end.get('i', 0), low_is_target=False)
        desc_parts.append(f"{level} 똑똑해졌다")
    
    # 수치심 변화 (0에 가까울수록 좋음)
    if changes['s'] < 0:
        level = _get_level(changes['s'], stage_end.get('s', 0), low_is_target=True)
        desc_parts.append(f"{level} 부끄러움을 잊었다")
    elif changes['s'] > 1:
        level = _get_level(changes['s'], stage_end.get('s', 0), low_is_target=False)
        desc_parts.append(f"{level} 수치심을 가진다")
    
    # 주도권 변화 (5에 가까울수록 좋음)
    if changes['d'] > 0:
        level = _get_level(changes['d'], stage_end.get('d', 0), low_is_target=False)
        desc_parts.append(f"{level} 적극적으로 행동한다.")
    elif changes['d'] < -1:
        level = _get_level(changes['d'], stage_end.get('d', 0), low_is_target=True)
        desc_parts.append(f"{level} 수동적으로 행동한다")
    
    if not desc_parts:
        return "특정한 변화 없음"
    
    return ", ".join(desc_parts)


def get_fluent_status_ko_v2(m, l, a, o, i, s, d, gen=0):
    """
    캐릭터 스탯 기반 라이트 노벨 스타일 상태 문구 생성

    Args:
        m: 도덕성 (0-5)
        l: 음란도 (0-5)
        a: 호감도 (0-5)
        o: 복종도 (0-5)
        i: 지성 (0-5)
        s: 수치심 (0-5)
        d: 주도권 (0-5)
        gen: 성별 (0=여성, 1=남성)

    Returns:
        str: "형용사 명사" 형식의 상태 문구
    """
    adj_matrix = {
        "noble": ["고결하기 그지없는", "성역과도 같은", "범접할 수 없는 기품의", "서늘할 정도로 정결한", "결벽에 가까운", "숭고한 의지를 품은", "달빛처럼 고고한", "금욕의 끝에 선", "엄격하고도 우아한", "지조 높은"],
        "innocent": ["금방이라도 부서질 듯한", "세상 물정 모르는 순진한", "이슬 맺힌 꽃봉오리 같은", "위태롭게 흔들리는", "수줍음이 가득한", "때 묻지 않은 백지 같은", "보호 본능을 자극하는", "풋풋한 향기가 나는", "가련하고도 청초한", "투명하게 빛나는"],
        "devoted": ["맹목적인 사랑에 빠진", "오직 한 사람만을 바라보는", "헌신과 애정으로 가득 찬", "다정함이 넘쳐흐르는", "숨소리조차 맞추려는", "깊은 신뢰로 묶인", "상냥하게 감싸 안는", "포근한 온기를 품은", "지극한 정성으로 모시는", "일편단심의"],
        "obsessive": ["뒤틀린 애욕에 젖은", "광기 어린 집착의", "늪처럼 깊게 가라앉은", "소유욕에 눈이 먼", "섬뜩할 정도로 의존적인", "피폐해진 정신의", "어두운 갈망을 품은", "독점욕에 불타는", "질척이는 애정의", "절박하게 매달리는"],
        "cold": ["얼음처럼 차갑고 오만한", "냉혹한 시선으로 내려다보는", "가차 없는 냉정함의", "서늘한 거리감을 두는", "무심한 듯 날카로운", "도도함이 뼈에 사무친", "비정한 이성의", "싸늘하게 식어버린", "안중에도 없다는 듯한", "시니컬한"],
        "submissive": ["완벽하게 길들여진", "자아를 버리고 복종하는", "순종적인 강아지 같은", "저항을 포기한 채 굴복한", "시키는 대로 움직이는 인형 같은", "비굴할 정도로 고분고분한", "예속의 쾌락에 익숙한", "납작 엎드린 비천한", "주인의 뜻만을 기다리는", "온순하게 꺾인"],
        "lewd_bold": ["배덕한 쾌락에 눈뜬", "농염한 향기를 풍기는", "수치심을 잊은 천박한", "욕망에 충실하게 타오르는", "요염하게 유혹하는", "방탕한 일탈을 갈구하는", "관능적인 곡선미의", "도발적인 눈빛을 한", "육욕의 소용돌이에 빠진", "파렴치할 정도로 대담한"],
        "shameful": ["치욕스러운 쾌락에 떨고 있는", "배덕감에 짓눌려 울먹이는", "부정하고 싶지만 달아오른", "굴욕적인 상황에 젖어든", "모순된 욕망에 괴로워하는", "얼굴을 붉히며 몸부림치는", "자괴감 속에서 쾌락을 찾는", "수치사에 이를 정도로 당혹스러운", "짓눌린 자존심의", "비참하게 무너져 내리는"],
        "mindless": ["이성이 하얗게 타버린", "쾌락에 절여져 멍해진", "본능만이 남은 텅 빈", "사고 회로가 정지된", "몽롱한 안개 속에 있는", "침을 흘리며 쾌락을 쫓는", "나사가 빠져버린 바보 같은", "인형처럼 초점 없는", "지능이 녹아내린", "흐물흐물하게 풀려버린"],
        "dominant": ["군림하는 여왕과 같은", "가학적인 지배욕의", "무자비하게 유린하는", "압도적인 위압감의", "강압적인 명령을 내리는", "포식자의 눈빛을 한", "오만하게 내려다보는", "사악한 유희를 즐기는", "통제 불능의 광기를 띤", "거만한 주인의"],
        "rebellious": ["가시 돋친 말로 반항하는", "길들여지지 않은 야생의", "독설을 내뱉는 불손한", "증오와 갈망이 섞인", "악바리처럼 버티는", "날 선 적대감의", "사나운 맹수 같은", "비협조적으로 굴어대는", "침을 뱉듯 냉소적인", "불손하기 짝이 없는"],
        "feminine": ["암컷으로서의 자각이 싹튼", "꽃향기가 배어나는", "여성스러운 곡선이 강조된", "교태가 넘치는 앙큼한", "보드라운 살결의", "레이스가 어울리는 가냘픈", "수줍게 젖어든", "아리따운 외모의", "암컷의 향기를 풍기는", "깜찍하고 요염한"]
    }

    if gen == 0:
        noun_pools = {
            0: ["고귀한 영애", "빛나는 성녀", "하늘의 공주님", "금욕의 수녀", "범접할 수 없는 숙녀"],
            1: ["이슬 맺힌 소녀", "순진무구한 어린 양", "피어오를 꽃봉오리", "희생될 순결한 양", "세상을 모르는 견습생"],
            2: ["농염한 요부", "월광의 무희", "비밀의 비서", "관능의 모델", "애정의 연인"],
            3: ["금기를 깨뜨린 배덕자", "쾌락의 탕녀", "마법의 유혹자", "방탕한 일탈의 여인", "도덕을 버린 일탈자"],
            4: ["주인의 장난감", "소유된 인형", "복종의 노예", "채워질 그릇", "명령받는 메이드"],
            5: ["쾌락의 암컷", "감각의 암컷", "길들여진 가축", "뇌가 녹은 빔보", "본능의 짐승"]
        }
    else:
        noun_pools = {
            0: ["고귀한 귀공자", "철의 기사", "우아한 신사", "청순한 공자", "영광의 도련님"],
            1: ["순진한 미소년", "푸른 새싹 청년", "때 묻지 않은 어린 양", "피어오를 새싹", "헌신하는 시종"],
            2: ["화려한 광대", "귀염둥이 소년", "관능의 모델", "은밀한 남창", "아름다운 미인"],
            3: ["여성화의 시시", "변신한 자", "방탕한 일탈자", "금기를 깨뜨린 배덕자", "타락한 미소년"],
            4: ["레이스 입은 펨보이", "장식된 여장 인형", "복종하는 하녀 소년", "조종되는 장난감", "소유된 전유물"],
            5: ["쾌락의 암컷 소년", "길들여진 애완 펨보이", "감각의 육인형", "뇌가 녹은 펨보이 빔보", "본능의 가축"]
        }

    if i <= 1 and l >= 3: key = "mindless"
    elif gen == 1 and l >= 3 and random.random() > 0.5: key = "feminine"
    elif l >= 3 and s >= 4: key = "shameful"
    elif l >= 4: key = "lewd_bold"
    elif d >= 4: key = "dominant"
    elif o >= 4: key = "submissive"
    elif a >= 4 and m <= 1: key = "obsessive"
    elif a >= 4: key = "devoted"
    elif o <= 1 and a <= 1: key = "rebellious"
    elif m >= 4: key = "noble"
    elif a <= 1: key = "cold"
    else: key = "innocent"

    selected_adj = random.choice(adj_matrix[key])
    m_idx = max(0, min(int(m), 4))
    selected_noun = noun_pools[l][4 - m_idx]

    return f"{selected_adj} {selected_noun}"


if __name__ == "__main__":
    # 테스트: ID 1 (순애와 타락), 기본 호감도 2, 에피소드 10
    episodes = generate_flow_curve(flow_id=1, base_affection=2, num_episodes=10)
    print_flow_curve(episodes)
