import os
import time
from platform import system

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

load_dotenv(override=True)

#创建与大模型交互的客户端对象 （DEEPSEEK_API_KEY环境变量的名字，值是api key的值）
client = OpenAI(api_key=os.environ.get('DEEPSEEK_API_KEY'), base_url=os.getenv("DEEPSEEK_BASE_URL"))

#与大模型交互 多轮对话
messages = [{"role": "system", "content": "You are a helpful assistant"}]
while True:
    user_content = input("请输入您想要的内容:")

    if user_content != "退出":
        try:
            messages.append({"role": "user", "content": user_content})
            response = client.chat.completions.create(
                model=os.getenv("DEEPSEEK_MODEL"),
                messages=messages,
                stream=False,
            )

            system_content = response.choices[0].message.content
            print()
            print(system_content)
            print(f"提示词消耗tokens：{response.usage.prompt_tokens}")
            print(f"输出消耗tokens：{response.usage.completion_tokens}")
            print(f"总tokens：{response.usage.total_tokens}")

        except OpenAIError as e:
            print(type(e).__name__, e)

    else:
        break

    messages.append({"role": "system", "content": system_content})



#流式测验内容
# full_text = ""
# t_first = None
# usage = None
# stamp = []
# for chunk in response:
#     if chunk.usage:  # ① 最后一包：只有 usage
#         usage = chunk.usage
#         continue
#     if not chunk.choices:  # ② 空列表保险
#         continue
#     piece = chunk.choices[0].delta.content
#     if piece is None:  # ③ 首包/尾包没有内容
#         continue
#     if t_first is None:  # ④ 首字到达的时刻
#         t_first = time.perf_counter()
#     full_text += piece  # ⑤ 拼完整回复
#     print(piece, end="", flush=True)  # ⑥ 逐字输出
#     stamp.append(time.perf_counter())
# t_end = time.perf_counter()
# print()
# print(stamp[0] - t0,stamp[1] - stamp[0],stamp[2] - stamp[1], stamp[3] - stamp[2])
# print(stamp[-1] - stamp[-2])
# print(f"首字延时：{t_first - t0:.2f}, 总耗时 {t_end - t0:.2f},速率：{len(full_text) / (t_end - t_first):.2f}")
# print(f"提示词消耗tokens：{usage.prompt_tokens}")
# print(f"输出消耗tokens：{usage.completion_tokens}")
# print(f"总tokens：{usage.total_tokens}")
#


