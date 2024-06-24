import json
import logging
import requests

# from slack_bolt.adapter.socket_mode import SocketModeHandler
# from slack_bolt import App

# slack_bolt_app = App()
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    try:
        # logger.debug(f'## EVENT\n{json.dumps(event)}')
        # logger.debug(f'## CONTEXT\n{json.dumps(context)}')
        slack_json = event['body']
        logger.debug(f"SLACK JSON:\n{slack_json}")
        slack_event = json.loads(slack_json)
        slack_file_url = slack_event['event']['files'][0]['url_private']
        logger.debug(f"SLACK FILE URL: {slack_file_url}")
        slack_file = get_slack_file(slack_file_url).content
        logger.info(type(slack_file))
        # TODO: push file to S3
        # TODO: push metadata to DB
        return {
            'statusCode': 200
        }
    except Exception as err:
        logger.error(err)
        return {
            'statusCode': 500
        }


def get_slack_file(url):
    try:
        return requests.get(url)
    except Exception as err:
        logger.error('Unable to retrieve file via Slack URL.')
        raise
