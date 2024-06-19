import json
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.adapter.aws_lambda import SlackRequestHandler

slack_bolt_app = App()

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@slack_bolt_app.event("app_mention")
def handle_app_mention(ack, body, say, client):
    json_object = json.dumps(body, indent=4)
    logger.info(json_object)
    say(json_object)


if __name__ == "__main__":
    SocketModeHandler(slack_bolt_app).start()
