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
from openai import APITimeoutError, APIConnectionError, InternalServerError, RateLimitError
from rag.bm25 import build_index as _build_index, search as _bm25_search

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
    if len(body) > 2000:
        body = body[:2000] + f"…（已截断，原长 {len(body)} 字）"
    return body

# ============ RAG 检索 ============
_rag_index = None


def _load_rag():
    """懒加载：第一次调用才读 corpus.json 并建索引（1–2 秒）。"""
    global _rag_index
    if _rag_index is None:
        corpus = json.loads(
            (Path(__file__).parent / "rag" / "corpus.json").read_text(encoding="utf-8")
        )
        _rag_index = _build_index(corpus)
        log.info("RAG 索引已加载：%d 块", len(_rag_index[0]))
    return _rag_index


def _to_english(query: str) -> str:
    """把中文问题转成英文检索关键词。语料是英文，直接拿中文搜一个词都匹配不上。"""
    resp = _create_with_retry(
        model=MODEL,
        messages=[
            {"role": "system", "content": (
                "把用户的问题转成用于检索英文技术文档的关键词。"
                "只输出关键词，用空格分隔，不要解释，不要标点。"
                "问题里的英文专有名词（如 IAB-MT、F1、NG-RAN）必须原样保留在输出里。"
            )},
            {"role": "user", "content": query},
        ],
        reasoning_effort="none",
        temperature=0,
        max_tokens=60,
    )
    return (resp.choices[0].message.content or "").strip()

#级间聚合
MAX_AGG_CHARS = 2500     # 聚合后总字符上限
MAX_AGG_SECTIONS = 2      # 最多聚合几个节


def _expand_by_section(hits: list[dict], corpus: list[dict]) -> list[dict]:
    # 进：hits   = BM25 返回的 [{score, num, title, text}, ...]（top-3，按分数降序）
    #      corpus = 全部 1406 块 [{num, title, text}, ...]
    # 出：[{num, title, text}, ...]  —— 聚合后的块列表
    # 硬约束：
    #   1. hits 里的块一定保留，而且排在前面
    #   2. 只聚合 hits 所属的节，最多 MAX_AGG_SECTIONS 个（按 hits 里首次出现的顺序）
    #   3. 同一节内：表格块（title 以 "表格" 开头）优先于其他正文块
    #   4. 各块 text 长度之和不超过 MAX_AGG_CHARS；超了就不再加（但继续看后面的短块）

    menu_list = []
    for h in hits:
        if h["num"] not in menu_list:
            if len(menu_list) < MAX_AGG_SECTIONS:
                menu_list.append(h["num"])

    result = []
    old_str = 0
    old_key = set()
    for h in hits:
        if h["num"] in menu_list:
            result.append(h)
            old_str += len(h["text"])
            old_key.add((h["num"],h["title"]))

    for num in menu_list:
        local_chunk = []
        for c in corpus:
            if c["num"] == num:
                local_chunk.append(c)

        table_chunk = []
        other_chunk = []
        for b in local_chunk:
            if b ["title"].startswith("表格"):
                table_chunk.append(b)
            else:
                other_chunk.append(b)

        for b in table_chunk:
            if (b["num"], b["title"]) in old_key:
                continue
            if old_str + len(b["text"]) > MAX_AGG_CHARS:
                continue
            result.append(b)
            old_str += len(b["text"])
            old_key.add((b["num"],b["title"]))

        for b in other_chunk:
            if (b["num"], b["title"]) in old_key:
                continue
            if old_str + len(b["text"]) > MAX_AGG_CHARS:
                continue
            result.append(b)
            old_str += len(b["text"])
            old_key.add((b["num"],b["title"]))
    return result


def search_docs(query: str) -> str:
    """按关键词检索 3GPP 正文，返回 top-3 段落，每段带 §条款号。"""
    docs, df, avg_len = _load_rag()
    en = _to_english(query)
    hits = _bm25_search(en, docs, df, avg_len, top_k=3)

    if not hits:
        return f"检索不到相关段落（检索词：{en}）。"

    corpus = [d["chunk"] for d in docs]
    expanded = _expand_by_section(hits, corpus)
    log.info(
        "search_docs query=%r en=%r hits=%d 聚合后=%d 块/%d 字符",
        query, en, len(hits), len(expanded), sum(len(b["text"]) for b in expanded),
    )

    blocks = [f'【§{b["num"]} {b["title"]}】\n{b["text"]}' for b in expanded]
    return f"（检索词：{en}）\n\n" + "\n\n".join(blocks)

