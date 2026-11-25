import json
import os
from pathlib import Path

DEFAULT = {"tickets": {}, "applications": {}, "partners": {}, "next_id": 1}


class Store:
    """Open tickets + pending submissions. Persists to Postgres when
    DATABASE_URL is set, otherwise a local JSON file."""

    def __init__(self, path: str = "data/data.json"):
        self._pool = None
        self._path = Path(path)
        self.data = dict(DEFAULT)

    async def connect(self):
        dsn = os.getenv("DATABASE_URL")
        if dsn:
            import asyncpg

            self._pool = await asyncpg.create_pool(dsn)
            async with self._pool.acquire() as conn:
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS state"
                    " (id INT PRIMARY KEY, data JSONB NOT NULL)"
                )
                row = await conn.fetchrow("SELECT data FROM state WHERE id = 1")
                if row:
                    self.data = json.loads(row["data"])
                else:
                    await self._write(conn)
        elif self._path.exists():
            self.data = json.loads(self._path.read_text(encoding="utf-8"))
        else:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            await self.save()

    async def _write(self, conn):
        await conn.execute(
            "INSERT INTO state (id, data) VALUES (1, $1::jsonb)"
            " ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data",
            json.dumps(self.data),
        )

    async def save(self):
        if self._pool is not None:
            async with self._pool.acquire() as conn:
                await self._write(conn)
        else:
            self._path.write_text(
                json.dumps(self.data, indent=2), encoding="utf-8"
            )

    async def new_id(self) -> int:
        i = self.data["next_id"]
        self.data["next_id"] += 1
        await self.save()
        return i
