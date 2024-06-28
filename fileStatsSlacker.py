import json
import boto3
from botocore.exceptions import NoCredentialsError
from botocore.exceptions import ClientError
import io
import logging
import logging
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
region = 'us-east-2'
s3 = boto3.client('s3', region)
athena = boto3.client('athena', region)


def lambda_handler(event, context):
    logger.debug(json.dumps(event))
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    logger.debug(f'bucket: {bucket}')
    logger.debug(f'key: {key}')

    if key.startswith('meta/'):
        metadata = get_s3_metadata(bucket, key)

        # Slack TS message thread
        message_ts = metadata['slack_orig_ts']

        # ID of SLACK channel
        channel_id = metadata['slack_orig_channel']

        try:
            result = client.chat_postMessage(
                channel=channel_id,
                thread_ts=message_ts,
                text=f"The file {metadata['name']} was successfully uploaded to AWS S3.",
                blocks=get_slack_msg_blocks(bucket, key, metadata)
            )

            logger.debug(result)

        except SlackApiError as e:
            logger.error(f"A Slack API Error occurred: {e}")


def get_s3_metadata(bucket, key):
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        m = response['Body'].read().decode('utf-8')
        logger.debug(m)
        return json.loads(m)
    except NoCredentialsError as e:
        logging.error(f"AWS Credentials not available\n{e}")
        raise
    except ClientError as e:
        logging.error(f"A Client Error occurred while getting the s3 file, {key}, from S3 bucket {bucket}: {e}")
        raise


def get_stats_summary():
    sql = '''SELECT
   count(*) "total #",
   count(distinct(user)) "# of users", 
   count(distinct(slack_orig_channel)) "# of slack channels",
   count(distinct(filetype)) "# of filetype",
   round(min(size)/1000,2) "min size (kB)",
   round(max(size)/1000,2) "max size (kB)",
   round(avg(size)/1000,2) "avg size (kB)",
   sum(case when nullif(user_text,'') is not null then 1 else 0 end) "# with text",
   min(from_unixtime(created)) "first create date",
   max(from_unixtime(created)) "last create date"
FROM "file_slacker_db"."metadata";'''
    try:
        query_execution = athena.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={
                'Database': 'file_slacker_db'
            },
            ResultConfiguration={
                'OutputLocation': 's3://file-slacker-athena-query-result-bucket'
            }
        )
        execution_id = query_execution['QueryExecutionId']
    except Exception as e:
        logging.error(f"An error occurred whiled executing the overall stats sql.\n{e}")
        raise

    for i in range(1, 5):
        try:
            time.sleep(i)
            query_details = athena.get_query_execution(QueryExecutionId=execution_id)
            state = query_details['QueryExecution']['Status']['State']
            if state == 'SUCCEEDED':
                query_result = athena.get_query_results(QueryExecutionId=execution_id)
                row_data = query_result['ResultSet']['Rows'][1]['Data']
                summary_lines = list()
                summary_lines.append("*Summary*  ")
                summary_lines.append(f"\nfileSlackerBot has stored {row_data[0]['VarCharValue']} files in AWS S3 from")
                summary_lines.append(f"{row_data[1]['VarCharValue']} different users across {row_data[2]['VarCharValue']}")
                summary_lines.append(f"slack channels since {row_data[8]['VarCharValue']}. There are")
                summary_lines.append(f"{row_data[3]['VarCharValue']} types of files with sizes ranging from")
                summary_lines.append(f"{row_data[4]['VarCharValue']} kB to {row_data[5]['VarCharValue']} kB with an")
                summary_lines.append(f"average size of {row_data[6]['VarCharValue']} kB.")
                return " ".join(summary_lines)
            elif state == 'FAILED':
                raise Exception(f"The stats query failed.\n{query_details['QueryExecution']['Status']['StateChangeReason']}")
            elif state == 'CANCELLED':
                raise Exception(f"The stats query was cancelled.\n{query_details['QueryExecution']['Status']['StateChangeReason']}")
        except Exception as e:
            logging.error(f"An error occurred while fetching the query results.\n{e}")
            raise

def get_stats_by_filetype():
    sql = '''SELECT filetype,
   count(*) "# per filetype",
   count(distinct(user)) "# of users", 
   count(distinct(slack_orig_channel)) "# of slack channels",
   round(avg(size)/1000,2) "avg size (kB)",
   sum(case when nullif(user_text,'') is not null then 1 else 0 end) "# with text",
   to_char(min(from_unixtime(created)), 'mm/dd/yyyy') "first create date",
   to_char(max(from_unixtime(created)), 'mm/dd/yyyy') "last create date"
FROM "file_slacker_db"."metadata"
group by filetype
order by 2 desc;'''
    query_execution = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={
            'Database': 'file_slacker_db'
        },
        ResultConfiguration={
            'OutputLocation': 's3://file-slacker-athena-query-result-bucket'
        }
    )
    execution_id = query_execution['QueryExecutionId']

    for i in range(1, 5):
        time.sleep(i)
        query_details = athena.get_query_execution(QueryExecutionId=execution_id)
        state = query_details['QueryExecution']['Status']['State']
        if state == 'SUCCEEDED':
            return athena.get_query_results(QueryExecutionId=execution_id)
        elif state == 'FAILED':
            raise Exception("The stats query failed.")
        elif state == 'CANCELLED':
            raise Exception("The stats query was cancelled.")


def get_slack_msg_blocks(bucket, key, metadata):
    blcks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"""The file `{metadata['name']}` was successfully uploaded to AWS S3. :thumbsup:  
This is the <{generate_presigned_url(bucket, metadata['s3_key'])}|S3 link> (_link is valid for 1 hour_)"""
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": get_stats_summary()
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": """
`   Col 1  ` `  Col 2   ` `  Col 3 Test`
`----------` `----------` `------------`
`   This   ` `   is a   ` `  test test `
`   This   ` `   is a   ` `  test test `
`   This   ` `   is a   ` `  test test `
`   This   ` `   is a   ` `  test test `
`   This   ` `   is a   ` `  test test `
`   This   ` `   is a   ` `  test test `

"""
            }
        }]
    return json.dumps(blcks)


def generate_presigned_url(bucket, key):
    try:
        url = s3.generate_presigned_url(ClientMethod='get_object',
                                        Params={'Bucket': bucket,
                                                'Key': key},
                                        ExpiresIn=3600
                                        )
        logger.debug("Got presigned URL: %s", url)
    except ClientError as e:
        logger.error(e)
        raise
    return url
