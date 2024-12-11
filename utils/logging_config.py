import json
import logging
import logging.config
from pythonjsonlogger import jsonlogger
from config import LOG_LEVEL

class UnicodeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, str):
            return obj.encode('utf-8').decode('utf-8')
        return super().default(obj)

class UnicodeJsonFormatter(jsonlogger.JsonFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, json_ensure_ascii=False, json_encoder=UnicodeEncoder, **kwargs)

def configure_logging():
    logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'unicode_json': {
            '()': UnicodeJsonFormatter,
            'format': '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'unicode_json',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
        },
    },
    })
    log = logging.getLogger(__name__)

    return log

logger = configure_logging()
