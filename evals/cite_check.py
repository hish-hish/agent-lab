import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tool_call_demo import _normalize_num
from tool_call_demo import _load_corpus

CITE_ANY = re.compile(r"§\s*\d+(?:\.\d+)+|Annex\s+[A-H]\b|Table\s+[A-H]-\d+")
EN_TERM  = re.compile(r"[A-Za-z][A-Za-z0-9\-\.]{1,}")

STOP = {
    "3gpp", "ts", "tr", "the", "and", "for", "with", "this", "that", "see",
    "note", "is", "of", "to", "in", "on", "at", "by", "as", "be", "or",
    "an", "a", "if", "it", "we", "can", "not", "are", "was",
    "fig", "table", "figure","gpp", "xx", "xxx", "etc", "eg", "ie",
}

MAX_ANCHOR_DF = 30          # 锚点最多出现在多少个块里，超过就算"太泛"
_lower_cache = None


def _lower_texts(corpus: list[dict]) -> list[str]:
    """把所有块的 text 转小写，只做一次。

    不缓存的话：18 条断言 × 3 个锚点 × 1406 块 = 7.6 万次 lowercase，慢到十几秒。
    """
    global _lower_cache
    if _lower_cache is None:
        _lower_cache = [c["text"].lower() for c in corpus]
    return _lower_cache

def split_claims(answer: str) -> list[dict]:
    """把答案拆成"带引用的断言"。
    进：答案全文（可能 500–1500 字，含中文、markdown、表格）
    出：[{"claim": "那句话", "cites": ["§4.7.1", "Annex G"]}, ...]
       只保留"至少带一个引用"的那些句子
    约束：
      1. 按句号、问号、换行、竖线切（markdown 表格用 |）
      2. 一个句子里有多个引用 → 全收进 cites
      3. 句子里没有引用 → 丢掉（这次只核验"有引用的"）
      4. 句子里没有中文/英文实词（纯符号）→ 丢掉
    """
    line_list = answer.split("\n")
    sentence_list = []
    for line in line_list:
        line = line.strip()
        sentence = ""
        for s in line:
            if s in "。？":
                sentence_list.append(sentence)
                sentence = ""
            else:
                sentence += s
        if sentence:
            sentence_list.append(sentence)

    result = []
    for sentence in sentence_list:
        index_list = CITE_ANY.findall(sentence)
        if not index_list:
            continue
        if len(sentence.strip()) < 8:
            continue
        result.append({"claim": sentence.strip(), "cites": index_list,})
    return result

def extract_anchors(claim: str, corpus: list[dict] | None = None) -> list[str]:
    """从断言里抽"不该被翻译的英文锚点"。
    进："IAB-donor 是宿主基站（见 §4.7.1）"
    出：["IAB-donor"]
    约束：
      1. 去掉 STOP 里的常见词
      2. 去掉纯数字/纯标点
      3. 大小写不敏感去重
      4. 传了 corpus 时：出现块数 > MAX_ANCHOR_DF 的锚点视为"太泛"，丢掉
    """
    clean_sentence = CITE_ANY.sub("", claim)
    choices = EN_TERM.findall(clean_sentence)

    mark = []
    seen = set()
    for choice in choices:
        if choice.lower() in STOP:
            continue
        if choice.replace(".", "").replace("-", "").isdigit():
            continue
        if choice.lower() in seen:
            continue
        seen.add(choice.lower())
        mark.append(choice)

    #按"出现块数"筛掉太泛的锚点
    if corpus is not None:
        lower_texts = _lower_texts(corpus)
        kept = []
        for a in mark:
            df = sum(1 for t in lower_texts if a.lower() in t)
            if df <= MAX_ANCHOR_DF:
                kept.append(a)
        mark = kept

    mark.sort(key=len, reverse=True)
    return mark[:3]


def _result(claim: dict, anchors: list[str], supported: bool,
            found_in: str | None, reason: str) -> dict:
    return {
        "claim": claim["claim"],
        "cites": claim["cites"],
        "anchors": anchors,
        "supported": supported,
        "found_in": found_in,
        "reason": reason,
    }

def _section_text(cite: str, corpus: list[dict]) -> str:
    """按引用取那一节的全文（给 LLM 当证据）。"""
    clean = cite.replace("§", "").strip()
    m = re.match(r"Table\s+([A-H])-\d+", clean)
    if m:
        num = f"Annex {m.group(1)}"
    else:
        num = _normalize_num(clean)
    return "\n".join(c["text"] for c in corpus if c["num"] == num)

def _llm_judge(claim: str, section: str) -> str:
    """让模型判断：这段原文是否支持这个结论。"""
    from tool_call_demo import _create_with_retry, MODEL

    resp = _create_with_retry(
        model=MODEL,
        messages=[
            {"role": "system", "content": (
                "你是严格的审稿人。判断【原文段落】是否支持【结论】。"
                "只输出三个词之一：支持 / 部分支持 / 不支持。不要解释。"
            )},
            {"role": "user", "content": f"【结论】{claim}\n\n【原文段落】{section[:2500]}"},
        ],
        reasoning_effort="none",
        temperature=0,
        max_tokens=20,
    )
    return (resp.choices[0].message.content or "").strip()

