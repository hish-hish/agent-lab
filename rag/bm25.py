#给"查询"和"文档块"算一个相关度分数，然后排序取前几个
import math
import re
import json
from collections import Counter
from pathlib import Path

K1 = 1.5      # 词频饱和速度
B = 0.75      # 长度归罚强度


def tokenize(text: str) -> list[str]:
    """英文切词：只留字母数字，统一小写。"""
    return re.findall(r"[a-z0-9]+", text.lower())


def build_index(chunks: list[dict]):
    """
    建索引，提前写好算数
    :param chunks:输入
    :return:，docs 每个块的三样东西：原文、词频表、长度，df 每个词出现在多少个块里，avg_len 平均每块多少词
    """
    docs = []
    df = Counter()          # df[词] = 这个词出现在多少个块里
    total_len = 0
    for c in chunks:
        toks = tokenize(c["text"])
        tf = Counter(toks)  # tf[词] = 这个块里出现几次
        docs.append({"chunk": c, "tf": tf, "len": len(toks)})
        for t in tf:
            df[t] += 1
        total_len += len(toks)
    avg_len = total_len / len(docs) if docs else 0
    return docs, df, avg_len


def _score(query_tokens, doc, df, avg_len, N) -> float:
    """单个块的得分。"""
    score = 0.0
    for t in query_tokens:
        f = doc["tf"].get(t, 0)
        if f == 0:
            continue
        idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
        denom = f + K1 * (1 - B + B * doc["len"] / avg_len)
        score += idf * f * (K1 + 1) / denom
    return score


def search(query: str, docs, df, avg_len, top_k: int = 3):
    """返回 [(分数, doc), ...]，按分数降序取前 top_k。"""
    qt = list(set(tokenize(query)))  # 去重
    if not qt or not docs:
        return []

    N = len(docs)
    scored = []
    for d in docs:
        s = _score(qt, d, df, avg_len, N)
        if s > 0:  # ← 只留有命中的
            scored.append((s, d))

    scored.sort(key=lambda x: -x[0])  # 按分数降序

    out = []
    for s, d in scored[:top_k]:
        out.append({
            "score": round(s, 2),
            "num": d["chunk"]["num"],
            "title": d["chunk"]["title"],
            "text": d["chunk"]["text"],
        })
    return out

if __name__ == '__main__':


    corpus = json.loads(
        (Path(__file__).parent / "corpus.json").read_text(encoding="utf-8")
    )
    docs, df, avg_len = build_index(corpus)
    print("块数:", len(docs), " 词表:", len(df), " 平均长度:", int(avg_len))

    for q in ["IAB node functionality", "multi-hop backhaul", "random access"]:
        print(f"\n=== {q} ===")
        for hit in search(q, docs, df, avg_len, top_k=3):
            print(f'  {hit["score"]:>6.2f}  §{hit["num"]}  {hit["title"][:40]}')