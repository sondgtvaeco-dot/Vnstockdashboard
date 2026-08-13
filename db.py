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
    """
    CREATE TABLE IF NOT EXISTS futures_scores_history (
        id SERIAL PRIMARY KEY,
        run_time TIMESTAMPTZ NOT NULL,
        symbol TEXT NOT NULL,
        technical_score DOUBLE PRECISION,
        basis_score DOUBLE PRECISION,
        combined_score DOUBLE PRECISION,
        zone TEXT,
        last_close DOUBLE PRECISION,
        rsi DOUBLE PRECISION,
        basis DOUBLE PRECISION,
        basis_pct DOUBLE PRECISION,
        note TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_futures_scores_symbol_time ON futures_scores_history(symbol, run_time)",
    """
    CREATE TABLE IF NOT EXISTS futures_positions (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        entry_price DOUBLE PRECISION NOT NULL,
        quantity DOUBLE PRECISION NOT NULL,
        entry_date DATE NOT NULL,
        entry_score DOUBLE PRECISION,
        entry_zone TEXT,
        note TEXT,
        status TEXT NOT NULL DEFAULT 'Mở',
        exit_price DOUBLE PRECISION,
        exit_date DATE,
        closed_at TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_futures_positions_symbol ON futures_positions(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_futures_positions_status ON futures_positions(status)",
]

# Các cột chi tiết chỉ báo được thêm SAU khi bảng đã tồn tại ở một số môi trường
# (bạn đã chạy hệ thống trước khi có tính năng này) - dùng ALTER TABLE ... ADD
# COLUMN IF NOT EXISTS để bổ sung an toàn, không ảnh hưởng dữ liệu cũ đã có.
MIGRATION_STATEMENTS = [
    """
    ALTER TABLE scores_history
        ADD COLUMN IF NOT EXISTS macd DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS macd_signal DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS macd_hist DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS bb_percent_b DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS support DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS resistance DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS sma_20 DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS sma_50 DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS sma_200 DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS mfi DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS obv_trend TEXT
    """,
    """
    ALTER TABLE futures_scores_history
        ADD COLUMN IF NOT EXISTS macd DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS macd_signal DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS macd_hist DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS bb_percent_b DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS support DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS resistance DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS sma_20 DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS sma_50 DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS sma_200 DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS mfi DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS obv_trend TEXT
    """,
    """
    ALTER TABLE trade_journal
        ADD COLUMN IF NOT EXISTS asset_type TEXT DEFAULT 'Cổ phiếu'
    """,
]


def init_db() -> None:
    """Tạo bảng nếu chưa tồn tại, và bổ sung cột mới nếu bảng đã có từ trước. Gọi an toàn nhiều lần (idempotent)."""
    engine = get_engine()
    with engine.begin() as conn:
        for stmt in SCHEMA_STATEMENTS:
            conn.execute(text(stmt))
        for stmt in MIGRATION_STATEMENTS:
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
                 zone, last_close, rsi, current_pe, current_pb, note,
                 macd, macd_signal, macd_hist, bb_percent_b, support, resistance,
                 sma_20, sma_50, sma_200, mfi, obv_trend)
                VALUES (:run_time, :symbol, :technical_score, :valuation_score, :combined_score,
                        :zone, :last_close, :rsi, :current_pe, :current_pb, :note,
                        :macd, :macd_signal, :macd_hist, :bb_percent_b, :support, :resistance,
                        :sma_20, :sma_50, :sma_200, :mfi, :obv_trend)
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
                "macd": r.get("macd"),
                "macd_signal": r.get("macd_signal"),
                "macd_hist": r.get("macd_hist"),
                "bb_percent_b": r.get("bb_percent_b"),
                "support": r.get("support"),
                "resistance": r.get("resistance"),
                "sma_20": r.get("sma_20"),
                "sma_50": r.get("sma_50"),
                "sma_200": r.get("sma_200"),
                "mfi": r.get("mfi"),
                "obv_trend": r.get("obv_trend"),
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


