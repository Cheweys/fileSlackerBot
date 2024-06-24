import json
import logging
import requests
from botocore.client import Config
import boto3
from botocore.exceptions import NoCredentialsError
import mimetypes

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_FILE_BUCKET = 'file-slacker-bucket'


# S3_METADATA_FOLDER

def lambda_handler(event, context):
    try:
        # logger.debug(f'## EVENT\n{json.dumps(event)}')
        # logger.debug(f'## CONTEXT\n{json.dumps(context)}')
        slack_json = event['body']
        logger.info(f"SLACK JSON:\n{slack_json}")
        slack_event = json.loads(slack_json)
        slack_file_url = slack_event['event']['files'][0]['url_private']
        slack_file_name = slack_event['event']['files'][0]['name']
        logger.info(f"SLACK FILE URL: {slack_file_url}")
        upload_file(slack_file_url, S3_FILE_BUCKET, slack_file_name)
        # TODO: push metadata to DB
        return {
            'statusCode': 200
        }
    except Exception as err:
        logger.error(err)
        return {
            'statusCode': 500
        }


def upload_file(remote_url, bucket, file_name):
    cfg = Config(connect_timeout=2, retries={'max_attempts': 0})
    s3 = boto3.client('s3', config=cfg)
    try:
        response = requests.get(remote_url, stream=True).raw
        content_type = response.headers['content-type']
        # extension = mimetypes.guess_extension(content_type)
        s3.upload_fileobj(response, bucket, file_name)
        print("Upload Successful")
    except FileNotFoundError:
        print("The file was not found")
        raise
    except NoCredentialsError:
        print("Credentials not available")
        raise
