import json
import logging
import sys

from json_probe import client,MODEL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("agent-lab")

def get_weather(city:str):
    return f"{city}:rain，26度"

#用文字给模型写一份说明书，模型按name，description，parameters生成数据，再dispatch这个name的函数
TOOLS = [{
    "type": "function",#声明是函数
    "function":{
        "name": "get_weather",
        "description":"用户问某城市天气如何",#判断什么时候调用
        "parameters": {
            "type": "object",
            "properties": {
            "city": {"type": "string", "description": "城市名，中文"}
            },
            "required": ["city"]
        },
        "strict": True,
    }
}]

messages = [{"role": "user", "content": "今天天气怎么样"}]

#进行循环对话
MAX_ROUNDS = 5
final_answer = None
round_no = 1
while round_no < MAX_ROUNDS + 1:

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,  # 这行决定调用工具
        tool_choice="auto",#强制调用，必须产出一个 tool_calls，不能文本输出 #tool_choice="none"禁止调工具，只说话
        #tool_choice="auto"自己决定 tool_choice={"type": "function", "function": {"name": "get_weather"}}调指定的
        #tool_choice="required" 必须调工具
        reasoning_effort="none",#关闭thinking
        temperature=0,
        max_tokens=1500
    )
    fr = resp.choices[0].finish_reason
    msg = resp.choices[0].message
    if fr == "stop":
        final_answer = msg.content
        log.info("round=%d 结束 fr=stop 答案长度=%d", round_no, len(final_answer or ""))
        break
    if fr != "tool_calls":
        log.error(f"round = {round_no},异常终止,finish_reason = {fr}")
        break

    tc = msg.tool_calls[0]
    args = json.loads(tc.function.arguments)  # 得到get_weather
    if tc.function.name == "get_weather":
        result = get_weather(args["city"])  # 用args是因为json.loads后是dict
    else:
        result = f"未知工具：{tc.function.name}"
    log.info("round=%d tool=%s args=%s result_len=%d", round_no, tc.function.name, args, len(result))

    messages.append(msg)
    messages.append({
        "role": "tool",
        "tool_call_id": tc.id,
        "content": result,
    })
    round_no += 1

if final_answer is None:
    print(f"达到上限{MAX_ROUNDS}仍未得到答案")
else:
    print("最终答案：", final_answer)





# resp2 = client.chat.completions.create(
#     model=MODEL,
#     messages=messages,
#     temperature=0,
#     max_tokens=1500,
# )
#
# print("第二次 finish_reason:", resp2.choices[0].finish_reason)
# print("最终答案:", resp2.choices[0].message.content)#第一次的"空"是因为它在选工具，不是因为出错；第二次的"有"是因为你把答案递到它嘴边了。
"""第一次：模型看到 [问题]，手里没有数据
        → 判断"我需要数据"
        → 有 tools 才能把这个判断变成 tool_calls
        → 所以：tools 是"必要条件"，不是"原因"

第二次：模型看到 [问题 + 工单 + 工具结果]
        → 判断"数据有了，可以答"
        → 不需要再要工具
        → 所以：输出文字"""
