#验证json_schema不支持，只能靠手写的prompt和check_schema约束字段结构
from openai import OpenAIError

from json_probe import TEXT_A, TEXT_C, V2, V3, try_one

N = 5

JSON_OBJECT_RF = {"type": "json_object"}

SCHEMA_RF = {
    "type": "json_schema",
    "json_schema": {
        "name": "spec_extract",
        "schema": {
            "type": "object",
            "properties": {
                "clause": {"type": ["string", "null"]},
                "title": {"type": "string"},
                "network_nodes": {"type": "array", "items": {"type": "string"}},
                "is_procedure": {"type": "boolean"},
                "summary": {"type": "string"},
            },
            "required": [
                "clause", "title", "network_nodes", "is_procedure", "summary"
            ],
            "additionalProperties": False,
        },
    },
}


def probe_support(name, rf):
    print(f"\n===== 探测 {name} =====")
    try:
        status, raw = try_one(V2, TEXT_A, response_format=rf)
        print(f"  结果: {status}")
        print(f"  前 120 字: {raw[:120]}")
    except OpenAIError as e:
        print(f"  服务端拒绝: {type(e).__name__}: {str(e)[:200]}")


if __name__ == "__main__":
    probe_support("json_object", JSON_OBJECT_RF)
    probe_support("json_schema", SCHEMA_RF)

    for name, prompt in [("V2", V2), ("V3", V3)]:
        print(f"\n===== TEXT_C / {name} =====")
        ok = 0
        for i in range(1, N + 1):
            status, raw = try_one(prompt, TEXT_C)
            print(f"  [{i}/{N}] {status}")
            if status == "ok":
                ok += 1
                print(f"      {raw[:150]}")
        print(f"  → {name} on TEXT_C: {ok}/{N}")