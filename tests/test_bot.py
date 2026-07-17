import os
import sys
import types

os.environ.setdefault("TELEGRAM_TOKEN", "dummy")
os.environ.setdefault("OPENROUTER_API_KEY", "dummy")
os.environ["ALLOWED_USERNAMES"] = "alice,bob"
os.environ["ALLOWED_USER_IDS"] = "100,200"

# Stub openai to prevent real API calls at import time
openai_stub = types.ModuleType("openai")

class _FakeOpenAIClient:
    def __init__(self, **kwargs):
        pass

openai_stub.OpenAI = _FakeOpenAIClient
sys.modules["openai"] = openai_stub

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

def test_wildcard_allows_anyone():
    import importlib, os
    os.environ["ALLOWED_USERNAMES"] = "*"
    os.environ["ALLOWED_USER_IDS"] = ""
    bot2 = importlib.reload(bot)
    update = FakeUpdate("total_stranger", 99999)
    assert bot2.is_allowed(update) is True
    # restore
    os.environ["ALLOWED_USERNAMES"] = "alice,bob"
    os.environ["ALLOWED_USER_IDS"] = "100,200"
