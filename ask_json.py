import json
import random
import re


from json_probe import TEXT_A, TEXT_B, TEXT_C, V2, MODEL, client, check_schema
from repair_probe import clean

MAX_RETRY = 1


def _call(messages):#messages->TEXT ABC
    """发一次请求，返回字符串内容"""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0,
        max_tokens=1500,
        stream=False
    )
    return resp.choices[0].message.content


def ask_json(user_text, system_prompt = V2, max_retry=MAX_RETRY):#user_text测试时可变更TEXT_B TEXT_B
    """返回 (dict 或 None, stats)"""

    stats = {"attempts": 0, "cleaned": 0, "retried": 0}
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    for attempt in range(max_retry + 1):
        raw = _call(messages)
        stats["attempts"] += 1

        fixed = clean(raw)
        if fixed != raw.strip():
            stats["cleaned"] += 1

        try:
            d = json.loads(fixed)  # 是json文档
        except json.JSONDecodeError as e:
            err = f"非法 JSON: {e}"#清洗完还不是json文档
        else:#try 块里没有抛异常时，才执行 else。
            ok, reason = check_schema(d)
            if ok:
                return d, stats
            err = reason#清洗完json文档对但是schema不对

        if attempt < max_retry:
            stats["retried"] += 1
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": f"你上次的输出有问题：{err}。请重新输出，只输出 JSON。"},
            ]

    return None, stats#循环完但是一次也没成功


if __name__ == '__main__':
    texts = [("A", TEXT_A), ("B", TEXT_B), ("C", TEXT_C)]
    N = 20
    random.seed(42)
    ok_cnt = 0
    total_attempts = 0
    total_retried = 0
    total_cleaned = 0
    fail_cases = []

    for i in range(1,N + 1):
        name, text = random.choice(texts)
        d, stats = ask_json(text)
        total_attempts += stats["attempts"]
        total_retried += stats["retried"]
        total_cleaned += stats["cleaned"]
        if d is None:
            fail_cases.append(name)
            print(f"[{i}/{N}] {name} 失败（调用 {stats['attempts']} 次）")
        else:
            ok_cnt += 1
            print(f"[{i}/{N}] {name} ok（调用 {stats['attempts']} 次）")

    print("\n===== 汇总 =====")
    print(f"成功: {ok_cnt}/{N} = {ok_cnt / N * 100:.1f}%")
    print(f"总调用次数: {total_attempts}（平均 {total_attempts / N:.2f} 次/条）")
    print(f"触发重试: {total_retried} 条")
    print(f"清洗生效: {total_cleaned} 条")
    if fail_cases:
        print(f"失败输入: {fail_cases}")