def verify_claim(claim: dict, corpus: list[dict]) -> dict:
    """核验一条断言：它引的那几节里，有没有它说的东西。

    顺序很重要：
      ① 先查引用指向的节存不存在（编造条款号最严重，要优先暴露）
      ② 再查有没有英文锚点（没有就"无法核验"）
      ③ 最后查锚点在不在那一节里
    """
    # 【第 1 段】引用指向的节，找得到吗
    sections = []  # [(引用, 这一节全文), ...]
    parent_only = False  # 至少有一个引用指向"父节"

    for cite in claim["cites"]:
        clean = cite.replace("§", "").strip()

        # Table X-N → Annex X
        m = re.match(r"Table\s+([A-H])-\d+", clean)
        if m:
            num = f"Annex {m.group(1)}"
        else:
            num = _normalize_num(clean)

        text = ""
        for c in corpus:
            if c["num"] == num:
                text += c["text"] + "\n"

        if not text:
            # 有子节 → 它是父节（合法，但自己没正文）
            if any(c["num"].startswith(num + ".") for c in corpus):
                parent_only = True
            continue

        sections.append((cite, text))

    # 【第 2 段】一条都找不到
    if not sections:
        reason = "parent_section" if parent_only else "missing_section"
        return _result(claim, [], False, None, reason)

    # 【第 3 段】抽锚点（传 corpus，让 idf 筛选生效）
    anchors = extract_anchors(claim["claim"], corpus)
    if not anchors:
        return _result(claim, [], False, None, "no_anchor")

    # 【第 4 段】在找到的那几节里查锚点
    for cite, text in sections:
        lower = text.lower()
        for a in anchors:
            if a.lower() in lower:
                return _result(claim, anchors, True, cite, "ok")

    return _result(claim, anchors, False, None, "no_match")


if __name__ == "__main__":
    import logging
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))
    logging.getLogger().setLevel(logging.WARNING)

    from tool_call_demo import _load_corpus, run_agent
    from cases import CASES

    corpus = _load_corpus()
    print(f"语料：{len(corpus)} 块\n")

    all_claims = []
    for case in CASES:
        r = run_agent(case["question"])
        answer = r["answer"] or ""
        claims = split_claims(answer)
        for c in claims:
            v = verify_claim(c, corpus)
            v["case_id"] = case["id"]
            v["question"] = case["question"]
            all_claims.append(v)
        print(f'#{case["id"]:2d}  断言 {len(claims)} 条')

    total = len(all_claims)
    missing = sum(1 for c in all_claims if c["reason"] == "missing_section")
    parent = sum(1 for c in all_claims if c["reason"] == "parent_section")
    no_anchor = sum(1 for c in all_claims if c["reason"] == "no_anchor")
    checkable = total - missing - parent - no_anchor
    supported = sum(1 for c in all_claims if c["supported"])
    unsupported = checkable - supported

    print(f"\n断言总数：{total}")
    print(f"  编造引用（节不存在）：{missing}")
    print(f"  父节（合法但无正文）：{parent}")
    print(f"  无法核验（无英文锚点）：{no_anchor}")
    print(f"  可核验：{checkable}")
    print(f"    支持：{supported}")
    print(f"    不支持：{unsupported}")

    if checkable:
        print(f"\n引用主题一致性：{supported}/{checkable} = {supported / checkable * 100:.0f}%")
    print(f"可核验覆盖率：{checkable}/{total} = {checkable / total * 100:.0f}%")

    print("\n=== 有问题的断言 ===")
    for c in all_claims:
        if c["reason"] in ("no_match", "missing_section"):
            print(f'  #{c["case_id"]} [{c["reason"]}] {c["claim"][:60]}')
            print(f'      引用: {c["cites"]}')
            print(f'      锚点: {c["anchors"]}')



    # ===== LLM 抽检 =====
    import random
    random.seed(42)                    # 固定随机种子，保证可复现

    ok_claims = [c for c in all_claims if c["supported"]]
    n = len(ok_claims)
    sample = random.sample(ok_claims, n)

    print(f"\n=== LLM 抽检（{n} 条）===")
    agree = 0
    for c in sample:
        sec = _section_text(c["found_in"], corpus)
        verdict = _llm_judge(c["claim"], sec)
        good = "不支持" not in verdict
        agree += 1 if good else 0
        print(f'  {verdict:<6} {c["claim"][:55]}')

    print(f'\n规则判"支持"的 {n} 条里，LLM 认可 {agree} 条')
    print(f"估计假阳性率：{((n - agree) / n * 100):.0f}%")