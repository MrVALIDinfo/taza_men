from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

# Статусы жалобы:
#   draft        — AI принял фото, ждём место и подтверждение пользователя
#   rejected_ai  — AI отклонил фото (нет нарушения / фейк)
#   pending      — пользователь подтвердил, ждёт модерации администрации
#   approved     — инспектор подтвердил нарушение (жителю начисляются баллы)
#   rejected     — инспектор отклонил
#   cancelled    — пользователь отменил
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    lang        TEXT NOT NULL,
    username    TEXT,
    first_name  TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS complaints (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    photo_path   TEXT NOT NULL,
    file_id      TEXT NOT NULL,
    ai_json      TEXT,
    verdict      TEXT,
    violation_type TEXT,
    waste_type   TEXT,
    volume_m3    REAL,
    burning      INTEGER,
    confidence   REAL,
    lat          REAL,
    lon          REAL,
    address      TEXT,
    status       TEXT NOT NULL,
    moderator_id INTEGER,
    moderator_comment TEXT,
    moderated_at TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_complaints_user ON complaints(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
"""

# Колонки, которых может не быть в базе, созданной старой версией бота
MIGRATIONS = {
    "users": {"first_name": "TEXT"},
    "complaints": {
        "violation_type": "TEXT",
        "address": "TEXT",
        "moderator_id": "INTEGER",
        "moderator_comment": "TEXT",
        "moderated_at": "TEXT",
    },
}

# Что показываем на общей карте: только то, что дошло до администрации
MAP_STATUSES = ("pending", "approved")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._migrate()
        await self._conn.commit()

    async def _migrate(self) -> None:
        for table, columns in MIGRATIONS.items():
            async with self._conn.execute(f"PRAGMA table_info({table})") as cur:
                existing = {row["name"] for row in await cur.fetchall()}
            for column, column_type in columns.items():
                if column not in existing:
                    await self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        return self._conn

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        async with self.conn.execute(sql, params) as cur:
            return [dict(row) for row in await cur.fetchall()]

    async def _fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        async with self.conn.execute(sql, params) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    # --- пользователи ---

    async def get_lang(self, user_id: int) -> str | None:
        row = await self._fetchone("SELECT lang FROM users WHERE user_id = ?", (user_id,))
        return row["lang"] if row else None

    async def set_lang(self, user_id: int, lang: str, username: str | None, first_name: str | None) -> None:
        await self.conn.execute(
            """
            INSERT INTO users (user_id, lang, username, first_name, created_at) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                lang = excluded.lang, username = excluded.username, first_name = excluded.first_name
            """,
            (user_id, lang, username, first_name, _now()),
        )
        await self.conn.commit()

    async def update_names(self, user_id: int, username: str | None, first_name: str | None) -> None:
        """Обновляет имя для рейтинга (только у тех, кто уже выбрал язык)."""
        await self.conn.execute(
            "UPDATE users SET username = ?, first_name = ? WHERE user_id = ?",
            (username, first_name, user_id),
        )
        await self.conn.commit()

    # --- жалобы: бот ---

    async def count_today(self, user_id: int) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        row = await self._fetchone(
            "SELECT COUNT(*) AS n FROM complaints WHERE user_id = ? AND created_at >= ?",
            (user_id, today),
        )
        return row["n"]

    async def create_complaint(
        self,
        *,
        user_id: int,
        photo_path: str,
        file_id: str,
        ai_json: str,
        verdict: str,
        violation_type: str,
        waste_type: str,
        volume_m3: float,
        burning: bool,
        confidence: float,
        status: str,
    ) -> int:
        now = _now()
        cur = await self.conn.execute(
            """
            INSERT INTO complaints
                (user_id, photo_path, file_id, ai_json, verdict, violation_type, waste_type, volume_m3,
                 burning, confidence, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, photo_path, file_id, ai_json, verdict, violation_type, waste_type, volume_m3,
             int(burning), confidence, status, now, now),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def submit_complaint(
        self, complaint_id: int, *, lat: float | None, lon: float | None, address: str | None
    ) -> None:
        """Пользователь подтвердил обращение — оно уходит на модерацию."""
        await self.conn.execute(
            """
            UPDATE complaints SET lat = ?, lon = ?, address = ?, status = 'pending', updated_at = ?
            WHERE id = ?
            """,
            (lat, lon, address, _now(), complaint_id),
        )
        await self.conn.commit()

    async def set_status(self, complaint_id: int, status: str) -> None:
        await self.conn.execute(
            "UPDATE complaints SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), complaint_id),
        )
        await self.conn.commit()

    async def list_user_complaints(self, user_id: int, limit: int = 5) -> list[dict]:
        return await self._fetchall(
            """
            SELECT id, violation_type, status, created_at FROM complaints
            WHERE user_id = ? AND status NOT IN ('rejected_ai', 'cancelled', 'draft')
            ORDER BY id DESC LIMIT ?
            """,
            (user_id, limit),
        )

    # --- жалобы: Mini App ---

    async def map_points(self) -> list[dict]:
        placeholders = ",".join("?" * len(MAP_STATUSES))
        return await self._fetchall(
            f"""
            SELECT id, lat, lon, violation_type, waste_type, volume_m3, burning, status, created_at
            FROM complaints
            WHERE status IN ({placeholders}) AND lat IS NOT NULL AND lon IS NOT NULL
            ORDER BY id DESC LIMIT 2000
            """,
            MAP_STATUSES,
        )

    async def stats(self) -> dict:
        row = await self._fetchone(
            """
            SELECT
                SUM(status IN ('pending', 'approved', 'rejected')) AS total,
                SUM(status = 'pending') AS pending,
                SUM(status = 'approved') AS approved,
                COUNT(DISTINCT CASE WHEN status IN ('pending', 'approved', 'rejected') THEN user_id END) AS reporters
            FROM complaints
            """
        )
        return {key: int(value or 0) for key, value in row.items()}

    async def user_complaints(self, user_id: int, limit: int = 50) -> list[dict]:
        return await self._fetchall(
            """
            SELECT id, violation_type, waste_type, volume_m3, burning, status, lat, lon, address,
                   moderator_comment, created_at
            FROM complaints
            WHERE user_id = ? AND status IN ('pending', 'approved', 'rejected')
            ORDER BY id DESC LIMIT ?
            """,
            (user_id, limit),
        )

    async def leaderboard(self, limit: int = 10) -> list[dict]:
        return await self._fetchall(
            """
            SELECT c.user_id, u.first_name, u.username, COUNT(*) AS approved
            FROM complaints c LEFT JOIN users u ON u.user_id = c.user_id
            WHERE c.status = 'approved'
            GROUP BY c.user_id
            ORDER BY approved DESC, MIN(c.moderated_at) ASC
            LIMIT ?
            """,
            (limit,),
        )

    async def moderation_queue(self, limit: int = 50) -> list[dict]:
        return await self._fetchall(
            """
            SELECT c.*, u.first_name, u.username
            FROM complaints c LEFT JOIN users u ON u.user_id = c.user_id
            WHERE c.status = 'pending'
            ORDER BY c.burning DESC, c.id ASC LIMIT ?
            """,
            (limit,),
        )

    async def get_complaint(self, complaint_id: int) -> dict | None:
        return await self._fetchone("SELECT * FROM complaints WHERE id = ?", (complaint_id,))

    async def moderate(self, complaint_id: int, *, approved: bool, moderator_id: int, comment: str | None) -> bool:
        """Решение инспектора. False — если жалоба уже не ждёт модерации."""
        now = _now()
        cur = await self.conn.execute(
            """
            UPDATE complaints
            SET status = ?, moderator_id = ?, moderator_comment = ?, moderated_at = ?, updated_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            ("approved" if approved else "rejected", moderator_id, comment, now, now, complaint_id),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def approved_count(self, user_id: int) -> int:
        row = await self._fetchone(
            "SELECT COUNT(*) AS n FROM complaints WHERE user_id = ? AND status = 'approved'", (user_id,)
        )
        return row["n"]
