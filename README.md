# agent-lab

从零手写 AI Agent 的实验仓库 —— 不依赖 LangChain / LlamaIndex / AutoGen，所有环节自己写一遍。

目标是搞清楚每件事**为什么这么做**，而不是把框架调通。所以每个脚本都可以单独跑，每个结论都有数字或日志支撑。

## 这是什么

8 天的实验记录，覆盖四块：

| 主题 | 做了什么 | 结果 |
|---|---|---|
| **API 调用** | 最小调用、参数实验、流式、多轮、超时与分类重试 | 摸清服务端的真实行为（含流式实际是批量下发这种反直觉发现） |
| **结构化输出** | 三版 prompt 对照、`response_format` 能力探测、清洗 + 重试修复 | prompt 约束强度 V1 0/10 → V2 10/10；封装后 20/20，平均 1.00 次/条 |
| **Function Calling** | tools schema、`tool_calls` 解析、两条消息回填、三出口循环、参数校验、错误回填 | 三工具（天气/计算器/时间），10 题测试 **10/10 选对**，全程无 400、无崩溃 |
| **文档解析** | 3GPP TS 38.300（V19.4.0）docx 解析 | 5567 段 / 15 表 / **617 节**，条款号自带，可按 `§4.3.1` 级引用 |

## 怎么跑

需要一台装了 [uv](https://docs.astral.sh/uv/) 的机器。Python 不用单独装，uv 会自己下载。

```bash
git clone https://github.com/hish-hish/agent-lab
cd agent-lab
uv sync

# 复制环境变量模板，填入自己的 key（去 https://platform.deepseek.com/api_keys 申请）
Copy-Item .env.example .env      # Windows PowerShell
cp .env.example .env             # macOS / Linux
```

然后任选一个脚本跑起来：

```bash
uv run python hello_llm.py          # 最小调用
uv run python tool_call_demo.py     # Function Calling 三工具
```

Windows 下如果中文输出乱码，先执行 `$env:PYTHONUTF8=1`。

## 现在能做什么

**Function Calling**（`tool_call_demo.py`）

- 三个工具：`get_weather(city)` / `calculator(expr)` / `get_time()`
- 分发表按 `name` 查函数（白名单，不用 `globals()`）
- 一轮可以调多个工具，每个工单各回填一条带 `tool_call_id` 的 `role="tool"` 消息
- 参数校验前置：不执行就能判断的错误在校验层拦下，必须执行才知道的错误（如 `7//2`、除零）在函数内 `raise`
- 工具异常**不往上抛**，转成错误文本回填 —— 模型能读懂并自我修正
- 循环三个出口：`stop` / 非 `tool_calls`（`length` 等）/ 达到 `MAX_ROUNDS`

**结构化输出**（`ask_json.py`）

- `ask_json(text, system_prompt=V2, max_retry=1) -> (dict | None, stats)`
- 清洗围栏 → `json.loads` → 字段校验 → 带具体错误的单次重试
- 跑批 20 次：20/20 成功，平均 1.00 次/条

**文档解析**（`docx_smoke.py`）

- 按 `Heading 1–5` 切节，输出 `num / title / level / body`
- 过滤 617 条目录项；章节号就在 `text` 里（`"4.3.1\tNG Interface"`）
- 结构自洽性检验：编号的点数 = `level - 1`

## 文件说明

| 文件 | 干什么 |
|---|---|
| `hello_llm.py` | 最小 API 调用，打印回复和 token 用量 |
| `temperature_probe.py` | `temperature=0` 到底有多确定（实测 4 次结果不同） |
| `chat_cli.py` | 多轮对话 CLI：流式、30s 超时、分类重试、优雅退出、双 handler 日志 |
| `json_probe.py` | 三版 prompt 对照实验，量化"约束强度"对合规率的影响 |
| `format_probe.py` | `response_format` 能力探测（`json_object` 可用 / `json_schema` 不可用） |
| `repair_probe.py` | 清洗 + 重试能救回多少（基线 0/10、只清洗 0/10、清洗+重试 10/10） |
| `ask_json.py` | 上面几件事封装成一个函数，并跑 20 次统计成功率 |
| `tool_call_demo.py` | 手写 Function Calling：三工具、分发表、参数校验、错误回填、三出口循环 |
| `docx_smoke.py` | 3GPP docx 解析冒烟测试（探结构、切节、验编号） |

## 文档

- [`docs/openai-response-structure.md`](docs/openai-response-structure.md) —— 响应结构速查（非流式 / 流式 / `finish_reason` 全取值 / 常用访问路径）
- [`docs/mcp-architecture.md`](docs/mcp-architecture.md) —— MCP 架构笔记（三角色、两层、三类原语，以及与 Function Call 的分层关系）

## 几个已验证的服务端能力边界

这些是实测出来的，不是看文档抄的：

- `response_format` 只支持 `text` / `json_object`，**没有 `json_schema`** → 结构化保证只能靠 prompt + 客户端校验
- tool calling 的 `strict: True` **可用**（Beta）→ 工具参数是这套系统里唯一有服务端强约束的地方
- `tool_choice="required"` 在 thinking 模式下 **400**，需配合 `reasoning_effort="none"`
- `tool_choice="required"` 对每一轮都生效，会把 `stop` 出口封死 → 必须写成 `"required" if round == 1 else "auto"`
- 流式实测 chunk 间隔 0.1ms、速率 567 字/秒（`curl -N` 绕过 SDK 复现）→ 服务端是聚合后批量下发，不是逐 token 推送

## 已知限制

这个仓库是**学习过程**，不是成品：

- 没有界面、没有部署，全是脚本和 CLI
- 工具都是本地假数据或模拟实现，没接真实业务系统
- 只有 1 篇文档完成解析，RAG（检索 + 引用 + 拒答）还没做
- 主项目（3GPP 规范问答 Agent + 告警日志查询）在后续阶段，会把上面几块拼起来

## 技术选型

- **不用 Agent 框架**：手写一遍才知道 `tool_call_id` 为什么必填、`finish_reason` 为什么不能靠 `content` 判断
- **`uv` 管依赖**：锁文件保证别人 clone 下来装出一样的环境
- **日志双 handler**：文件留 DEBUG、屏幕只看 INFO，排查时不用改代码

## 许可

MIT
