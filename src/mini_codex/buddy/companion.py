"""
电子宠物彩蛋模块 (companion.py)
=============================
这是一个内置的小彩蛋，用户输入 `/buddy` 即可触发。
它使用了 Mulberry32 伪随机算法，根据当天的日期（或用户指定的种子）生成一只专属的"电子宠物"。
该功能主要用于娱乐和舒缓编程时的压力（类似于"小黄鸭调试法"）。
"""

import math
from datetime import datetime


# Mulberry32 伪随机数生成算法 (32-bit)
def mulberry32(a: int):
    def random():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = a
        t = (t ^ (t >> 15)) * (t | 1) & 0xFFFFFFFF
        t ^= (t + ((t ^ (t >> 7)) * (t | 61))) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0
    return random


# 宠物种类库
BUDDY_TYPES = [
    {"emoji": "\U0001F986", "name": "小黄鸭 (Duck)"},
    {"emoji": "\U0001F996", "name": "暴龙 (T-Rex)"},
    {"emoji": "\U0001F980", "name": "代码蟹 (Crab)"},
    {"emoji": "\U0001F9A5", "name": "树懒 (Sloth)"},
    {"emoji": "\U0001F999", "name": "羊驼 (Alpaca)"},
    {"emoji": "\U0001F989", "name": "猫头鹰 (Owl)"},
]

# 宠物性格库
PERSONALITIES = [
    "沉着冷静", "话痨", "社恐", "喜欢熬夜", "代码洁癖", "暴躁", "呆萌"
]


def spawn_buddy(seed_input: str = None) -> str:
    """
    根据种子生成一只电子宠物，返回宠物卡片文本。
    如果未提供种子，默认使用当天的日期字符串，同一天生成的宠物固定不变。
    """
    seed_string = seed_input if seed_input else datetime.now().strftime("%a %b %d %Y")

    seed_num = 0
    for char in seed_string:
        seed_num = ((seed_num << 5) - seed_num + ord(char)) & 0xFFFFFFFF

    if seed_num & 0x80000000:
        seed_num = -((seed_num ^ 0xFFFFFFFF) + 1)

    random_fn = mulberry32(abs(seed_num))

    type_index = math.floor(random_fn() * len(BUDDY_TYPES))
    pers_index = math.floor(random_fn() * len(PERSONALITIES))

    buddy = BUDDY_TYPES[type_index]
    personality = PERSONALITIES[pers_index]

    lines = [
        "彩蛋触发：你获得了一只电子宠物！",
        "=================================================",
        "   宠物: " + buddy["emoji"] + " " + buddy["name"],
        "   性格: " + personality,
        "   基因: " + seed_string,
        "=================================================",
        "（提示：它是你排 Bug 时的最佳倾听者，有事没事跟它吐吐槽）",
    ]
    return "\n".join(lines)