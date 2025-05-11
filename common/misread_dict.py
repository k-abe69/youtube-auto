# 読み間違い補正辞書（全文一致で置換）
MISREAD_REPLACEMENTS = {
    "良い人": "いいひと",
    "一番": "いちばん",
    "大人しい": "おとなしい",
    "重なる": "かさなる",
    "実は": "じつわ",
}

def apply_misread_corrections(text: str) -> str:
    """
    登録された読み間違い補正辞書を元に、全文一致で置換する
    """
    for wrong, corrected in MISREAD_REPLACEMENTS.items():
        text = text.replace(wrong, corrected)
    return text
