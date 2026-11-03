#调用测试题库，验证模型回答的准确率
#验证引用率
import logging
import sys
from pathlib import Path
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from tool_call_demo import run_agent
from cases import CASES
from judge import judge

logging.getLogger().setLevel(logging.ERROR)      # ← 必须在 import 之后

results = []
for case in CASES:
    r = run_agent(case["question"])
    ok = judge(case, r["answer"])
    results.append({"case": case, "ok": ok, "answer": r["answer"]})

    mark = "✓" if ok else "✗"
    print(f'{case["id"]:2d} {mark}  {case["category"]:6s}  {case["question"][:26]}')

# ================= 统计 =================
# 1. 总准确率
#    ok_count = sum(1 for x in results if x["ok"])
#    print(f"总准确率：{ok_count}/{len(results)} = {ok_count/len(results)*100:.0f}%")
#
# 2. 分类准确率
#    先按 category 分组，再每组算 对/总
#
# 3. 错题清单
#    每个 ✗ 的题：id + must_contain + answer 前 100 字

ok_count = sum(1 for x in results if x["ok"])
print(f"总准确率：{ok_count}/{len(results)} = {ok_count/len(results)*100:.0f}%")

# 按类别分组
by_cat = {}
for x in results:
    cat = x["case"]["category"]
    if cat not in by_cat:           # 第一次见到这个类别
        by_cat[cat] = []            # 先建一个空列表
    by_cat[cat].append(x["ok"])     # 把这次的对错塞进去

#oks = [True, True, False, True, False]
#len(oks)      # 5    ← 列表里有 5 个东西，这是总数
#sum(oks)      # 3    ← 1+1+0+1+0 = 3，这是"对的个数"
for cat, oks in by_cat.items():
    print(f"  {cat:6s} {sum(oks)}/{len(oks)}")


#引用统计
CITE = re.compile(r"§\s*\d+(?:\.\d+)+")                    # §4.7.1
NUM  = re.compile(r"(?<![\d.])\d+(?:\.\d+)+(?![\d.])")     # 4.7.1（不带 §）

strong = sum(1 for x in results if CITE.search(x["answer"] or ""))
weak   = sum(1 for x in results
             if not CITE.search(x["answer"] or "")
             and NUM.search(x["answer"] or ""))

doc_cases = [x for x in results if x["case"]["category"] in ("长文档", "跨节推理")]
strong_doc = sum(1 for x in doc_cases if CITE.search(x["answer"] or ""))

n_all = len(results)
n_doc = len(doc_cases)
print(f"\n引用情况：")
print(f"  文档题带 §：      {strong_doc}/{n_doc} = {strong_doc/n_doc*100:.0f}%")
print(f"  全部 {n_all} 题带 §：  {strong}/{n_all} = {strong/n_all*100:.0f}%")
print(f"  全部 {n_all} 题只有数字编号：{weak}/{n_all}")

#错题清单
# 错题清单
wrong = [x for x in results if not x["ok"]]
if not wrong:
    print("\n全部答对")
else:
    print(f"\n错题清单（{len(wrong)} 道）：")
    for x in wrong:
        c = x["case"]
        ans = (x["answer"] or "（无答案）")
        print(f'  #{c["id"]} {c["question"][:26]}')
        print(f'     需要: {c["must_contain"]}')
        print(f'     实际: {ans[:100]}')

