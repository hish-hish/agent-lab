#测试用题
CASES = [
    # ── 单工具（3）──
    {"id": 1, "category": "单工具", "question": "北京今天天气怎么样",
     "must_contain": ["26"]},
    {"id": 2, "category": "单工具", "question": "123 乘 456 等于多少",
     "must_contain": ["56088"]},
    {"id": 3, "category": "单工具", "question": "现在几点了",
     "must_contain": ["2026"]},

    # ── 多工具（2）──
    {"id": 4, "category": "多工具", "question": "北京和上海今天哪个更热",
     "must_contain": ["26", "29"]},
    {"id": 5, "category": "多工具", "question": "现在几点，顺便看下北京天气",
     "must_contain": ["2026", "26"]},

    # ── 长文档（3）──
    {"id": 6, "category": "长文档", "question": "38.300 里 4.7.1 讲了什么",
     "must_contain": ["IAB", "donor"]},
    {"id": 7, "category": "长文档", "question": "38.300 里IAB-node 的两部分功能分别是什么",
     "must_contain": ["DU", "MT"]},
    {"id": 8, "category": "长文档", "question": "4.7.4.1 讲了什么",
     "must_contain": ["38.401"]},

    # ── 异常边界（3）──
    {"id": 9, "category": "异常边界", "question": "杭州今天天气怎么样",
     "must_contain": ["上海"]},
    {"id": 10, "category": "异常边界", "question": "帮我查一下广州的天气",
     "must_contain": ["深圳"]},
    {"id": 11, "category": "异常边界", "question": "算子里的 abc 乘以 3",
     "must_contain": ["数字"]},

    # ── 跨节推理（3）──
    {"id": 12, "category": "跨节推理", "question": "4.7.1 这一节是讲什么的",
     "must_contain": ["IAB"]},
    {"id": 13, "category": "跨节推理", "question": "38.300 里IAB-donor 是什么",
     "must_contain": ["核心网"]},
    {"id": 14, "category": "跨节推理", "question": "4.7.2 讲的是什么",
     "must_contain": ["F1"]},

    # ── 计算（3）──
    {"id": 15, "category": "计算", "question": "(88+12)/5 等于多少",
     "must_contain": ["20"]},
    {"id": 16, "category": "计算", "question": "2 的 10 次方是多少",
     "must_contain": ["1024"]},
    {"id": 17, "category": "计算", "question": "9 乘 9 再乘 9 等于多少",
     "must_contain": ["729"]},

    # ── 拒答（3）──
    {"id": 18, "category": "拒答", "question": "华为基站的安装步骤是什么",
     "must_contain": []},
    {"id": 19, "category": "拒答", "question": "5G 套餐一个月多少钱",
     "must_contain": []},
    {"id": 20, "category": "拒答", "question": "100 除以 0 等于几",
     "must_contain": []},
]