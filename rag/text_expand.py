import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tool_call_demo import _expand_by_section

corpus = json.loads(
    (Path(__file__).parent / "corpus.json").read_text(encoding="utf-8")
)

hits = [c for c in corpus if c["num"] == "Annex G"]
for h in hits:
    h["score"] = 30.0

out = _expand_by_section(hits, corpus)

print("块数:", len(out))
print("总字符:", sum(len(b["text"]) for b in out))
for b in out:
    print(f'  {len(b["text"]):>5}  {b["num"]:<10} {b["title"][:40]}')