"""
统一日志：写入 ~/.resume-genie/logs/python_app.log，并可选输出到 stderr。

与 Tauri 的约定：
- STEP:n 与 RESUME_DATA:... 必须仍写入 stdout（由 emit_step / emit_resume_data 完成），
  以便 Rust 侧解析；同时写入日志文件。
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

_CONFIGURED = False


def _log_dir() -> Path:
    return Path.home() / ".resume-genie" / "logs"


def _ensure_configured() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True
    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "python_app.log"
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    parent = logging.getLogger("resume_genie")
    parent.setLevel(logging.DEBUG)
    parent.propagate = False
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    parent.addHandler(fh)
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    parent.addHandler(sh)


def get_logger(name: str | None = None) -> logging.Logger:
    """子 logger 名形如 resume_genie.boss；name 通常传 __name__。"""
    _ensure_configured()
    suffix = name if name else "app"
    return logging.getLogger(f"resume_genie.{suffix}")


def emit_step(step: int) -> None:
    """唤醒脚本进度：写入日志 + stdout（供 Tauri 解析 STEP:）。"""
    line = f"STEP:{step}"
    get_logger("protocol").info(line)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def emit_resume_data(data: dict) -> None:
    """解析结果：写入日志 + stdout（供 Tauri 解析 RESUME_DATA:）。"""
    payload = json.dumps(data, ensure_ascii=False)
    line = f"RESUME_DATA:{payload}"
    get_logger("protocol").info(line)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()
