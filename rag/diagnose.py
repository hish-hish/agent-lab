import sys
import json
from pathlib import Path
from build_corpus import OUT_PATH

sys.path.insert(0, str(Path(__file__).parent))

from docx import Document
from build_corpus import load_sections, make_chunks, DOC_PATH

sections = load_sections()
chunks = make_chunks(sections)

print("=== 最大的 5 块 ===")
for c in sorted(chunks, key=lambda x: len(x["text"]), reverse=True)[:5]:
    print(f'{len(c["text"]):>6}  {c["num"]:<10} {c["title"][:50]}')



data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
big = [c for c in data if len(c["text"]) > 850]
print(f"\n=== 超过 850 字符的块：{len(big)} 个 ===")
for c in sorted(big, key=lambda x: -len(x["text"]))[:10]:
    print(f'{len(c["text"]):>6}  {c["num"]:<12} {c["title"][:40]}')