def main() -> None:
    print(
        "agent-lab —— 手写 AI Agent 实验仓库\n"
        "\n"
        "直接运行具体脚本，例如：\n"
        "  uv run python hello_llm.py         # 最小 API 调用\n"
        "  uv run python chat_cli.py          # 多轮对话 CLI（流式 / 超时 / 分类重试）\n"
        "  uv run python json_probe.py        # 三版 prompt 结构化输出对照\n"
        "  uv run python ask_json.py          # 结构化输出封装 + 20 次跑批\n"
        "  uv run python tool_call_demo.py    # Function Calling 三工具\n"
        "  uv run python docx_smoke.py        # 3GPP docx 解析冒烟测试\n"
        "\n"
        "完整说明见 README.md"
    )
