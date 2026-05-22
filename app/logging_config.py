import logging


class ContextDefaultsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key in ('dialog_id', 'message_id', 'external_chat_id', 'operator_id', 'action', 'error_type'):
            if not hasattr(record, key):
                setattr(record, key, '-')
        return True


def setup_logging(log_level: str = 'INFO') -> None:
    logging.basicConfig(level=log_level)
    root_logger = logging.getLogger()
    formatter = logging.Formatter(
        '%(asctime)s level=%(levelname)s logger=%(name)s action=%(action)s '
        'dialog_id=%(dialog_id)s message_id=%(message_id)s external_chat_id=%(external_chat_id)s '
        'operator_id=%(operator_id)s error_type=%(error_type)s msg="%(message)s"'
    )
    defaults_filter = ContextDefaultsFilter()

    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
        handler.addFilter(defaults_filter)
