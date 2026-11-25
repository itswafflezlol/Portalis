import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage import Store


def test_store_roundtrip(tmp_path):
    os.environ.pop("DATABASE_URL", None)  # force file backend

    async def go():
        s = Store(str(tmp_path / "d.json"))
        await s.connect()
        assert await s.new_id() == 1
        assert await s.new_id() == 2
        s.data["tickets"]["123"] = {"owner": 42, "type": "support"}
        await s.save()

        s2 = Store(str(tmp_path / "d.json"))
        await s2.connect()
        assert s2.data["tickets"]["123"]["owner"] == 42
        assert s2.data["next_id"] == 3

    asyncio.run(go())


if __name__ == "__main__":
    import tempfile
    test_store_roundtrip(Path(tempfile.mkdtemp()))
    print("store roundtrip ok")
