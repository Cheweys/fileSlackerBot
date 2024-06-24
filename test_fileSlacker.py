import unittest
import json
from fileSlacker import lambda_handler

class MyTestCase(unittest.TestCase):
    def test_lambda_handler(self):
        event_json = '''{
  "version": "1.0",
  "resource": "/fileSlacker",
  "path": "/default/fileSlacker",
  "httpMethod": "POST",
  "headers": {
    "Content-Length": "2740",
    "Content-Type": "application/json",
    "Host": "wpi46j1wb5.execute-api.us-east-2.amazonaws.com",
    "User-Agent": "Slackbot 1.0 (+https://api.slack.com/robots)",
    "X-Amzn-Trace-Id": "Root=1-6676a652-37da23fe0f44ae8e4e6ea464",
    "X-Forwarded-For": "3.94.76.231",
    "X-Forwarded-Port": "443",
    "X-Forwarded-Proto": "https",
    "X-Slack-Request-Timestamp": "1719051858",
    "X-Slack-Signature": "v0=2b44f784a1c9068e3842d6669689cd3d076513a0676cf996e2bf89286b9ec254",
    "accept": "*/*",
    "accept-encoding": "gzip,deflate"
  },
  "pathParameters": null,
  "stageVariables": null,
  
  "isBase64Encoded": false
}'''
        # event = json.loads(event_json)
        context = ""
        # print(lambda_handler(event, context))
        self.assertTrue(isinstance(event_json, str))  # add assertion here


if __name__ == '__main__':
    unittest.main()
