import time
import logging


from tool_call_demo import run_agent
logging.getLogger().setLevel(logging.WARNING)

QUESTION = "北京天气怎么样"
N = 10

results = []
total_cost = 0

for i in range(1, N + 1):
    t0 = time.time()
    r = run_agent(QUESTION)
    cost = time.time() - t0

    results.append({"ok": r["ok"], "rounds": r["rounds"], "cost": cost})
    print(f"{i:2d}  ok={r['ok']}  rounds={r['rounds']}  {cost:.1f}s")
    total_cost += cost
#统计部分
print()
ok_count = sum(1 for r in results if r["ok"])
print(f"完成率：{ok_count}/{len(results)} = {ok_count/len(results)*100:.0f}%")
print(f"平均轮数：{sum(r["rounds"] for r in results) / len(results)}")
print(f"平均耗时:{total_cost / N:.2f}")
