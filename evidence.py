#模型输出给出原文
import re


def pick_sentences(section_text: str, anchors: list[str], top_n: int = 10,max_chars: int = 2000) -> str:
    """进：section_text = 一节全文（可能 13000 字符）
        anchors = ["IAB-donor", "gNB"]（从断言里抽的）
        出：拼好的 10 个句子（用换行连），约 1500–2000 字符
        约束：
        1. 按 ". "  / "\n" 切句（英文句子用 ". " 切，**别用单个 "."**，否则 "§4.7.1"、"gNB." 会被切碎）
        2. 每句算"含几个锚点"（大小写不敏感）
        3. 按锚点数降序，取前 top_n 句
        4. **输出时按原顺序排**（不要按分数排，否则读起来是乱的）
        5. 锚点一个都没命中的句子不要（得分为 0 的不取）"""
    sentence_list = []
    for line in section_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        for par in line.split(". "):
            par = par.strip()
            if par:
                sentence_list.append(par)

    score_list = []
    for i, sentence in enumerate(sentence_list):
        sentence_lower = sentence.lower()
        hits = 0
        for a in anchors:
            if a.lower() in sentence_lower:
                hits += 1
        if hits > 0:
            score_list.append((hits,i))

    score_list.sort(key=lambda x: (-x[0],x[1]))

    down_list = [x[1] for x in score_list[:top_n]]

    # 表格行无条件带上：表格是结构化数据，锚点过滤对它有百害无一利
    chosen_set = set(down_list)
    for i, s in enumerate(sentence_list):
        if "|" in s:
            chosen_set.add(i)
    down_list = sorted(chosen_set)


    sentence_list_after = []
    for i in down_list:
        sentence_list_after.append(sentence_list[i])

    result = ""
    used = 0
    for sentence in sentence_list_after:
        if used + len(sentence) + 1 > max_chars:
            break
        result += sentence + "\n"
        used += len(sentence) + 1
    return result


def extract_spans(claim: str, picked: str) -> list[str]:
    """让 LLM 从候选句里挑编号，返回原句（不返回 LLM 生成的文本）。

    进：claim  = 断言
        picked = pick_sentences 的输出（每行一句，带编号）
    出：被选中的原句列表（逐字，来自 picked）
    """
    from tool_call_demo import _create_with_retry, MODEL

    # 给每句编号
    lines = [ln for ln in picked.split("\n") if ln.strip()]
    numbered = "\n".join(f"{i+1}. {ln}" for i, ln in enumerate(lines))

    if not lines:
        return []

    resp = _create_with_retry(
        model=MODEL,
        messages=[
            {"role": "system", "content": (
                "你是文献检索助手。给定若干编号的原文句子和一条结论，"
                "选出能支持该结论的句子编号。\n"
                "要求：\n"
                "1. 只输出编号，用逗号分隔，例如：1,3,5\n"
                "2. 最多选 4 个\n"
                "3. 如果结论包含多个并列要点（如「两部分」「三个步骤」），"
                "每个要点都要选至少一个编号\n"
                "4. 如果一个都找不到，只输出：NONE\n"
                "5. 不要输出任何解释、不要输出原文"
            )},
            {"role": "user", "content": f"【结论】{claim}\n\n【候选句子】\n{numbered}"},
        ],
        reasoning_effort="none",
        temperature=0,
        max_tokens=50,
    )
    text = (resp.choices[0].message.content or "").strip()

    if text.upper().startswith("NONE"):
        return []

    # 解析 "1,3,5"
    indices = []
    for part in re.split(r"[,，\s]+", text):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(lines):
                indices.append(idx)

    return [lines[i] for i in sorted(set(indices))]

def _norm(w):
    return re.sub(r"[^\w\-]", "", w.lower())

