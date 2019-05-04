import logging


def get_logger(logger_name: str, log_file_path: str) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.setLevel('DEBUG')
    file_handler = logging.FileHandler(log_file_path)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
