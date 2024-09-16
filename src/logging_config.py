import logging
import logging.config
import json
from pythonjsonlogger import jsonlogger

class UnicodeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, str):
            return obj.encode('utf-8').decode('utf-8')
        return super().default(obj)

class UnicodeJsonFormatter(jsonlogger.JsonFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, json_ensure_ascii=False, json_encoder=UnicodeEncoder, **kwargs)

logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'unicode_json': {
            '()': UnicodeJsonFormatter,
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
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
            'level': 'INFO',
        },
    },
})

logger = logging.getLogger(__name__)