def get_score_trend(symbol: str, limit: int = 20) -> list:
    """N giá trị combined_score gần nhất (cũ->mới) - dùng vẽ sparkline xu hướng."""
    query = """
        SELECT combined_score FROM scores_history
        WHERE symbol = :symbol ORDER BY run_time DESC LIMIT :limit
    """
    df = pd.read_sql(text(query), get_engine(), params={"symbol": symbol, "limit": limit})
    return df["combined_score"].iloc[::-1].tolist()


# ───────────────────────────────── Nhật ký giao dịch ─────────────────────────────────

def add_trade(symbol: str, action: str, trade_date: str, price: float, quantity: float,
              note: str, combined_score_at_time, zone_at_time, asset_type: str = "Cổ phiếu") -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO trade_journal
            (symbol, action, trade_date, price, quantity, note, combined_score_at_time, zone_at_time, asset_type)
            VALUES (:symbol, :action, :trade_date, :price, :quantity, :note, :score, :zone, :asset_type)
        """), {
            "symbol": symbol, "action": action, "trade_date": trade_date,
            "price": price, "quantity": quantity, "note": note,
            "score": combined_score_at_time, "zone": zone_at_time, "asset_type": asset_type,
        })


def get_trades(symbol: str = None) -> pd.DataFrame:
    engine = get_engine()
    if symbol:
        query = "SELECT * FROM trade_journal WHERE symbol = :symbol ORDER BY created_at DESC"
        return pd.read_sql(text(query), engine, params={"symbol": symbol})
    return pd.read_sql(text("SELECT * FROM trade_journal ORDER BY created_at DESC"), engine)


# ───────────────────────── Cấu hình & dữ liệu phái sinh (VN30F) ─────────────────────────

def get_futures_watchlist() -> list:
    val = _get_config_value("futures_watchlist")
    return json.loads(val) if val else list(cfg.FUTURES_WATCHLIST)


def set_futures_watchlist(symbols: list) -> None:
    _set_config_value("futures_watchlist", json.dumps(symbols, ensure_ascii=False))


def get_futures_thresholds() -> dict:
    val = _get_config_value("futures_thresholds")
    if val:
        return json.loads(val)
    return {"cheap": cfg.FUTURES_ZONE_CHEAP_THRESHOLD, "expensive": cfg.FUTURES_ZONE_EXPENSIVE_THRESHOLD}


def set_futures_thresholds(cheap: float, expensive: float) -> None:
    _set_config_value("futures_thresholds", json.dumps({"cheap": cheap, "expensive": expensive}))


def get_futures_weights() -> dict:
    val = _get_config_value("futures_weights")
    if val:
        return json.loads(val)
    return {"technical": cfg.FUTURES_TECHNICAL_WEIGHT, "basis": cfg.FUTURES_BASIS_WEIGHT}


def set_futures_weights(technical: float, basis: float) -> None:
    _set_config_value("futures_weights", json.dumps({"technical": technical, "basis": basis}))


def insert_futures_scores(rows: list, run_time: datetime = None) -> None:
    run_time = run_time or datetime.now(timezone.utc)
    engine = get_engine()
    with engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO futures_scores_history
                (run_time, symbol, technical_score, basis_score, combined_score,
                 zone, last_close, rsi, basis, basis_pct, note,
                 macd, macd_signal, macd_hist, bb_percent_b, support, resistance,
                 sma_20, sma_50, sma_200, mfi, obv_trend)
                VALUES (:run_time, :symbol, :technical_score, :basis_score, :combined_score,
                        :zone, :last_close, :rsi, :basis, :basis_pct, :note,
                        :macd, :macd_signal, :macd_hist, :bb_percent_b, :support, :resistance,
                        :sma_20, :sma_50, :sma_200, :mfi, :obv_trend)
            """), {
                "run_time": run_time,
                "symbol": r.get("symbol"),
                "technical_score": r.get("technical_score"),
                "basis_score": r.get("basis_score"),
                "combined_score": r.get("combined_score"),
                "zone": r.get("zone"),
                "last_close": r.get("last_close"),
                "rsi": r.get("rsi"),
                "basis": r.get("basis"),
                "basis_pct": r.get("basis_pct"),
                "note": r.get("note"),
                "macd": r.get("macd"),
                "macd_signal": r.get("macd_signal"),
                "macd_hist": r.get("macd_hist"),
                "bb_percent_b": r.get("bb_percent_b"),
                "support": r.get("support"),
                "resistance": r.get("resistance"),
                "sma_20": r.get("sma_20"),
                "sma_50": r.get("sma_50"),
                "sma_200": r.get("sma_200"),
                "mfi": r.get("mfi"),
                "obv_trend": r.get("obv_trend"),
            })


