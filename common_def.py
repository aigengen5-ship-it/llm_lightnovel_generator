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

def name_chg (line, name, name2):
    p1 = get_particles(name)
    p2 = get_particles(name2)

    line = line.replace('[NAME]이', p1['subject'])
    line = line.replace('[NAME]을', p1['object'])
    line = line.replace('[NAME]은', p1['topic'])
    line = line.replace('[NAME]과', p1['comitative'])
    line = line.replace('[NAME]', name)

    line = line.replace('[NAME2]이', p2['subject'])
    line = line.replace('[NAME2]을', p2['object'])
    line = line.replace('[NAME2]은', p2['topic'])
    line = line.replace('[NAME2]과', p2['comitative'])
    line = line.replace('[NAME2]', name2)

    return line

