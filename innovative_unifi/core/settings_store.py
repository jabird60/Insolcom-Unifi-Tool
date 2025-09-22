import json, os
from typing import Optional

class SettingsStore:
    def __init__(self, filename: Optional[str] = None):
        if filename:
            self.path = filename
        else:
            home = os.path.expanduser("~")
            self.path = os.path.join(home, ".innovative_unifi_tool.json")
        self._data = {}
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            self._data = {}

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass

    def get_value(self, key: str, default=None):
        return self._data.get(key, default)

    def set_value(self, key: str, value):
        self._data[key] = value
        self.save()
