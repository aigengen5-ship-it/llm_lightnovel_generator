def get_particles(name: str) -> dict:
    """한글 이름의 마지막 글자 받침 유무에 따라 조사를 반환합니다.
    
    Returns:
        dict: {
            'subject': '이/가',    # 주격 조사
            'object': '을/를',     # 목적격 조사
            'topic': '은/는',      # 주제격 조사
            'comitative': '과/와'  # 부사격 조사
        }
    """
    if not name:
        return {'subject': '가', 'object': '를', 'topic': '는', 'comitative': '와'}
    has_batchim = (ord(name[-1]) - 0xAC00) % 28 > 0
    return {
        'subject': '이' if has_batchim else '가',
        'object': '을' if has_batchim else '를',
        'topic': '은' if has_batchim else '는',
        'comitative': '과' if has_batchim else '와',
    }

def name_chg (line, name, name2, name3=""):
    """본문의 [NAME]/[NAME2]/[NAME3] 토큰을 실제 이름으로 치환한다.

    조사 직속 토큰([NAME]이 / [NAME]을 / [NAME]은 / [NAME]과)은
    '이름 + 올바른 조사'로 치환한다. 조사 교정이 이 분기의 존재 이유이므로
    [D1] 조사만 남기고 이름을 버리던 기존 동작(타깃 동일)을 수정했다.
    """
    p1 = get_particles(name)
    p2 = get_particles(name2)

    line = line.replace('[NAME]이', f"{name}{p1['subject']}")
    line = line.replace('[NAME]을', f"{name}{p1['object']}")
    line = line.replace('[NAME]은', f"{name}{p1['topic']}")
    line = line.replace('[NAME]과', f"{name}{p1['comitative']}")
    line = line.replace('[NAME]', name)

    line = line.replace('[NAME2]이', f"{name2}{p2['subject']}")
    line = line.replace('[NAME2]을', f"{name2}{p2['object']}")
    line = line.replace('[NAME2]은', f"{name2}{p2['topic']}")
    line = line.replace('[NAME2]과', f"{name2}{p2['comitative']}")
    line = line.replace('[NAME2]', name2)

    if name3:
        p3 = get_particles(name3)
        line = line.replace('[NAME3]이', f"{name3}{p3['subject']}")
        line = line.replace('[NAME3]을', f"{name3}{p3['object']}")
        line = line.replace('[NAME3]은', f"{name3}{p3['topic']}")
        line = line.replace('[NAME3]과', f"{name3}{p3['comitative']}")
        line = line.replace('[NAME3]', name3)

    return line

