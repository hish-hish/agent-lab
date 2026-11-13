"""3GPP 规范问答 —— Gradio 界面

跑法：uv run python app.py
然后浏览器打开 http://127.0.0.1:7860
"""
import logging

import gradio as gr


from tool_call_demo import run_agent

logging.getLogger().setLevel(logging.WARNING)


def chat_fn(message: str, chat_history: list[dict]):
    """一次提问。

    进：message       = 输入框里的文字
        chat_history  = 对话历史，[{"role": "user"|"assistant", "content": "..."}, ...]
    出：(清空后的输入框, 新历史, 本轮依据文本)
    """
    if not message.strip():
        return ("", chat_history, "")

    r = run_agent(message, history=chat_history)


    evidence = r["evidence"] or "(本轮没有生成依据)"

    return ("", r["history"], evidence)


def clear_fn():
    """清空对话。"""
    return [], ""


with gr.Blocks(title="5G NR 架构问答（TS 38.300）") as demo:
    gr.Markdown(
        "# 5G 接入网架构问答\n"
        "基于 **3GPP TS 38.300**\n\n"
        "支持多轮对话。答案下方附 **原文依据**，可逐字核对。"
    )

    chatbot = gr.Chatbot(label="对话", height=420)

    with gr.Row():
        msg = gr.Textbox(
            placeholder="例如：IAB-donor 是什么",
            show_label=False,
            scale=5,
            container=False,
        )
        send = gr.Button("提问", variant="primary", scale=1)
        clear = gr.Button("清空", scale=1)

    evidence = gr.Textbox(
        label="原文依据",
        lines=10,
        max_lines=24,
        interactive=False,
    )

    send.click(chat_fn, [msg, chatbot], [msg, chatbot, evidence])
    msg.submit(chat_fn, [msg, chatbot], [msg, chatbot, evidence])
    clear.click(clear_fn, None, [chatbot, evidence])


if __name__ == "__main__":
    demo.launch(share=True)