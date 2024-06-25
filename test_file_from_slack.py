# fetching a private Slack file with requests

import requests
import os

slack_token = os.environ['SLACK_TOKEN']
url = 'https://files.slack.com/files-pri/T077J3X3A6P-F0791QQ74DR/slack.png'

res = requests.get(url, headers={'Authorization': f'Bearer {slack_token}'})
res.raise_for_status()

with open('my_file.png', 'wb') as f:
    f.write(res.content)