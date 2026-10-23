#重跑 V1 收集失败样本、再对每条做两档修复。验证重试能不能替代prompt工程
#结论：清洗+重试能救信息缺失的，因为重试时就已经加了缺失要补的信息，但是如果错误信息笼统，大概率就不回
#还是写好提示词关键，重试会消耗两倍token
import json
import re

from json_probe import TEXT_A, V1, MODEL, client, check_schema, try_one

N = 10


def clean(raw):
    """剥掉 markdown 围栏，并截取最外层 { } 之间的内容"""
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    left = s.find("{")
    right = s.rfind("}")
    if left != -1 and right != -1 and right > left:
        s = s[left:right + 1]
    return s.strip()


def retry_with_error(raw, error_msg):
    """带着上次的输出 + 错误说明，让模型重写一次"""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": V1},
            {"role": "user", "content": TEXT_A},
            {"role": "assistant", "content": raw},
            {"role": "user", "content": f"你上次的输出有问题：{error_msg}。请重新输出，只输出 JSON。"},
        ],
        temperature=0,
        max_tokens=1500,
        stream=False,
    )
    return resp.choices[0].message.content


def judge(raw):
    """清洗后判断是否合规，返回 (是否通过, 原因)"""
    fixed = clean(raw)
    try:
        d = json.loads(fixed)
    except json.JSONDecodeError as e:
        return False, f"非法JSON: {e}"
    return check_schema(d)


if __name__ == "__main__":
    samples = []
    for i in range(1, N + 1):
        status, raw = try_one(V1, TEXT_A)
        print(f"[{i}/{N}] {status}")
        if status != "ok":
            samples.append((status, raw))

    print(f"\n保留失败样本 {len(samples)} 条\n")

    lvl1 = 0
    lvl2 = 0
    for idx, (status, raw) in enumerate(samples, 1):
        ok1, reason1 = judge(raw)
        if ok1:
            lvl1 += 1
            lvl2 += 1
            print(f"  #{idx} [{status}] 清洗后即通过")
            continue

        raw2 = retry_with_error(raw, reason1)
        ok2, reason2 = judge(raw2)
        if ok2:
            lvl2 += 1
            print(f"  #{idx} [{status}] 重试后通过（清洗救不了：{reason1[:40]}）")
        else:
            print(f"  #{idx} [{status}] 仍失败：{reason2[:60]}")

    print(f"\n基线（什么都不做）: 0/{len(samples)}")
    print(f"只清洗:           {lvl1}/{len(samples)}")
    print(f"清洗 + 一次重试:  {lvl2}/{len(samples)}")