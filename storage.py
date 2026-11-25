import json
from pathlib import Path


class Store:
    """Tiny JSON store: open tickets, pending applications, partner requests."""

    def __init__(self, path: str = "data/data.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"tickets": {}, "applications": {}, "partners": {}, "next_id": 1}
            self.save()

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def new_id(self) -> int:
        i = self.data["next_id"]
        self.data["next_id"] += 1
        self.save()
        return i
