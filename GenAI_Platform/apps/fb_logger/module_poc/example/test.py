import os
import fb_logging as log
logger = log.logger

logger.create_image("test_user", "test_workspace", "test_image", "pull")
logger.update_image("test_user", "test_workspace", "test_image")
logger.delete_image("test_user", "test_workspace", "test_image")

logger.create_dataset("test_user", "test_workspace", "test_dataset")
logger.update_dataset("test_user", "test_workspace", "test_dataset")
logger.delete_dataset("test_user", "test_workspace", "test_dataset")

logger.create_workspace("test_user", "test_workspace")
logger.update_workspace("test_user", "test_workspace")
# logger.delete_workspace("test_user", "test_workspace")

logger.create_training("test_user", "test_workspace", "test_training", "custom")
logger.update_training("test_user", "test_workspace", "test_training", "custom")

logger.create_job("test_user", "test_workspace", "test_job", "test_training")
logger.delete_job("test_user", "test_workspace", "test_job", "test_training")

logger.create_hps_group("test_user", "test_workspace", "test_hps", "test_training")
logger.create_hps_task("test_user", "test_workspace", "test_hps", "test_training", 1)
logger.create_hps_task("test_user", "test_workspace", "test_hps", "test_training", 2)
logger.delete_hps("test_user", "test_workspace", "test_hps", "test_training")

logger.delete_training("test_user", "test_workspace", "test_training", "custom")

logger.create_deployment("test_user", "test_workspace", "test_deployment")
logger.update_deployment("test_user", "test_workspace", "test_deployment")
logger.delete_deployment("test_user", "test_workspace", "test_deployment")


logger.set_level(log.DEBUG)
logger.debug("This is a debug message")
logger.info("This is an info message")
logger.error("This is an error message")

logger.debug("This is a multiline start message", multiline_start=True)
logger.info("This is a multiline continued message", multiline_continued=True)
logger.error("Level might not considered if continued :(", multiline_continued=True)

logger.set_level(log.INFO)
logger.debug("This debug message MUST NOT appear")
logger.info("This is an info message after changing log level")
logger.error("This is an error message after changing log level")

logger.set_level(log.ERROR)
logger.debug("This debug message MUST NOT appear")
logger.info("This info message MUST NOT appear")
logger.error("This is an error message after changing log level again")

def div_zero():
    return 1/0
try:
    a = div_zero()
except ZeroDivisionError as e:
    logger.stacktrace(e)
    logger.stacktrace(e, end_message=None)

logger.usage(data={"action": "test", "status": "success"})
logger.usage(data_string='{"nested": {"json": "test", "and": ["a", "r", "ray"]}, "hello": "world"}')
logger.usage(data={"another": "test", "with": {"nested": "data"}})

invalid_json_string = '{"invalid": "json",}'
logger.usage(data_string=invalid_json_string, skip_validation=True)

b = 2 / 0
print("Hi~")