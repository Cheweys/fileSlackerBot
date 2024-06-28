import json
import logging
import requests
import mimetypes
import os
import boto3
from io import BytesIO
from botocore.exceptions import NoCredentialsError
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

S3_FILE_BUCKET = 'file-slacker-bucket'
S3_METADATA_FOLDER = 'meta'

s3 = boto3.client('s3', 'us-east-2')


def lambda_handler(event, context):
    try:
        logger.debug(f'## EVENT\n{json.dumps(event)}')
        logger.debug(f'## CONTEXT\n{str(context)}')
        slack_metadata = build_slack_metadata(event)

        # uncomment to verify the Slack Request URL from a new Slack app
        '''
        if slack_event['type'] == 'url_verification':
            return {
                'statusCode': 200,
                'body': f'{slack_event['challenge']}'
            }
        '''

        upload_file_to_s3(slack_metadata)

        upload_metadata_to_s3(slack_metadata)

        return {
            'statusCode': 200,
        }
    except Exception as err:
        logger.error(f"An error occurred.\n{err}")
        return {
            'statusCode': 500
        }


def upload_file_to_s3(metadata):
    try:
        slack_token = os.environ["SLACK_BOT_TOKEN"]
        slack_file_response = requests.get(
            metadata['url_private'],
            headers={'Content-Type': 'text', 'Authorization': f'Bearer {slack_token}'},
            stream=True)
        if slack_file_response.status_code == 200:
            slack_file = slack_file_response.content
            binary_stream = BytesIO(slack_file)
            s3.upload_fileobj(
                binary_stream,
                S3_FILE_BUCKET,
                metadata['s3_key'],
                ExtraArgs={'ContentType': f'{metadata['mimetype']}'})
        else:
            raise Exception(f"Unsuccessful HTTP status while fetching Slack file: {slack_file_response.status_code}")
    except FileNotFoundError as e:
        logging.error(f"The slack file was not found at {metadata['url_private']}\n{e}")
        raise
    except NoCredentialsError as e:
        logging.error(f"Credentials not available\n{e}")
        raise
    except ClientError as e:
        logging.error(f"A Client Error occurred while saving the file, {metadata['name']}, to S3\n{e}")
        raise


def upload_metadata_to_s3(metadata):
    try:
        metadata_json = json.dumps(metadata)
        response = s3.put_object(
            Body=metadata_json,
            Bucket=S3_FILE_BUCKET,
            Key=f'{S3_METADATA_FOLDER}/{metadata['id']}.json',
            ContentType='application/json'
        )
    except NoCredentialsError as e:
        logging.error(f"Credentials not available\n{e}")
        raise
    except ClientError as e:
        logging.error(f"A Client Error occurred with saving the metadata to S3\n{e}")
        raise


def build_slack_metadata(event):
    slack_json = event['body']
    logger.debug(f"SLACK JSON:\n{slack_json}")
    slack_event = json.loads(slack_json)
    slack_event_file = slack_event['event']['files'][0]
    file_extension = mimetypes.guess_extension(slack_event_file['mimetype'])
    md = {
        'id': f'{slack_event_file['id']}',
        'created': f'{slack_event_file['created']}',
        'timestamp': f'{slack_event_file['timestamp']}',
        'name': f'{slack_event_file['name']}',
        'mimetype': f'{slack_event_file['mimetype']}',
        'filetype': f'{slack_event_file['filetype']}',
        'file_extension': f'{file_extension}',
        'user': f'{slack_event_file['user']}',
        'user_team': f'{slack_event_file['user_team']}',
        'size': f'{slack_event_file['size']}',
        'url_private': f'{slack_event_file['url_private']}',
        'user_text': '',
        's3_key': f'{slack_event_file['id']}{file_extension}',
        'slack_orig_channel': f'{slack_event['event']['channel']}',
        'slack_orig_ts': f'{slack_event['event']['ts']}'
    }
    try:
        blocks = slack_event['event']['blocks']
        for b in blocks:
            if b['type'] == 'rich_text':
                for e1 in b['elements']:
                    if e1['type'] == 'rich_text_section':
                        for e2 in e1['elements']:
                            if e2['type'] == 'text':
                                md.update({'user_text': f'{e2['text']}'})
                                break
                        break
                break
    except KeyError:
        logger.debug('No "user_text" was found.')
    logger.info(f'METADATA JSON:\nf{json.dumps(md, indent=4)}')
    return md