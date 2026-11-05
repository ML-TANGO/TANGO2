import logging

class DeepSpeedFilter(logging.Filter):
    """Filter to block DeepSpeed messages and timing information."""
    def filter(self, record):
        if (hasattr(record, 'name') and 'deepspeed' in record.name.lower()) or \
           (hasattr(record, 'msg') and isinstance(record.msg, str) and 
            ('time (ms)' in record.msg or 'optimizer_' in record.msg or 
             'bwd_' in record.msg or '_microstep' in record.msg)):
            return False
        return True

def configure_logging():
    """Configure logging to filter out DeepSpeed messages and set appropriate levels."""
    # Apply the filter to the root logger
    root_logger = logging.getLogger()
    root_logger.addFilter(DeepSpeedFilter())

    # Silence specific DeepSpeed loggers
    for logger_name in ['deepspeed', 'deepspeed.comm', 'deepspeed.runtime', 
                       'deepspeed.runtime.engine', 'deepspeed.runtime.zero', 'deepspeed.utils']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL)
        logger.propagate = False

    # Monkey-patch DeepSpeed logging
    import deepspeed
    def completely_silent_log_dist(*args, **kwargs):
        return None
    deepspeed.utils.logging.log_dist = completely_silent_log_dist