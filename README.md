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
3. Enable "Socket Mode"
    - Created app token ("xapp..."), fileSlackerBotAppToken and keep for later use
4. Enable "Event Subscriptions"
    - "Subscribe to Bot Events"
        - Add "app_mention" Bot User Event
5. IDE - install python slack_bolt pip
    - a slack development framework
    - https://slack.dev/bolt-python/tutorial/getting-started
    - Use the "xoxb" bot token from the slack app "OAuth & Permissions"

### Lambda App

1. I think I need to use the HTTP Gateway URL in the Slack App?

#### Packaging for deployment  
Use [Lambda Layers](https://docs.aws.amazon.com/lambda/latest/dg/chapter-layers.html?icmpid=docs_lambda_help) 
to deploy the python dependencies. The following can be used to create the zip archive to upload ...  
```
$ mkdir lambda_layers
$ cd lambda_layers
$ mkdir python
$ cd python
$ pip3 install boto3 -t ./
$ pip3 install slack_bolt -t ./
$ pip3 install requests -t ./
$ cd ..
$ zip -r python_modules.zip .
```

The use of layers will keep your deployment small so inline editing in Lambda is still available.

## Notes

Using "Ohio" for the region.

---

# Historical 

## Slack Upload Files to AWS S3 via Workflow - DEAD END (moved to this section for reference only)

### Slack API App

Using [Slack APi - Apps](https://api.slack.com/apps/) add the fileSlackerBot application and configure the Redirect URL
and User Token Scopes per [AWS AppFlow Docs](https://docs.aws.amazon.com/appflow/latest/userguide/slack.html)

### S3

Configure an S3 bucket, `fileSlackerBotBucket`

Set the bucket policy to allow S3 to be a destination ...
```json
{
    "Statement": [
        {
            "Effect": "Allow",
            "Sid": "AllowAppFlowDestinationActions",
            "Principal": {
                "Service": "appflow.amazonaws.com"
            },
            "Action": [
                "s3:PutObject",
                "s3:AbortMultipartUpload",
                "s3:ListMultipartUploadParts",
                "s3:ListBucketMultipartUploads",
                "s3:GetBucketAcl",
                "s3:PutObjectAcl"
            ],
            "Resource": [
                "arn:aws:s3:::file-slacker-bot-bucket",
                "arn:aws:s3:::file-slacker-bot-bucket/*"
            ]
        }
    ]
}
```
Had to set `Block all public access` to **OFF** to allow AppFlow to use the S3 bucket as a destination.

**Flow Trigger:** Run on Demand  
**Source to destination field mapping:** Chose to 'Map all fields directly'

#### S3 URL
https://console.aws.amazon.com/s3/buckets/file-slacker-bot-bucket/fileSlackerBotToS3/

### AppFlow

[Amazon AppFlow Workshop - Slack](https://catalog.us-east-1.prod.workshops.aws/workshops/9787ec94-1ace-44cc-91e5-976ad7ddc0b1/en-US/slack) looks like another good reference.

Configure a AWS Appflow, `fileSlackerBotFlowToS3`, per [AWS AppFlow](https://us-east-2.console.aws.amazon.com/appflow/home?region=us-east-2/)
using the following details ...
- **Source Name:** Slack
- **Client ID:** 7256133112227.7287072003317
- **~~Client Secret:** f7e16e33fb7356e0a9ad9dff868bad70~~
- **Workspace:** foobar-scv8244
- **Slack Objects:** Conversations
- **Slack Channel:** all-foobar

**PROBLEM: I didn't see a way to trigger AppFlow per attached file. Running 'On Demand' or 'Scheduled' saves all Slack 
activity in on S3 record. Also, I saw no reference to the uploaded file :(  
Considering a Lambda to listen to slack file upload events and write to s3.  
The S3 bucket can emit events for another Lambda to analyse and respond to the slack user.**