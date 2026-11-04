import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bm25 import build_index, search

data = json.loads((Path(__file__).parent / "corpus.json").read_text(encoding="utf-8"))
docs, df, avg_len = build_index(data)

queries = [
    "Annex G Mobility Latency components",
    "Annex F I-RNTI profile encoding",
    "Annex C reference profiles",
]

for q in queries:
    print(f"\n=== {q} ===")
    for hit in search(q, docs, df, avg_len, top_k=15):
        print(f'  {hit["score"]:>6.2f}  {hit["num"]:<12} {hit["title"][:40]}')