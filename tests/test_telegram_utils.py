import importlib
import sys
import types

# Stub out external dependencies required by utils.telegram_utils
telegram = types.ModuleType('telegram')
telegram.error = types.ModuleType('telegram.error')
class Update:  # minimal stub
    pass
class TelegramError(Exception):
    pass
class BadRequest(TelegramError):
    pass
telegram.Update = Update
telegram.error.TelegramError = TelegramError
telegram.error.BadRequest = BadRequest
sys.modules.setdefault('telegram', telegram)
sys.modules.setdefault('telegram.error', telegram.error)

logging_config = types.ModuleType('utils.logging_config')
class DummyLogger:
    def error(self, *args, **kwargs):
        pass
logging_config.logger = DummyLogger()
sys.modules.setdefault('utils.logging_config', logging_config)

telegram_utils = importlib.import_module('utils.telegram_utils')
escape_markdown_v2 = telegram_utils.escape_markdown_v2

def test_escape_special_characters():
    text = r"Escape []()~>#+=|{}.!- and \\backslashes"
    expected = r"Escape \[\]\(\)\~\>\#\+\=\|\{\}\.\!\- and \\\\backslashes"
    assert escape_markdown_v2(text) == expected

def test_inline_code_preserved():
    text = "Start `code [x](y) ~` end."
    expected = "Start `code [x](y) ~` end\\."
    assert escape_markdown_v2(text) == expected

def test_code_block_preserved():
    text = "Begin ```\nblock [x](y) -``` end."
    expected = "Begin ```\nblock [x](y) -``` end\\."
    assert escape_markdown_v2(text) == expected
