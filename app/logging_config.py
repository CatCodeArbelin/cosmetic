import logging


def setup_logging(log_level: str = 'INFO') -> None:
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    )