#用文字给模型写一份说明书，模型按name，description，parameters生成数据，再dispatch这个name的函数
TOOLS = [{
    "type": "function",#声明是函数
    "function":{
        "name": "get_weather",
        "description":"用户问某城市天气如何",#判断什么时候调用
        "parameters": {
            "type": "object",#代表是一个对象，对应dict
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
},},},
{
    "type": "function",
    "function":{
        "name": "search_docs",
        "description":"按关键词检索 3GPP 规范正文。用户询问概念、术语、功能、流程，但没有给出具体章节号时使用。",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "用户的问题或关键词，用中文即可"}},
            "required": ["query"],
        "strict": True
},},}
]

TOOL_MAP = {
    "get_weather": get_weather,
    "calculator": calculator,
    "get_time": get_time,
    "get_doc_section": get_doc_section,
    "search_docs": search_docs,
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

    if tool_name == "search_docs":
        q = (args.get("query") or "").strip()
        args["query"] = q
        if not q:
            errors.append("缺少 query 参数")

    if tool_name == "calculator":
        expr = (args.get("expr") or "").strip()
        args["expr"] = expr
        if not expr:
            errors.append("缺少expr")

        elif not _ALLOWED_EXPR.match(expr):
            errors.append("表达式只能包含数字和 + - * / ( ) .")

    return errors

#加重试
RETRY = ("APITimeoutError", "APIConnectionError", "InternalServerError", "RateLimitError")
def _create_with_retry(**kwargs):
    """调模型，可重试的错误最多试 3 次，间隔 1s / 2s。"""
    for attempt in range(1, 4):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            name = type(e).__name__
            if name in RETRY:
                if attempt == 3:
                    raise
                wait = 2 ** (attempt - 1)
                log.warning("第 %d 次失败 %s，%d 秒后重试", attempt, name, wait)
                time.sleep(wait)
            else:
                raise


def run_agent(question: str) -> dict:
    # 用户指令
    messages = [{"role": "system", "content": (
            "回答涉及 3GPP 规范内容（例如 TS 38.300 的章节）时，"
            "必须在答案中标注条款号，格式为 §4.7.1。"
            "不要只写「第 4.7.1 节」或「4.7.1 节」，要写成 §4.7.1。"
            "用户给出具体章节号（如 4.7.1）时用 get_doc_section；"
            "用户只问概念、术语或功能（没有章节号）时用 search_docs 检索。"
        )},{"role": "user", "content": question}]

    # 进行循环对话
    MAX_ROUNDS = 5
    final_answer = None
    round_no = 1
    seen = {}  # 账本 用来记录之前是否问过

    # ReAct
    while round_no < MAX_ROUNDS + 1:  # ReAct

        resp = _create_with_retry(
            model=MODEL,
            messages=messages,
            tools=TOOLS,  # 这行决定调用工具
            tool_choice="auto",  # 强制调用，必须产出一个 tool_calls，不能文本输出 #tool_choice="none"禁止调工具，只说话
            # tool_choice="auto"自己决定 tool_choice={"type": "function", "function": {"name": "get_weather"}}调指定的
            # tool_choice="required" 必须调工具
            reasoning_effort="none",  # 关闭thinking
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
        # 上文出现stop则输出后停止，出现非stop且非"tool_calls"则报错异常
        # 下文表示出"tool_calls"的情况
        messages.append(msg)

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)  # arguments实参
            except json.JSONDecodeError:
                result = f"参数解析失败：{tc.function.arguments[:100]}"
            else:
                fn = TOOL_MAP.get(tc.function.name)  # 查tc.function.name是否在TOOL_MAP中
                fp = f"{tc.function.name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
                if tc.function.name != "get_time" and fp in seen:
                    result = f"重复调用：你刚用相同参数调过 {tc.function.name}，结果见上一条 tool 消息。请换参数，或直接回答。"
                else:
                    if fn is None:
                        result = f"未知工具：{tc.function.name}"
                    else:
                        errors = validate_args(tc.function.name, args)  # 模型给args后不进函数，先判断
                        if errors:
                            result = "参数校验失败：" + "；".join(errors)
                        else:
                            try:
                                result = fn(**args)  # fn首先是函数名，然后**把字典拆成关键字参数
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

    return {
            "ok": final_answer is not None,
            "answer": final_answer,
            "rounds": round_no,
            "reason": "stop" if final_answer else "no_answer",
        }

if __name__ == "__main__":
    result = run_agent("SPID 的取值范围和映射规则")
    print(result)



"""第一次：模型看到 [问题]，手里没有数据
        → 判断"我需要数据"
        → 有 tools 才能把这个判断变成 tool_calls
        → 所以：tools 是"必要条件"，不是"原因"

第二次：模型看到 [问题 + 工单 + 工具结果]
        → 判断"数据有了，可以答"
        → 不需要再要工具
        → 所以：输出文字"""
