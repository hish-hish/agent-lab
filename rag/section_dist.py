import json
from collections import Counter
from pathlib import Path

data = json.loads(
    (Path(__file__).parent / "corpus.json").read_text(encoding="utf-8")
)

# ① 每节有几块
cnt = Counter(c["num"] for c in data)

print("节数:", len(cnt))
print("块数最多的 12 个：")
for num, n in cnt.most_common(12):
    print(f"  {num:<14} {n} 块")

# ② 块的分布：几块的节各有几个
print("\n块数分布：")
dist = Counter(cnt.values())
for n_blocks, n_sections in sorted(dist.items()):
    print(f"  {n_blocks:>2} 块的节：{n_sections} 个")

print("\n" + "=" * 50)
blocks = [c for c in data if c["num"] == "9.2.3.5.2"]
total = sum(len(c["text"]) for c in blocks)

print(f"块数: {len(blocks)}   总字符: {total}   平均: {total // len(blocks)}")
print("\n前 6 块的标题和开头：")
for c in blocks:
    print(f"  {len(c['text']):>4}  {c['title'][:36]:<38} {c['text'][:50]!r}")