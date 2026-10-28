#验证38300是可拆解可读的
from pathlib import Path

from docx import Document

path = Path(__file__).parent / "data" / "38300-j40.docx"
doc = Document(path)

sections = []
cur = None

for p in doc.paragraphs:
    style = p.style.name
    text = p.text.strip()
    if not text:
        continue
    if style.startswith("toc"):          # 目录项，跳过
        continue
    if style.startswith("Heading"):
        parts = p.text.split("\t")
        num = parts[0].strip() if len(parts) > 1 else ""
        title = parts[1].strip() if len(parts) > 1 else parts[0].strip()
        cur = {"num": num, "title": title, "level": int(style.split()[-1]), "body": []}
        sections.append(cur)
    elif cur is not None:
        cur["body"].append(p.text)

print("总节数:", len(sections))

with_body = [s for s in sections if s["body"]]
print("有正文的节:", len(with_body))
print("无正文的节（纯标题，多半是父节）:", len(sections) - len(with_body))

for s in with_body[:3]:
    body = "\n".join(s["body"])
    print(f"--- §{s['num']} {s['title']} | 层级 {s['level']} | 字数 {len(body)}")
    print(body[:150])
    print()

print("\n========== §4.7 整棵子树 ==========")
lines = []
for s in sections:
    if s["num"] == "4.7" or s["num"].startswith("4.7."):
        body = "\n".join(s["body"])
        indent = "  " * (s["level"] - 2)
        head = f"{indent}§{s['num']} {s['title']}   [L{s['level']}] {len(body)}字"
        print(head)
        lines.append(f"## §{s['num']} {s['title']}  (L{s['level']}, {len(body)} 字)\n")
        lines.append(body + "\n")
        if body:
            print("    " + body[:120].replace("\n", " "))

out = Path(__file__).parent / "4.7_excerpt.md"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"\n已导出：{out}")