# fileSlackerBot

![fileSlackerBot](docs/xtra/fileSlackerBot_icon.jpg)

## Overview
A project allowing for the Slack Upload of Files to AWS S3 via events to AWS Lambdas.

![Context Diagram](docs/fileSlackerBot_context.drawio.png)

## Slack API App

TODO: Container Diagram

Using  add the `fileSlackerBot` application and configure ...  

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

TODO: review the above

## Lambda Apps

### fileSlacker

TODO: Container Diagram

### fileStatsSlacker

TODO: Container Diagram

## S3

## Packaging for Deployment  
Use [Lambda Layers](https://docs.aws.amazon.com/lambda/latest/dg/chapter-layers.html?icmpid=docs_lambda_help) 
to deploy the python dependencies. The following can be used to create the zip archive to upload ...  
```
$ mkdir lambda_layers
$ cd lambda_layers
$ mkdir python
$ pip install -r ../requirements.txt --platform manylinux2014_x86_64 --target ./python --only-binary=:all:
$ zip -r python_modules.zip .
```  
Upload this dependency zip to the Lambda layers. The use of layers will keep your deployment small so that inline
editing in Lambda is still available. Pay attention to the versioning in layers ... it's rather straight-forward.

## Notes

Using "Ohio" for the region.
