import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage import Store


def test_store_roundtrip(tmp_path):
    s = Store(str(tmp_path / "d.json"))
    i = s.new_id()
    assert i == 1 and s.new_id() == 2
    s.data["tickets"]["123"] = {"owner": 42, "type": "support"}
    s.save()
    s2 = Store(str(tmp_path / "d.json"))
    assert s2.data["tickets"]["123"]["owner"] == 42
    assert s2.data["next_id"] == 3


if __name__ == "__main__":
    import tempfile
    test_store_roundtrip(Path(tempfile.mkdtemp()))
    print("store roundtrip ok")
