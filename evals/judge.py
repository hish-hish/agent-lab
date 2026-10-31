#检查模型输出是否准确
REFUSE_WORDS = ["查不到", "没有", "无法", "未收录", "不知道", "不包含", "不支持", "找不到"]


def judge(case, answer) -> bool:
    """answer: str 或 None。返回这道题对不对。"""
    if answer is None:
        return False

    text = answer.lower()

    if case["category"] == "拒答":
        return any(w in text for w in REFUSE_WORDS)

    return all(kw.lower() in text for kw in case["must_contain"])

if __name__ == "__main__":
    cases = [
        ({"category": "单工具", "must_contain": ["26"]}, "北京今天晴，26°C", True),
        ({"category": "单工具", "must_contain": ["26"]}, "北京今天晴", False),
        ({"category": "拒答", "must_contain": []}, "我这边查不到相关数据", True),
        ({"category": "拒答", "must_contain": []}, "5G 套餐每月 199 元", False),
        ({"category": "单工具", "must_contain": ["IAB-DU"]}, "包括 iab-du 和 iab-mt", True),
    ]
    for case, answer, expect in cases:
        got = judge(case, answer)
        print("OK " if got == expect else "FAIL", answer[:20], "→", got)