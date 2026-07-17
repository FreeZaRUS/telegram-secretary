import os
import sys
import types

os.environ.setdefault("TELEGRAM_TOKEN", "dummy")
os.environ.setdefault("GROQ_API_KEY", "dummy")
os.environ["ALLOWED_USERNAMES"] = "alice,bob"
os.environ["ALLOWED_USER_IDS"] = "100,200"

# Stub groq to prevent real API calls at import time
groq_stub = types.ModuleType("groq")

class _FakeGroqClient:
    def __init__(self, **kwargs):
        pass

groq_stub.Groq = _FakeGroqClient
sys.modules["groq"] = groq_stub

import importlib
bot = importlib.import_module("bot")


class FakeUser:
    def __init__(self, username, uid):
        self.username = username
        self.id = uid

class FakeUpdate:
    def __init__(self, username, uid):
        self.effective_user = FakeUser(username, uid)


def test_allowed_by_username():
    update = FakeUpdate("Alice", 999)
    assert bot.is_allowed(update) is True

def test_allowed_by_id():
    update = FakeUpdate(None, 100)
    assert bot.is_allowed(update) is True

def test_not_allowed():
    update = FakeUpdate("stranger", 999)
    assert bot.is_allowed(update) is False

def test_username_case_insensitive():
    update = FakeUpdate("BOB", 999)
    assert bot.is_allowed(update) is True