def get_latest_futures_scores() -> pd.DataFrame:
    query = """
        SELECT s.* FROM futures_scores_history s
        INNER JOIN (
            SELECT symbol, MAX(run_time) AS max_time FROM futures_scores_history GROUP BY symbol
        ) latest ON s.symbol = latest.symbol AND s.run_time = latest.max_time
        ORDER BY s.combined_score DESC NULLS LAST
    """
    return pd.read_sql(text(query), get_engine())


def get_futures_score_history(symbol: str) -> pd.DataFrame:
    query = "SELECT * FROM futures_scores_history WHERE symbol = :symbol ORDER BY run_time ASC"
    return pd.read_sql(text(query), get_engine(), params={"symbol": symbol})


def get_futures_score_trend(symbol: str, limit: int = 20) -> list:
    """N giá trị combined_score gần nhất (cũ->mới) cho phái sinh - dùng vẽ sparkline."""
    query = """
        SELECT combined_score FROM futures_scores_history
        WHERE symbol = :symbol ORDER BY run_time DESC LIMIT :limit
    """
    df = pd.read_sql(text(query), get_engine(), params={"symbol": symbol, "limit": limit})
    return df["combined_score"].iloc[::-1].tolist()


# ───────────────────────────────── Vị thế phái sinh (mở/đóng lệnh) ─────────────────────────────────

def open_futures_position(symbol: str, direction: str, entry_price: float, quantity: float,
                           entry_date: str, note: str, entry_score, entry_zone) -> None:
    """Mở 1 lệnh phái sinh mới - trạng thái mặc định 'Mở', chưa có giá đóng."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO futures_positions
            (symbol, direction, entry_price, quantity, entry_date, note, entry_score, entry_zone, status)
            VALUES (:symbol, :direction, :entry_price, :quantity, :entry_date, :note, :score, :zone, 'Mở')
        """), {
            "symbol": symbol, "direction": direction, "entry_price": entry_price,
            "quantity": quantity, "entry_date": entry_date, "note": note,
            "score": entry_score, "zone": entry_zone,
        })


def close_futures_position(position_id: int, exit_price: float, exit_date: str) -> None:
    """Đóng 1 lệnh đang mở - cập nhật giá đóng, ngày đóng, chuyển trạng thái 'Đã đóng'."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE futures_positions
            SET exit_price = :exit_price, exit_date = :exit_date,
                status = 'Đã đóng', closed_at = now()
            WHERE id = :id
        """), {"exit_price": exit_price, "exit_date": exit_date, "id": position_id})


def get_futures_positions(status: str = None) -> pd.DataFrame:
    """status: None (tất cả), 'Mở', hoặc 'Đã đóng'."""
    engine = get_engine()
    if status:
        query = "SELECT * FROM futures_positions WHERE status = :status ORDER BY created_at DESC"
        return pd.read_sql(text(query), engine, params={"status": status})
    return pd.read_sql(text("SELECT * FROM futures_positions ORDER BY created_at DESC"), engine)
