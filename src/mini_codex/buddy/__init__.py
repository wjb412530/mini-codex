"""
电子宠物彩蛋模块 (buddy)
=======================

提供一个内置的小彩蛋，用户输入 `/buddy` 即可触发。
"""

from .companion import spawn_buddy

__all__ = ["spawn_buddy"]