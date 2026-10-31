import json
import logging
import sys
import ast
import time
import operator
import re

from json_probe import client,MODEL
from pathlib import Path
from docx import Document

#设置info输出
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

#天气数据库
_WEATHER = {
    "北京":"晴，26°C",
    "上海":"多云，29°C",
    "深圳":"雷阵雨，31°C"
}

def get_weather(city:str):
    if city in _WEATHER:
        return f"{city}:{_WEATHER[city]}"


_OPS = {
    ast.Add: operator.add,      # 加
    ast.Sub: operator.sub,      # 减
    ast.Mult: operator.mul,     # 乘
    ast.Div: operator.truediv,  # 除
    ast.Pow: operator.pow,      # 乘方
}

def calculator(expr: str) -> str:
    """只允许数字和 + - * / **，不用 eval"""

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -walk(node.operand)
        raise ValueError(f"不支持的表达式片段: {ast.dump(node)}")

    value = walk(ast.parse(expr, mode="eval"))
    return str(round(value, 6))


def get_time() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")#年月日时分秒

_doc_cache = None

def _load_doc() -> dict:
    """把 38.300 解析成 {条款号: 正文}，只解析一次，结果缓存。

    搬 docx_smoke.py 里那段循环：
      - 跳过 style 以 "toc" 开头的段落
      - 遇到 Heading 就记 num（"\t" 前那段）
      - 其余段落塞进当前 num 的正文列表
      - 返回 {num: "\n".join(body)}
    """
    global _doc_cache
    if _doc_cache is not None:
        return _doc_cache

    path = Path(__file__).parent / "data" / "38300-j40.docx"
    doc = Document(path)

    sections = {}
    cur = None
    for p in doc.paragraphs:
        style = p.style.name
        text = p.text.strip()
        if not text:
            continue
        if style.startswith("toc"):
            continue
        if style.startswith("Heading"):
            parts = p.text.split("\t")
            num = parts[0].strip() if len(parts) > 1 else ""
            if num:
                cur = num
                sections[num] = []
            else:
                cur = None
        elif cur is not None:
            sections[cur].append(p.text)

    _doc_cache = {k: "\n".join(v) for k, v in sections.items()}
    return _doc_cache


def get_doc_section(num: str) -> str:
    """返回某个条款的正文，最多 2000 字。

    要求：
    1. 从 _load_doc() 拿字典，按 num 取
    2. 取不到 → raise ValueError（让错误回填机制处理）
    3. 超过 2000 字 → 截断，末尾加 "…（已截断，原长 N 字）"
    """
    doc = _load_doc()
    if num not in doc:
        raise ValueError(f"没有「{num}」这一节，可查的编号如 4.7 / 5.3.5")

    body = doc[num]
    if len(body) > 800:
        body = body[:800] + f"…（已截断，原长 {len(body)} 字）"
    return body

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
},
{
    "type": "function",#声明是函数
    "function":{
        "name": "calculator",
        "description":"当用户想要进行简单的数学计算",#判断什么时候调用
        "parameters": {
            "type": "object",
            "properties": {
            "expr": {"type": "string", "description": "用户输入数据，类似1+1"}
            },
            "required": ["expr"]
        },
        "strict": True
},
},
{
    "type": "function",#声明是函数
    "function":{
        "name": "get_time",
        "description":"当用户想要现在的时间",#判断什么时候调用
        "parameters": {
            "type": "object",
            "properties": {},#有输入才描述
            "required": [],
        "strict": True
},},},
{
    "type": "function",#声明是函数
    "function":{
        "name": "get_doc_section",
        "description":"用户想要某章节的文段",#判断什么时候调用
        "parameters": {
            "type": "object",
            "properties": {"num": {"type": "string", "description": "用户输入的章节号，类似1.1"}},#有输入才描述
            "required": ["num"],
        "strict": True
},},}
]

TOOL_MAP = {
    "get_weather": get_weather,
    "calculator": calculator,
    "get_time": get_time,
    "get_doc_section": get_doc_section,
}


_ALLOWED_EXPR = re.compile(r"^[0-9+\-*/(). ]+$")

def validate_args(tool_name: str, args: dict) -> list[str]:
    """返回所有不合法原因；空列表 = 通过。"""
    errors: list[str] = []

    if tool_name == "get_weather":
        city = args.get("city")

        if not city:
            errors.append("缺少 city 参数")

        elif city not in _WEATHER:
            errors.append(f"没有「{city}」的天气数据，可查询：{'、'.join(_WEATHER)}")

    if tool_name == "calculator":
        expr = (args.get("expr") or "").strip()
        args["expr"] = expr
        if not expr:
            errors.append("缺少expr")

        elif not _ALLOWED_EXPR.match(expr):
            errors.append("表达式只能包含数字和 + - * / ( ) .")

    return errors

#用户指令
messages = [{"role": "user", "content": "5.3.5.1"}]

#进行循环对话
MAX_ROUNDS = 5
final_answer = None
round_no = 1
seen = {}#账本 用来记录之前是否问过

# ReAct
while round_no < MAX_ROUNDS + 1:# ReAct

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
    log.info("round=%d prompt_tokens=%d total=%d", round_no, resp.usage.prompt_tokens, resp.usage.total_tokens)
    fr = resp.choices[0].finish_reason
    msg = resp.choices[0].message

    if fr == "stop":
        final_answer = msg.content
        log.info("round=%d 结束 fr=stop 答案长度=%d", round_no, len(final_answer or ""))
        break
    if fr != "tool_calls":
        log.error(f"round = {round_no},异常终止,finish_reason = {fr}")
        break
    #上文出现stop则输出后停止，出现非stop且非"tool_calls"则报错异常
    #下文表示出"tool_calls"的情况
    messages.append(msg)

    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)#arguments实参
        fn = TOOL_MAP.get(tc.function.name)#查tc.function.name是否在TOOL_MAP中
        fp = f"{tc.function.name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
        if tc.function.name != "get_time" and fp in seen:
            result = f"重复调用：你刚用相同参数调过 {tc.function.name}，结果见上一条 tool 消息。请换参数，或直接回答。"
        else:
            if fn is None:
                result = f"未知工具：{tc.function.name}"
            else:
                errors = validate_args(tc.function.name, args)#模型给args后不进函数，先判断
                if errors:
                    result = "参数校验失败：" + "；".join(errors)
                else:
                    try:
                        result = fn(**args)#fn首先是函数名，然后**把字典拆成关键字参数
                    except Exception as e:
                        result = f"工具执行失败：{type(e).__name__}: {e}"
            seen[fp] = result
        log.info("round=%d tool=%s args=%s result_len=%d",
                 round_no, tc.function.name, args, len(result))

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
