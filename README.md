# fileSlackerBot

## Slack Upload Files to AWS S3 via event to AWS Lambda

### Slack API App

Using  add the fileSlackerBot application and configure ...  

1. Create a new slack app `fileSlackerBot` at [Slack APi - Apps](https://api.slack.com/apps/)
    - from scratch
2. "OAuth & Permissions"
    - Bot Token Scopes
        - app_mentions:read
        - chat:write
        - remote_files:read **?**
    - Install to Workspace
3. Enable "Event Subscriptions"
    - "Subscribe to Bot Events"
        - Add "app_mention" Bot User Event
4. IDE - install python slack_bolt pip
    - a slack development framework
    - https://slack.dev/bolt-python/tutorial/getting-started
    - Use the "xoxb" bot token from the slack app "OAuth & Permissions"

### Lambda App



#### Packaging for deployment  
Use [Lambda Layers](https://docs.aws.amazon.com/lambda/latest/dg/chapter-layers.html?icmpid=docs_lambda_help) 
to deploy the python dependencies. The following can be used to create the zip archive to upload ...  
```
$ mkdir lambda_layers
$ cd lambda_layers
$ mkdir python
$ cd python
$ pip install boto3 --platform manylinux2014_x86_64 -t . --only-binary=:all:
$ pip install slack_bolt --platform manylinux2014_x86_64 -t . --only-binary=:all:
$ pip install requests --platform manylinux2014_x86_64 -t . --only-binary=:all:
$ pip install slack_sdk --platform manylinux2014_x86_64 -t . --only-binary=:all:
$ pip install openai --platform manylinux2014_x86_64 -t . --only-binary=:all:
$ cd ..
$ zip -r python_modules.zip .
```

or maybe this from the root dir of the project ...
    $ mkdir lambda_layers
    $ cd lambda_layers
    $ mkdir python
    $ pip install -r ../requirements.txt --platform manylinux2014_x86_64 --target ./python --only-binary=:all:
    $ zip -r python_modules.zip .

Upload this dependency zip to the Lambda layers. The use of layers will keep your deployment small so inline editing
in Lambda is still available. Pay attention to the versioning in layers ... it's rather straight-forward.

## Notes

Using "Ohio" for the region.
