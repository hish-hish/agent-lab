# agent-lab

从零手写 AI Agent 的实验仓库。第 1 天：跑通大模型 API 调用。

## 这是什么

- 用 `uv` 管理依赖和虚拟环境（Python 3.13）
- 一个 30 行的脚本，调用 DeepSeek 的 OpenAI 兼容接口，打印回复和 token 用量
- 不依赖任何 Agent 框架

项目结构：

```
agent-lab/
├── hello_llm.py     # 调模型的脚本
├── .env.example     # 环境变量模板
├── pyproject.toml   # 依赖声明
└── uv.lock          # 依赖锁文件
```

## 怎么跑

1. `git clone <仓库URL>`
2. `cd agent-lab`
3. `uv sync`
4. 复制一份环境变量模板，然后填入你自己的 key：

   - Windows PowerShell：`Copy-Item .env.example .env`
   - macOS / Linux：`cp .env.example .env`

   编辑 `.env`，把 `DEEPSEEK_API_KEY` 的值换成你自己的（去 [platform.deepseek.com](https://platform.deepseek.com/api_keys) 申请）
5. `uv run python hello_llm.py`

> 需要：一台装了 [uv](https://docs.astral.sh/uv/) 的机器。Python 不用单独装，uv 会自己下载。

## 输出示例

```
输入: "1+1"
输出:2
提示词消耗tokens：38
输出消耗tokens：16
总tokens：54
```
