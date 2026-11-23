import os
import sqlite3
from pathlib import Path

数据目录 = Path(os.environ.get("数据目录", Path(__file__).resolve().parent.parent / "data"))
夹具目录 = Path(os.environ.get("夹具目录", Path(__file__).resolve().parent.parent.parent / "fixtures"))
库路径 = 数据目录 / "播浪.db"


def 连接() -> sqlite3.Connection:
    """独立连接。WAL + busy_timeout 保证多请求并发时读写可排队，不撕裂。"""
    数据目录.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(库路径, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA busy_timeout = 30000")
    try:
        c.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        
        pass
    return c
