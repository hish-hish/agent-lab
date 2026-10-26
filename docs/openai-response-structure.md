# OpenAI 兼容接口的响应结构（DeepSeek 实测版）

> 用途：查"某个字段在哪一层、是什么类型"。
> 环境：`openai==3.35.1` + DeepSeek `deepseek-flash`，2026-10-24 实测。
> 官方依据：[DeepSeek Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion) 与本地 SDK 源码 `openai/types/chat/`。

---

## 1. 非流式响应（`stream=False`）

真实值取自一次工具调用返回。

```
resp                                        ← ChatCompletion
 ├── id: "chatcmpl-..."
 ├── object: "chat.completion"
 ├── created: 1761...
 ├── model: "deepseek-flash"
 ├── system_fingerprint: str | None
 ├── service_tier: str | None
 ├── metadata: dict | None
 ├── moderation: dict | None
 ├── usage: CompletionUsage                 ← token 统计（非流式才有）
 │    ├── prompt_tokens
 │    ├── completion_tokens
 │    ├── total_tokens
 │    ├── prompt_tokens_details.cached_tokens
 │    └── completion_tokens_details.reasoning_tokens   ← thinking 模式下才非 0
 └── choices: List[Choice]                 ← 通常只有 1 个元素
      └── [0]                              ← Choice
           ├── finish_reason: str          ← 见第 3 节
           ├── index: 0
           ├── logprobs: None
           └── message: ChatCompletionMessage
                ├── role: "assistant"
                ├── content: str | None    ← 普通回答的正文
                ├── reasoning_content: str | None   ← thinking 模式的思考过程
                └── tool_calls: List[ToolCall] | None
                     └── [0]               ← ChatCompletionMessageFunctionToolCall
                          ├── id: "call_00_ET_suAKAK2jQ0jZiUG72nnD6037"   str
                          ├── type: "function"                              str
                          ├── index: 0                                      int
                          └── function: Function
                               ├── name: "get_weather"                      str
                               └── arguments: '{"city": "北京"}'             str ← 是字符串！
```

---

## 2. 流式响应（`stream=True`）

`create()` 返回的不是 `ChatCompletion`，而是 `Stream`（可迭代对象，没有 `choices` / `usage` 属性）。

```
Stream                                     ← 只能迭代，每轮产出一个 ChatCompletionChunk
 └── for chunk in stream:
      └── ChatCompletionChunk
           ├── id / object / created / model     ← 每包都重复，不用管
           ├── system_fingerprint
           ├── obfuscation: str | None
           ├── service_tier
           ├── usage: CompletionUsage | None     ← 默认 None；需要 stream_options={"include_usage": True}
           └── choices: List[Choice]             ← 可能是空列表 []
                └── [0]                          ← Choice
                     ├── index: 0
                     ├── finish_reason: str | None ← 只有最后有内容的那包才有值
                     └── delta: ChoiceDelta
                          ├── role: "assistant" | None   ← 只有第一包有
                          ├── content: str | None        ← 正文增量，多包拼接
                          ├── reasoning_content: str | None
                          └── tool_calls: List[...] | None
```

**流式取内容的正确路径**：

```
chunk.choices[0].delta.content
```

不是 `chunk.choices[0].message.content`（流式里没有 `message`）。

---

## 3. `finish_reason` 的取值

| 值 | 含义 | 你的代码该做什么 |
|---|---|---|
| `"stop"` | 模型正常说完 | 读 `message.content`，结束 |
| `"tool_calls"` | **模型要求调用工具** | 执行 → 回填 `role="tool"` → 再请求 |
| `"length"` | 撞到 `max_tokens` 被截断 | 提高 `max_tokens`，或让模型分段输出 |
| `"content_filter"` | 被内容审核拦截 | 提示用户，不要重试 |
| `"function_call"` | 旧版工具调用（已废弃） | 忽略 |
| `"insufficient_system_resource"` | DeepSeek 特有：推理资源不足被中断 | 重试 |
| `"aborted"` | DeepSeek 特有：生成被中断 | 重试 |

**判断分支必须用 `finish_reason`，不能用 `content is None`**——因为 `content` 为空有多个原因（工具调用、截断、空回复）。

---

## 4. 两版结构的差异对照

| 维度 | `stream=False` | `stream=True` |
|---|---|---|
| 顶层类型 | `ChatCompletion` | `Stream`（迭代器） |
| 有 `usage` 吗 | ✅ 顶层直接有 | ❌ 需 `stream_options={"include_usage": True}` |
| 有 `choices` 吗 | ✅ 顶层直接有 | ❌ 在每一包的 `chunk.choices` |
| 取内容 | `choices[0].message.content` | `chunk.choices[0].delta.content` |
| 内容形态 | 一次性完整 | 分片递增（delta） |
| `finish_reason` | 一定是最终值 | 只有最后一包有 |
| 拿数据方式 | 读属性 | 迭代 |

---

## 5. 常用访问路径速查

```python
# 普通回答
resp.choices[0].message.content

# 停止原因
resp.choices[0].finish_reason

# token 用量
resp.usage.prompt_tokens / completion_tokens / total_tokens

# thinking 模式下的思考过程（DeepSeek 扩展字段）
resp.choices[0].message.reasoning_content

# 工具调用（第一条）
tc = resp.choices[0].message.tool_calls[0]
tc.id                        # 回填时用，必须一字不差
tc.function.name             # 决定调哪个函数
json.loads(tc.function.arguments)   # arguments 是字符串，要先解析

# 流式正文
for chunk in resp:
    piece = chunk.choices[0].delta.content   # 可能为 None，要判空
```

---

## 6. 四个高频误用

| 写法 | 报错 | 正确写法 |
|---|---|---|
| `tc.name` | `AttributeError` | `tc.function.name`（在 `function` 子对象下） |
| `tc.function.arguments["city"]` | `TypeError: string indices must be integers` | 先 `json.loads()` |
| 流式取 `chunk.choices[0].message.content` | `AttributeError` | `chunk.choices[0].delta.content` |
| 流式取 `stream.usage` | `AttributeError` | 循环里抓 `chunk.usage`（需开 `include_usage`） |

---

## 7. 怎么自己核实（不靠记忆）

```python
print(type(obj))            # 它到底是什么类
print(obj.model_dump())     # 整个转成 dict，所有字段与默认值一目了然
```

响应对象都是 pydantic 模型，`model_dump()` 比任何文档都准。

本地源码位置（`agent-lab\.venv\Lib\site-packages\openai\types\chat\`）：

| 文件 | 内容 |
|---|---|
| `chat_completion.py` | 非流式响应结构 |
| `chat_completion_chunk.py` | 流式 chunk 结构 |
| `chat_completion_message.py` | `message` 对象结构 |

---

## 8. 记忆口诀

> **非流式返回"结果"，流式返回"过程"。**
> 结果有 `message`、有 `usage`；过程只有 `delta`，`usage` 要自己攒。
>
> 工具调用时：`finish_reason` 说"我要工具"，`tool_calls` 给出"要什么"，`content` 是空的 —— 这是模型在**下单**，不是出错。
