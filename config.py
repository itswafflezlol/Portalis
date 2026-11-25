import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "")

DEFAULTS = {
    "guild_id": 0,
    "staff_role_id": 0,
    "partnership_manager_role_id": 0,
    "freelancer_role_id": 0,
    "partner_role_id": 0,
    "ticket_category_id": 0,
    "ticket_log_channel_id": 0,
    "applications_channel_id": 0,
    "forum_channels": {"public": 0, "bedrock": 0, "smps": 0, "other": 0},
}

CONFIG_PATH = Path("config.json")


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    else:
        CONFIG_PATH.write_text(json.dumps(DEFAULTS, indent=2), encoding="utf-8")
    return cfg
