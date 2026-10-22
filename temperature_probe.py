#随机性检验 temperature：0-2 越低越确定，越高越不稳定
#结论：temperature=0 不保证可复现 —— 4 次采样 completion_tokens = 708/647/501/498，极差 210（42%）
#同温度自波动 > 温度间差异，故温度对比必须多次采样取均值，单次对比无效
import os
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

load_dotenv(override=True)

#创建与大模型交互的客户端对象 （DEEPSEEK_API_KEY环境变量的名字，值是api key的值）
client = OpenAI(api_key=os.environ.get('DEEPSEEK_API_KEY'), base_url=os.getenv("DEEPSEEK_BASE_URL"))


#与大模型交互
for t in [0, 0.7, 1.9, 0]:
    try:
        print(f"\n---------temperature = {t}---------")
        response = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL"),
            messages=[
                {"role": "system", "content": "你是一个非常热心的助手，善于将复杂的东西说明白"},
                {"role": "user", "content": "推荐三种周末的放松方式，并说明适合什么人"},
            ],
            temperature=t,
            stream=False,
        )
        print(response.choices[0].message.content)
        print(f"提示词消耗tokens：{response.usage.prompt_tokens},输出消耗tokens：{response.usage.completion_tokens},总tokens：{response.usage.total_tokens}")

    except OpenAIError as e:
        print(type(e).__name__, e)


