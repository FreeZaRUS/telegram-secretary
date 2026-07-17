import os
import sys
import types

# Установить env-переменные до импорта bot, чтобы не было KeyError
os.environ.setdefault("TELEGRAM_TOKEN", "dummy")
os.environ.setdefault("CLAUDE_API_KEY", "dummy")
os.environ["ALLOWED_USERNAMES"] = "alice,bob"
os.environ["ALLOWED_USER_IDS"] = "100,200"

# Заглушка anthropic — без неё import bot упадёт из-за отсутствия ключа
anthropic_stub = types.ModuleType("anthropic")
class _FakeAnthropicClient:
    def __init__(self, **kwargs):
        pass
anthropic_stub.Anthropic = _FakeAnthropicClient
sys.modules["anthropic"] = anthropic_stub

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
