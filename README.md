# fileSlackerBot


## Slack Upload Files to AWS S3 via Workflow

### Slack

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

Configure a AWS Appflow, `fileSlackerBotFlowToS3`, per [AWS AppFlow](https://us-east-2.console.aws.amazon.com/appflow/home?region=us-east-2/)
using the following details ...
- **Source Name:** Slack  
- **Client ID:** 7256133112227.7287072003317  
- **~~Client Secret:** f7e16e33fb7356e0a9ad9dff868bad70~~  
- **Workspace:** foobar-scv8244  
- **Slack Objects:** Conversations
- **Slack Channel:** all-foobar

**PROBLEM: I didn't see a way to trigger AppFlow per attached file.  
Considering a Lambda to listen to slack file upload events and write to s3.  
The S3 bucket can emit events for another Lambda to analyse and respond to the slack user.**

## Notes

[Amazon AppFlow Workshop - Slack](https://catalog.us-east-1.prod.workshops.aws/workshops/9787ec94-1ace-44cc-91e5-976ad7ddc0b1/en-US/slack) looks like another good reference.

Using "Ohio" for the region.