import json
import logging
import requests
import os
from botocore.client import Config
import boto3
from io import BytesIO
from botocore.exceptions import NoCredentialsError
from botocore.exceptions import ClientError
import mimetypes

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_FILE_BUCKET = 'file-slacker-bucket'


# S3_METADATA_FOLDER

def lambda_handler(event, context):
    try:
        logger.debug(f'## EVENT\n{json.dumps(event)}')
        logger.debug(f'## CONTEXT\n{str(context)}')
        slack_json = event['body']
        logger.info(f"SLACK JSON:\n{slack_json}")
        slack_event = json.loads(slack_json)

        # uncomment to verify the Slack Request URL (i.e. for new slack app)
        '''
        if slack_event['type'] == 'url_verification':
            return {
                'statusCode': 200,
                'body': f'{slack_event['challenge']}'
            }
        '''

        slack_file_url = slack_event['event']['files'][0]['url_private']
        slack_file_name = slack_event['event']['files'][0]['name']
        slack_file_mimetype = slack_event['event']['files'][0]['mimetype']
        logger.info(f"SLACK FILE URL: {slack_file_url}")
        logger.debug(f"SLACK FILE NAME: {slack_file_name}")
        upload_file(slack_file_url, S3_FILE_BUCKET, slack_file_name, slack_file_mimetype)

        # TODO: push metadata to DB
        return {
            'statusCode': 200,
        }
    except Exception as err:
        logger.error(f"An error occurred.\n{err}")
        return {
            'statusCode': 500
        }


def upload_file(remote_url, bucket, file_name, content_type):
    s3 = boto3.client('s3', 'us-east-2')
    try:
        slack_token = os.environ["SLACK_BOT_TOKEN"]
        slack_file_response = requests.get(
            remote_url,
            headers={'Content-Type':'text', 'Authorization': f'Bearer {slack_token}'},
            stream=True)
        if slack_file_response.status_code == 200:
            slack_file = slack_file_response.content
            binary_stream = BytesIO(slack_file)
            s3.upload_fileobj(
                binary_stream,
                bucket,
                file_name,
                ExtraArgs={'ContentType': content_type})
        else:
            raise Exception(f"Unsuccessful HTTP status while fetching Slack file: {slack_file_response.status_code}")
    except FileNotFoundError as e:
        logging.error(f"The file was not found\n{e}")
        raise
    except NoCredentialsError as e:
        logging.error(f"Credentials not available\n{e}")
        raise
    except ClientError as e:
        logging.error(f"A Client Error occurred\n{e}")
