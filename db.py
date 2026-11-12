"""SQLite 持久化：文案结果存档 + 历史查询。

设计取舍（都是踩过坑才这么写的）：
- 数组字段（features / bullets / keywords）存 JSON 文本。SQLite 没有数组类型，
  而这里要的是"存档回溯"而不是"按数组元素查询"，不值得建关联表。
- 每次操作新开连接。sqlite3 连接默认不能跨线程，而批量接口用了线程池，
  共享一个连接会抛 ProgrammingError。本地文件开连接开销极小，换来线程安全。
- 开启 WAL 模式。默认 journal 下写会锁住整个库，批量写入时读请求全被卡住；
  WAL 让读写可以并发。
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "listings.db"

# 东八区，避免用 UTC 导致查出来的时间和本地差 8 小时
TZ = timezone(timedelta(hours=8))

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    features    TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    bullets     TEXT    NOT NULL,
    keywords    TEXT    NOT NULL,
    char_count  INTEGER NOT NULL,
    source      TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_listings_created ON listings (created_at DESC);
"""

COLUMNS = (
    "name", "category", "features", "title",
    "bullets", "keywords", "char_count", "source", "created_at",
)


def connect() -> sqlite3.Connection:
    """新开一个连接。调用方负责关闭，别跨线程传。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表并把库切到 WAL。可以重复调用。"""
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()
    finally:
        conn.close()


def now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _to_row(item: dict, listing: dict, created_at: str) -> tuple:
    """把请求和结果压成一行。数组字段序列化成 JSON。"""
    return (
        item["name"],
        item["category"],
        json.dumps(item["features"], ensure_ascii=False),
        listing["title"],
        json.dumps(listing["bullets"], ensure_ascii=False),
        json.dumps(listing["keywords"], ensure_ascii=False),
        listing["char_count"],
        listing["source"],
        created_at,
    )


def save_many(pairs: list[tuple[dict, dict]]) -> int:
    """一次事务写入一批 (请求, 结果)，返回实际写入条数。

    用同一个连接 + 一次 commit，20 条也就几毫秒。
    并发写 SQLite 会争锁，串行反而更快。
    """
    if not pairs:
        return 0

    created_at = now()
    rows = [_to_row(item, listing, created_at) for item, listing in pairs]

    conn = connect()
    try:
        conn.executemany(
            f"INSERT INTO listings ({', '.join(COLUMNS)}) "
            f"VALUES ({', '.join('?' * len(COLUMNS))})",
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def save_one(item: dict, listing: dict) -> int:
    """写入单条，返回自增 id。"""
    conn = connect()
    try:
        cur = conn.execute(
            f"INSERT INTO listings ({', '.join(COLUMNS)}) "
            f"VALUES ({', '.join('?' * len(COLUMNS))})",
            _to_row(item, listing, now()),
        )
        conn.commit()
        return int(cur.lastrowid or 0)
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for field in ("features", "bullets", "keywords"):
        d[field] = json.loads(d[field])
    return d


def list_history(limit: int = 10, source: str | None = None) -> list[dict]:
    """按时间倒序取历史记录。source 可选 mock / llm。"""
    sql = "SELECT * FROM listings"
    params: list = []
    if source:
        sql += " WHERE source = ?"
        params.append(source)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    conn = connect()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [_row_to_dict(r) for r in rows]


def count(source: str | None = None) -> int:
    """总条数，用于确认落库是否真的生效。"""
    sql = "SELECT COUNT(*) FROM listings"
    params: list = []
    if source:
        sql += " WHERE source = ?"
        params.append(source)

    conn = connect()
    try:
        return int(conn.execute(sql, params).fetchone()[0])
    finally:
        conn.close()
