import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import logging
logging.getLogger().setLevel(logging.WARNING)

from tool_call_demo import run_agent

# 第一轮
r1 = run_agent("IAB-donor 是什么")
print("答1：", r1["answer"][:80])
print("history 条数：", len(r1["history"]))

# 第二轮：带上第一轮的 history，问"它"
r2 = run_agent("它的 CU 和 DU 怎么分工", history=r1["history"])
print("答2：", r2["answer"][:200])
print("history 条数：", len(r2["history"]))