def trim_span(sentence: str, anchors: list[str], context: int = 40) -> str:
    """按锚点位置截断，两头用 ... 表示省略。纯代码，结果确定。

    进："The IAB-node, which consists of a mobile termination (MT) part and a
         distributed unit (DU) part, supports both access and backhaul."
        anchors = ["IAB-node", "MT", "DU"]
    出："The IAB-node, which consists of a mobile termination (MT) part and a
         distributed unit (DU) part, ..."
    """
    lower = sentence.lower()
    positions = []

    for a in anchors:
        al = a.lower()
        start = 0
        while True:
            idx = lower.find(al, start)
            if idx == -1:
                break
            positions.append((idx, idx + len(al)))
            start = idx + 1

    if not positions:
        return sentence

    lo = max(0, min(p[0] for p in positions) - context)
    hi = min(len(sentence), max(p[1] for p in positions) + context)

    # 对齐到词边界（不要切在单词中间）
    while lo > 0 and sentence[lo - 1] not in " \t\n":
        lo -= 1
    while hi < len(sentence) and sentence[hi] not in " \t\n":
        hi += 1
    text = sentence[lo:hi].strip()
    if lo > 0:
        text = "..." + text
    if hi < len(sentence):
        text = text + "..."
    return text

def verify_verbatim(spans: list[str], section_text: str) -> list[str]:
    # 进：spans = ["...the network side termination point, an gNB with additional IAB support."]
    #     section_text = 被引节全文（1844 或 2031 字符）
    # 出：校验通过的片段列表（可能为空）
    # 约束：
    #   1. 去掉片段里的 "..." 和 "…"
    #   2. 按空格切词
    #   3. 每个词去标点、转小写，检查是否在"原文词集合"里
    #   4. 有任何词不在 → 整个片段作废
    #   5. 片段去 ... 后短于 20 字符 → 作废
    old_words = set()
    for word in section_text.split():
        clean_word = _norm(word)
        if clean_word:
            old_words.add(clean_word)

    pass_list = []
    for par in spans:
        new_par = par.replace("...", " ").replace("…", " ")
        if "|" not in new_par and len(new_par.strip()) < 20:
            continue
        all_ok = True
        for word in new_par.split():
            clean_word = _norm(word)
            if not clean_word:
                continue
            if clean_word not in old_words:
                all_ok = False
                break
        if all_ok:
            pass_list.append(par)

    return pass_list


def build_evidence(answer: str, corpus: list[dict]) -> str:
    """胶水，从答案里抽引用 → 逐节摘依据 → 拼成依据区文本。"""
    from evals.cite_check import split_claims, extract_anchors, _section_text

    claims = split_claims(answer)
    if not claims:
        return ""

    blocks = []
    seen = set()

    for c in claims:
        anchors = extract_anchors(c["claim"], corpus)

        for cite in c["cites"]:
            if cite in seen:
                continue
            seen.add(cite)

            section = _section_text(cite, corpus)
            if not section:
                continue

            if anchors:
                picked = pick_sentences(section, anchors)
            else:
                # 没锚点：用兜底锚点（常见技术词）挑句子，表格块会被整块带上
                picked = pick_sentences(section, ["LTM", "UE", "gNB", "IAB", "RRC"])
            if not picked:
                continue
            spans = extract_spans(c["claim"], picked)
            spans = verify_verbatim(spans, section)

            if spans:
                trimmed = [trim_span(s, anchors) for s in spans]
                body = "\n".join(f"  {i}. {s}" for i, s in enumerate(trimmed, 1))
            else:
                body = "  （未在该节找到直接依据）"

            blocks.append(f"{cite}：\n{body}")

    if not blocks:
        return ""

    return "\n────———————————— 原文依据 ────————————————\n" + "\n\n".join(blocks)


if __name__ == "__main__":
    import logging
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent))
    logging.getLogger().setLevel(logging.WARNING)

    from tool_call_demo import run_agent, _load_corpus

    corpus = _load_corpus()

    questions = [
        "IAB-donor 是什么",
        "IAB-node 的两部分功能是什么",
        "LTM 的移动性中断时间由哪几部分组成",
    ]

    for q in questions:
        r = run_agent(q)
        ans = r["answer"] or ""
        ev = r.get("evidence", "")

        print("=" * 70)
        print("问：", q)
        print()
        print(ans)
        if ev:
            print(ev)
        else:
            print("\n（没有生成依据区）")
        print()
        print(f"答案 {len(ans)} 字 + 依据 {len(ev)} 字 | {r['rounds']} 轮")
        print()

