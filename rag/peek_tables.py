import json
from pathlib import Path

data = json.loads(
    (Path(__file__).parent / "corpus.json").read_text(encoding="utf-8")
)

for c in data:
    if c["num"].startswith("table-"):
        print("=" * 70)
        print(c["num"], "|", c["title"], "|", len(c["text"]), "字符")
        print(c["text"][:400])
print("#"*30)
for c in data:
    if "Mobility Latency" in c["text"] or "Table G-1" in c["text"]:
        print(f'{c["num"]:<12} | {c["title"][:44]} | {len(c["text"])}')