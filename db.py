"""
Lớp truy cập database dùng chung cho:
  - main.py (collector, chạy qua GitHub Actions): ghi lịch sử điểm số, đọc cấu hình
  - Streamlit app (Home.py + pages/): đọc lịch sử để hiển thị, ghi cấu hình/nhật ký

Dùng Postgres (khuyến nghị: Supabase free tier) thay vì SQLite vì Streamlit
Community Cloud có filesystem tạm thời - dữ liệu ghi trực tiếp từ web (Cấu hình,
Nhật ký) sẽ mất khi app khởi động lại nếu không lưu ở một DB bên ngoài container.
"""

import json
import os
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, text

import config as cfg

_engine = None


def get_engine():
    """Tạo (hoặc tái sử dụng) SQLAlchemy engine kết nối tới Postgres."""
    global _engine
    if _engine is None:
        dsn = os.environ.get("DB_URL") or cfg.DB_URL
        if not dsn:
            raise RuntimeError(
                "Chưa cấu hình DB_URL (connection string Postgres/Supabase). "
                "Xem README phần 'Thiết lập Supabase'."
            )
        _engine = create_engine(dsn, pool_pre_ping=True)
    return _engine


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS scores_history (
        id SERIAL PRIMARY KEY,
        run_time TIMESTAMPTZ NOT NULL,
        symbol TEXT NOT NULL,
        technical_score DOUBLE PRECISION,
        valuation_score DOUBLE PRECISION,
        combined_score DOUBLE PRECISION,
        zone TEXT,
        last_close DOUBLE PRECISION,
        rsi DOUBLE PRECISION,
        current_pe DOUBLE PRECISION,
        current_pb DOUBLE PRECISION,
        note TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_scores_symbol_time ON scores_history(symbol, run_time)",
    """
    CREATE TABLE IF NOT EXISTS app_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trade_journal (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        symbol TEXT NOT NULL,
        action TEXT NOT NULL,
        trade_date DATE NOT NULL,
        price DOUBLE PRECISION,
        quantity DOUBLE PRECISION,
        note TEXT,
        combined_score_at_time DOUBLE PRECISION,
        zone_at_time TEXT
    )
    """,
]


def init_db() -> None:
    """Tạo bảng nếu chưa tồn tại. Gọi an toàn nhiều lần (idempotent)."""
    engine = get_engine()
    with engine.begin() as conn:
        for stmt in SCHEMA_STATEMENTS:
            conn.execute(text(stmt))


# ───────────────────────── Cấu hình (watchlist, ngưỡng, trọng số) ─────────────────────────

def _get_config_value(key: str):
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(text("SELECT value FROM app_config WHERE key = :k"), {"k": key}).fetchone()
        return row[0] if row else None


def _set_config_value(key: str, value: str) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO app_config (key, value) VALUES (:k, :v)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """), {"k": key, "v": value})


def get_watchlist() -> list:
    val = _get_config_value("watchlist")
    return json.loads(val) if val else list(cfg.WATCHLIST)


def set_watchlist(symbols: list) -> None:
    _set_config_value("watchlist", json.dumps(symbols, ensure_ascii=False))


def get_thresholds() -> dict:
    val = _get_config_value("thresholds")
    if val:
        return json.loads(val)
    return {"cheap": cfg.ZONE_CHEAP_THRESHOLD, "expensive": cfg.ZONE_EXPENSIVE_THRESHOLD}


def set_thresholds(cheap: float, expensive: float) -> None:
    _set_config_value("thresholds", json.dumps({"cheap": cheap, "expensive": expensive}))


def get_weights() -> dict:
    val = _get_config_value("weights")
    if val:
        return json.loads(val)
    return {"technical": cfg.TECHNICAL_WEIGHT, "valuation": cfg.VALUATION_WEIGHT}


def set_weights(technical: float, valuation: float) -> None:
    _set_config_value("weights", json.dumps({"technical": technical, "valuation": valuation}))


# ───────────────────────────────── Lịch sử điểm số ─────────────────────────────────

def insert_scores(rows: list, run_time: datetime = None) -> None:
    """Ghi thêm (append) một lượt chạy vào lịch sử - KHÔNG ghi đè dữ liệu cũ."""
    run_time = run_time or datetime.now(timezone.utc)
    engine = get_engine()
    with engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO scores_history
                (run_time, symbol, technical_score, valuation_score, combined_score,
                 zone, last_close, rsi, current_pe, current_pb, note)
                VALUES (:run_time, :symbol, :technical_score, :valuation_score, :combined_score,
                        :zone, :last_close, :rsi, :current_pe, :current_pb, :note)
            """), {
                "run_time": run_time,
                "symbol": r.get("symbol"),
                "technical_score": r.get("technical_score"),
                "valuation_score": r.get("valuation_score"),
                "combined_score": r.get("combined_score"),
                "zone": r.get("zone"),
                "last_close": r.get("last_close"),
                "rsi": r.get("rsi"),
                "current_pe": r.get("current_pe"),
                "current_pb": r.get("current_pb"),
                "note": r.get("note"),
            })


def get_latest_scores() -> pd.DataFrame:
    """Bản ghi mới nhất của mỗi mã, sắp xếp theo combined_score giảm dần."""
    query = """
        SELECT s.* FROM scores_history s
        INNER JOIN (
            SELECT symbol, MAX(run_time) AS max_time FROM scores_history GROUP BY symbol
        ) latest ON s.symbol = latest.symbol AND s.run_time = latest.max_time
        ORDER BY s.combined_score DESC NULLS LAST
    """
    return pd.read_sql(text(query), get_engine())


def get_score_history(symbol: str) -> pd.DataFrame:
    query = "SELECT * FROM scores_history WHERE symbol = :symbol ORDER BY run_time ASC"
    return pd.read_sql(text(query), get_engine(), params={"symbol": symbol})


# ───────────────────────────────── Nhật ký giao dịch ─────────────────────────────────

def add_trade(symbol: str, action: str, trade_date: str, price: float, quantity: float,
              note: str, combined_score_at_time, zone_at_time) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO trade_journal
            (symbol, action, trade_date, price, quantity, note, combined_score_at_time, zone_at_time)
            VALUES (:symbol, :action, :trade_date, :price, :quantity, :note, :score, :zone)
        """), {
            "symbol": symbol, "action": action, "trade_date": trade_date,
            "price": price, "quantity": quantity, "note": note,
            "score": combined_score_at_time, "zone": zone_at_time,
        })


def get_trades(symbol: str = None) -> pd.DataFrame:
    engine = get_engine()
    if symbol:
        query = "SELECT * FROM trade_journal WHERE symbol = :symbol ORDER BY created_at DESC"
        return pd.read_sql(text(query), engine, params={"symbol": symbol})
    return pd.read_sql(text("SELECT * FROM trade_journal ORDER BY created_at DESC"), engine)
