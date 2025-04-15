import logging
import logging.config
import json
import os
from datetime import datetime

# 创建日志目录
os.makedirs('logs', exist_ok=True)

# 日志配置
LOG_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s'
        },
        'json': {
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'datefmt': '%Y-%m-%dT%H:%M:%S%z'
        }
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': f'logs/blockchain_{datetime.now().strftime("%Y%m%d")}.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'standard'
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': f'logs/error_{datetime.now().strftime("%Y%m%d")}.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'standard'
        }
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['console', 'file', 'error_file'],
            'level': 'DEBUG',
            'propagate': True
        }
    }
}

# 配置日志
logging.config.dictConfig(LOG_CONFIG)

# 创建模块级别的日志记录器
def get_logger(name):
    return logging.getLogger(name)