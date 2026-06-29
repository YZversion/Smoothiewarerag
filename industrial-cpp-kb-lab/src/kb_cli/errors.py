"""kb_cli/errors.py — 统一异常类型"""
from __future__ import annotations


class KBError(Exception):
    """知识库基础异常。"""


class KBIndexError(KBError):
    """索引构建 / 加载失败（scan / ctags / chunk / 文件缺失等）。"""


class KBSearchError(KBError):
    """检索阶段错误（rg 未找到、BM25 未加载等）。"""
