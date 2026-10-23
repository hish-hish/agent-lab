import os
import time
import logging
import sys#sys.stdout让一起输出，不要流式，否则提示词会乱套
from platform import system
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

import logging

log = logging.getLogger("agent-lab")
log.setLevel(logging.DEBUG)                 # logger 自己接收 DEBUG 及以上

_fmt = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_fh = logging.FileHandler("app.log", encoding="utf-8")   # 文件：全量
_fh.setLevel(logging.DEBUG)

_sh = logging.StreamHandler(sys.stdout)                            # 屏幕：只看向上
_sh.setLevel(logging.INFO)

for h in (_fh, _sh):
    h.setFormatter(_fmt)
    log.addHandler(h)

load_dotenv(override=True)

#创建与大模型交互的客户端对象 （DEEPSEEK_API_KEY环境变量的名字，值是api key的值）
client = OpenAI(api_key=os.environ.get('DEEPSEEK_API_KEY'), base_url=os.getenv("DEEPSEEK_BASE_URL"),timeout=30,max_retries=0)

turn = 0#轮数
#与大模型交互 多轮对话
messages = [{"role": "system", "content": "You are a helpful assistant"}]
while True:
    turn += 1
    user_content = input("请输入您想要的内容:")

    if user_content != "退出" and user_content != "tuichu":
        messages.append({"role": "user", "content": user_content})
        assistant_content = None
        i = 0
        for attempt in range(3):
            try:
                i += 1
                t_first = time.perf_counter()
                response = client.chat.completions.create(
                    model=os.getenv("DEEPSEEK_MODEL"),
                    messages=messages,
                    stream=False,
                )
                t_end = time.perf_counter()

                elapsed = t_end - t_first
                assistant_content = response.choices[0].message.content
                print(assistant_content)

                log.debug(assistant_content)
                log.info("第 %d 轮完成 用时=%.2fs in=%d out=%d total=%d", turn, elapsed, response.usage.prompt_tokens,
                         response.usage.completion_tokens,response.usage.total_tokens)

                break

            except OpenAIError as e:
                if type(e).__name__ in ("APITimeoutError", "APIConnectionError", "RateLimitError",
                                            "InternalServerError"):
                    log.warning("第 %d/3 次失败 %s: %s", attempt + 1, type(e).__name__, e)
                    match type(e).__name__:
                        case "APITimeoutError":
                            log.warning("超时")
                            time.sleep(1)
                        case "APIConnectionError":
                            log.warning("网络问题")
                            time.sleep(1)
                        case "RateLimitError":
                            log.warning("限流")
                            time.sleep(1)
                        case "InternalServerError":
                            log.warning("服务端临时故障")
                            time.sleep(1)
                        case _:
                            log.warning("模型或程序问题")

                else:
                    log.error("第 %d 轮失败 %s: %s", turn, type(e).__name__, e)
                    break

        if assistant_content is None:
            break


        if assistant_content != None:
            messages.append({"role": "assistant", "content": assistant_content})

    else:
        break





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


