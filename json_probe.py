import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
    timeout=30,
    max_retries=0,
)

MODEL = os.getenv("DEEPSEEK_MODEL")

TEXT_A = (
    "5.3.5 RRC Reconfiguration — The RRCReconfiguration message is used to modify "
    "the radio configuration of the UE. It is sent on SRB1 using the DCCH. Upon "
    "reception, the UE shall apply the new configuration and, if successful, send "
    "RRCReconfigurationComplete to the network. If the reconfiguration fails, the "
    "UE shall initiate the RRC Connection Re-establishment procedure as specified "
    "in clause 5.3.7."
)

TEXT_B = (
    "7.2.1 PDCP Duplication — PDCP duplication may be configured by RRC for "
    "signaling radio bearers and data radio bearers. When duplication is activated, "
    "the same PDCP PDU is submitted to both RLC entities associated with the same "
    "PDCP entity. Duplication is controlled by the MAC layer through "
    "activation/deactivation MAC CE."
)

V1 = "把用户给的文档整理成 JSON。"
TEXT_C = (
    "4.4.1 Network Slicing — Network slicing allows the operator to create multiple "
    "logical networks on a common physical infrastructure. Each slice is identified "
    "by an S-NSSAI, which consists of a Slice/Service Type (SST) and an optional "
    "Slice Differentiator (SD)."
)

V1 = "把用户给的文档整理成JSON。"


V2 = """只输出 JSON，不要 markdown 围栏，不要任何解释。
字段如下：
- clause：字符串或 null。条款号，如 "5.3.5"；文本里没有条款号就填 null。
- title：字符串。条款标题，去掉前面的条款号。
- network_nodes：字符串数组。只填网元名（UE、gNB、AMF 这类），不要填协议名或信道名；没有就填 []。
- is_procedure：布尔。描述"条件 → 动作"的流程时为 true，否则 false。
- summary：字符串。一句中文概括，不超过 50 字。"""

V3 = V2 + """
示例：
输入：2.1.1 HARQ Retransmission — HARQ retransmission is controlled by the MAC layer. The UE shall flush the soft buffer upon receiving a new data indication.
输出：{"clause": "2.1.1", "title": "HARQ Retransmission", "network_nodes": ["UE"], "is_procedure": true, "summary": "HARQ 重传由 MAC 控制，UE 收到新数据指示时清空软缓存。"}
"""


REQUIRED = {
    "clause": (str, type(None)),
    "title": str,
    "network_nodes": list,
    "is_procedure": bool,
    "summary": str,
}

#schema （模式） 模式检查，查验输出是否满足REQUIRED
def check_schema(d):
     # """返回 (是否结构合规: bool, 原因: str)"""
    if not isinstance(d, dict):
        return False, "顶层不是 JSON 对象"
    missing = [k for k in REQUIRED if k not in d]
    if missing:
        return False, "缺字段 " + ",".join(missing)
    for k, t in REQUIRED.items():
        if not isinstance(d[k], t):
            return False, f"{k} 类型错({type(d[k]).__name__})"
    return True, "ok"

def try_one(system_prompt: str, user_text: str,response_format=None) :#response_format=None 设置默认值
    """返回 (是否解析成功: bool, 原始输出: str)"""
    kwargs = {}
    if response_format is not None:
        kwargs["response_format"] = response_format
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        temperature=0,
        max_tokens=1500,
        stream=False,
        **kwargs
    )
    if resp.choices[0].finish_reason == "length":  # ← 新增 2 行
        print("被 max_tokens 截断，这条不计入 prompt 失败")
        return "truncated", resp.choices[0].message.content
    raw = resp.choices[0].message.content
    try:
        d = json.loads(raw)#把字符串转为dict
    except json.JSONDecodeError as e:
        print(f"非法 JSON: {e}")
        return "bad_json", raw

    ok, reason = check_schema(d)
    if not ok:
        print(f"字段不符: {reason}")
        return "bad_schema", raw

    return "ok", raw

if __name__ == "__main__":
    V = {"V1":V1, "V2":V2, "V3":V3}
    for term in range(1,11):
        print()
        print(f"=======================轮数：{term}=======================")
        for v in V.keys():
            print(f"----------{v}----------")
            status, raw = try_one(V[v], TEXT_A)
            print("结果：", status)
            print("原始输出前 200 字：")
            print(raw[:200])
        term += 1





