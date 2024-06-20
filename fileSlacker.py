import json
import logging
# from slack_bolt.adapter.socket_mode import SocketModeHandler
# from slack_bolt import App

slack_bolt_app = App()

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    try:
        logger.debug(f'## EVENT\n{str(event)}')
        logger.debug(f'## CONTEXT\n{str(context)}')
        # slack_event = json.loads(event["body"])
        logger.info(event["body"])
        return {
            'statusCode': 200,
        }
    except Exception as err:
        logger.error(err)
