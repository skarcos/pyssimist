import logging,logging.config,logging.handlers
 
LOG_CONFG = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s %(levelname)s %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        }
    },
    'handlers': {
        'console':{
            'level':'ERROR',
            'class':'logging.StreamHandler',
            'formatter': 'simple'
        },
        'logfile':{
            'level': 'DEBUG',
            'mode' : 'w',
            'class':'logging.FileHandler',
            'formatter': 'verbose',
            'filename' : r'CallTrace.txt'
        },
    },
    'root':{
        'handlers':['console','logfile'],
        'level':'DEBUG'
    }
}

logging.config.dictConfig(LOG_CONFG)
logger=logging.getLogger(__name__)
debug,info,warning,error,critical,exception=logger.debug,logger.info,logger.warning,logger.error,logger.critical,logger.exception
