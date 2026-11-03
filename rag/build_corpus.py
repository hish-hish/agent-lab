#构建语料库
import json
from pathlib import Path

from docx import Document

DOC_PATH = Path(__file__).parent.parent / "data" / "38300-j40.docx"
OUT_PATH = Path(__file__).parent / "corpus.json"

MAX_CHUNK = 800          # 单块最大字符数，和 D10 的截断阈值保持一致
DROP_NUMS = {"2"}    # 空编号（Foreword）+ §2 References
DROP_TITLE = "Void"      # 3GPP 的空占位节


def load_sections() -> list[dict]:
    """解析 docx，返回 [{num, title, level, body}]。
    这段直接搬 docx_smoke.py 里的循环。
    """
    doc = Document(DOC_PATH)
    sections = []
    cur = None
    for p in doc.paragraphs:
        style = p.style.name
        text = p.text.strip()
        if not text or style.startswith("toc"):
            continue
        if style.startswith("Heading"):
            parts = p.text.split("\t")
            if len(parts) > 1:
                num = parts[0].strip()
                title = parts[1].strip()
            elif text.startswith("Annex"):
                head = text.split("\n")[0]
                num = head.split("(")[0].strip().rstrip(":").strip()
                title = text[len(head):].strip() or num
            else:
                num = ""
                title = text
            if num:
                cur = {"num": num, "title": title,
                       "level": int(style.split()[-1]), "body": []}
                sections.append(cur)
            else:
                cur = None
        elif cur is not None:
            cur["body"].append(p.text)
    return sections

#判断是否抛弃
def should_drop(sec: dict) -> bool:
    return sec["num"] in DROP_NUMS or sec["title"] == DROP_TITLE


def split_long(text: str) -> list[str]:
    """把长文本切成多块，按列表输出，每块尽量不超过 MAX_CHUNK。"""
    pieces = []
    cur = ""
    for para in text.split("\n"):
        para = para.strip()
        if not para:#空字段，直接跳
            continue
        if len(para) > MAX_CHUNK:
            if cur:
                pieces.append(cur)
                cur = ""
            for k in range(0, len(para), MAX_CHUNK):
                pieces.append(para[k:k + MAX_CHUNK])
            continue
        if cur and len(cur) + len(para) + 1 > MAX_CHUNK:#cur有值，长度超了 +1是\n的换行符
            pieces.append(cur)
            cur = para
        elif cur:#cur有值，长度没超
            cur += "\n" + para
        else:#cur空值
            cur = para
    if cur:#不把最后一个cur拉下
        pieces.append(cur)
    return pieces


def make_chunks(sections: list[dict]) -> list[dict]:
    """过滤 + 判断是否切块 + 切块"""
    chunks = []
    for sec in sections:
        if should_drop(sec):  # 噪音节直接扔
            continue
        text = "\n".join(sec["body"]).strip()  # 段落列表拼成一段文本，中间用\n连接
        if not text:  # 纯父节（0 字）也扔
            continue
        if len(text) <= MAX_CHUNK:  # 短节：整节一块
            chunks.append({"num": sec["num"], "title": sec["title"], "text": text})
        else:  # 长节：切成多块
            for i, piece in enumerate(split_long(text)):
                chunks.append({
                    "num": sec["num"],
                    "title": f"{sec['title']} (part {i + 1})",
                    "text": piece,
                })
    return chunks


def load_tables() -> list[dict]:
    """导出所有表格，超过 MAX_CHUNK 的按行切块，每块带上表头。"""
    doc = Document(DOC_PATH)
    tables = []
    for i, table in enumerate(doc.tables, start=1):
        rows = []
        for row in table.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            rows.append(" | ".join(cells))
        if not rows:
            continue
        header = rows[0]
        if "Change history" in header:
            continue
        body_rows = rows[1:] if len(rows) > 1 else rows

        cur, cur_len, part = [], len(header) + 1, 1
        for r in body_rows:
            if cur and cur_len + len(r) + 1 > MAX_CHUNK:
                tables.append({
                    "num": f"table-{i}",
                    "title": f"表格 (part {part})",
                    "text": "\n".join([header] + cur),
                })
                part, cur, cur_len = part + 1, [], 0
            cur.append(r)
            cur_len += len(r) + 1
        if cur:
            tables.append({
                "num": f"table-{i}",
                "title": f"表格 (part {part})",
                "text": "\n".join([header] + cur),
            })
    return tables


if __name__ == "__main__":
    sections = load_sections()
    print("原始节数:", len(sections))

    chunks = make_chunks(sections)
    tables = load_tables()
    all_chunks = chunks + tables

    OUT_PATH.write_text(
        json.dumps(all_chunks, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    texts = [c["text"] for c in all_chunks]
    print("总块数:", len(all_chunks))
    print("  正文块:", len(chunks))
    print("  表格块:", len(tables))
    print("最大块字符数:", max(len(t) for t in texts))
    print("平均块字符数:", sum(len(t) for t in texts) // len(texts))
    print("已写入:", OUT_PATH)