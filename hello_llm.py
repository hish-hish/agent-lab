import os
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

load_dotenv(override=True)

#创建与大模型交互的客户端对象 （DEEPSEEK_API_KEY环境变量的名字，值是api key的值）
client = OpenAI(api_key=os.environ.get('DEEPSEEK_API_KEY'), base_url=os.getenv("DEEPSEEK_BASE_URL"))


#与大模型交互
try:
    response = client.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL"),
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "1+1"},
        ],
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
    )
    print(response.choices[0].message.content)
    print(f"提示词消耗tokens：{response.usage.prompt_tokens}")
    print(f"输出消耗tokens：{response.usage.completion_tokens}")
    print(f"总tokens：{response.usage.total_tokens}")

except OpenAIError as e:
    print(type(e).__name__, e)


