"""kb_cli/logging.py — 统一日志入口

使用：
    from kb_cli.logging import get_logger
    log = get_logger(__name__)
    log.info("索引加载完成")

通过环境变量 LOG_LEVEL 控制级别（DEBUG / INFO / WARNING / ERROR）。
默认 WARNING，避免在 CLI 正常使用时产生噪音。
"""
from __future__ import annotations

import logging
import os


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(handler)
    level_name = os.environ.get("LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    logger.setLevel(level)
    return logger
