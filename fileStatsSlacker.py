import json
import boto3
from botocore.exceptions import NoCredentialsError
from botocore.exceptions import ClientError
import logging
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import time

# set env var DEBUG_LOGGING_ENABLED to true or false
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Set the following environment variables for the slack WebClient
# SLACK_BOT_TOKEN
# SLACK_SIGNING_SECRET
slack = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
region = 'us-east-2'
# set AWS policies to allow this Lambda to access S3 and Athena
s3 = boto3.client('s3', region)
athena = boto3.client('athena', region)


def lambda_handler(event, context):
    """ This Lambda handler is triggered by changes in the fileSlackerBot S3 bucket. It is configured to only send
    trigger events on JSON object in S3. We are only interested in the updates to the JSON objects in the `meta/`
    directory. (Configuring a prefix of `meta/` on S3 trigger didn't seem to work, so we do a check in this method.)
    We don't want to trigger off the file upload events or try to handle the upload of multiple files at once
    as this would trigger multiple messages back to the Slack user."""
    try:
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = event['Records'][0]['s3']['object']['key']
        logger.debug(f'bucket: {bucket}')
        logger.debug(f'key: {key}')

        # trigger by s3 updates in the meta/ folder only
        if key.startswith('meta/'):
            logger.debug(f"fileStatsSlacker.lambda_handler -- event: {json.dumps(event)}")
            post_message_to_slack_user(bucket, key)
    except Exception as e:
        logger.error(f"An exception occurred in the fileStatsSlacker.lambda_handler: {e}")


def post_message_to_slack_user(bucket, key):
    """ Posts a message to the slack user that uploaded a file via fileSlackerBot to AWS S3.
    The originating Slack channel and thread IDs are stored in the metadata S3 folder.
    Most of the analysis/reporting is done in the building of the Slack message blocks. """
    logger.debug(f"fileStatsSlacker.post_message_to_slack_user -- bucket: {bucket}, key: {key}")
    metadata = get_s3_metadata(bucket, key)
    # ID of SLACK channel
    channel_id = metadata['slack_orig_channel']
    # Slack TS message thread
    message_ts = metadata['slack_orig_ts']

    try:
        result = slack.chat_postMessage(
            channel=channel_id,
            thread_ts=message_ts,
            text=f"The file {metadata['name']} was successfully uploaded to AWS S3.",
            blocks=get_slack_msg_blocks(bucket, key, metadata)
        )
        logger.debug(result)
    except SlackApiError as e:
        logger.error(f"A Slack API Error occurred: {e}")


def get_s3_metadata(bucket, key):
    """ Fetches the JSON metadata for the uploaded file and converts it to a python data structure. """
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


def get_slack_msg_blocks(bucket, key, metadata):
    """ Generates a simple report of the fileSlackerBot files in S3. The formatting isn't the best. Slack doesn't
    support all the markdown syntax. Tried to allow the reporting text to wrap and kept the simple tables narrow to be
    more easily read on mobile devices. """

    # Execute AWS Athena queries to get resulting data structures that can be reported upon.
    stats_summary_row_data = get_stats_summary()
    stats_by_filetype = get_stats_by_filetype()
    # Build a data structure for Slack message blocks
    blocks = [
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
                "text": f"""*Description*  
{metadata['ai_analysis']}"""
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": report_summary_stats(stats_summary_row_data)
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": report_count_avg_size_by_filetype(stats_by_filetype)
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": report_user_channel_count_by_filetype(stats_by_filetype)
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": report_earliest_latest_dates_by_filetype(stats_by_filetype)
            }
        }]
    return json.dumps(blocks)


def generate_presigned_url(bucket, key):
    """ Create a temporary public-accessible URL for easy verification by the Slack user. The ExpiresIn attribute is
    in seconds. """
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


def get_stats_summary():
    """ Executes an Athena query of general stats of all the files uploaded to the fileSlackerBot S3 bucket.
    Returns a singe row data structure. """
    sql = '''SELECT
   count(*) "total #",
   count(distinct(user)) "# of users", 
   count(distinct(slack_orig_channel)) "# of slack channels",
   count(distinct(filetype)) "# of filetype",
   round(min(size)/1000,2) "min size (kB)",
   round(max(size)/1000,2) "max size (kB)",
   round(avg(size)/1000,2) "avg size (kB)",
   sum(case when nullif(user_text,'') is not null then 1 else 0 end) "# with text",
   to_char(min(from_unixtime(created)), 'mm/dd/yyyy') "first create date",
   to_char(max(from_unixtime(created)), 'mm/dd/yyyy') "last create date"
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
        logging.error(f"An error occurred whiled executing the summary stats sql.\n{e}")
        raise

    for i in range(1, 5):
        try:
            time.sleep(i)
            query_details = athena.get_query_execution(QueryExecutionId=execution_id)
            state = query_details['QueryExecution']['Status']['State']
            if state == 'SUCCEEDED':
                query_results = athena.get_query_results(QueryExecutionId=execution_id)
                return query_results['ResultSet']['Rows']
            elif state == 'FAILED':
                raise Exception(
                    f"The summary stats query failed.\n{query_details['QueryExecution']['Status']['StateChangeReason']}")
            elif state == 'CANCELLED':
                raise Exception(
                    f"The summary stats query was cancelled.\n{query_details['QueryExecution']['Status']['StateChangeReason']}")
        except Exception as e:
            logging.error(f"An error occurred while fetching the query results for summary stats.\n{e}")
            raise


def report_summary_stats(row_data):
    """ Generates some simple markdown text describing the status of all the files in the fileSlackerBot S3 bucket.
    Uses the data structure from `get_stats_summary` """
    data = row_data[1]['Data']
    report_lines = list()
    report_lines.append("*Summary of All Files*  ")
    report_lines.append(f"\n{data[0]['VarCharValue']} files have been stored in AWS S3 from")
    report_lines.append(f"{data[1]['VarCharValue']} different users across {data[2]['VarCharValue']}")
    report_lines.append(f"slack channels since {data[8]['VarCharValue']}. There are")
    report_lines.append(f"{data[3]['VarCharValue']} types of files with sizes ranging from")
    report_lines.append(f"{data[4]['VarCharValue']} kB to {data[5]['VarCharValue']} kB with an")
    report_lines.append(f"average size of {data[6]['VarCharValue']} kB.")
    return " ".join(report_lines)


def get_stats_by_filetype():
    """ Executes an Athena query of stats per filetype of the files uploaded to the fileSlackerBot S3 bucket.
    Returns a multiple row data structure. """
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
        logging.error(f"An error occurred whiled executing the stats by filetype sql.\n{e}")
        raise

    for i in range(1, 5):
        try:
            time.sleep(i)
            query_details = athena.get_query_execution(QueryExecutionId=execution_id)
            state = query_details['QueryExecution']['Status']['State']
            if state == 'SUCCEEDED':
                query_results = athena.get_query_results(QueryExecutionId=execution_id)
                return query_results['ResultSet']['Rows']
            elif state == 'FAILED':
                raise Exception(
                    f"The stats by filetype query failed.\n{query_details['QueryExecution']['Status']['StateChangeReason']}")
            elif state == 'CANCELLED':
                raise Exception(
                    f"The stats by filetype query was cancelled.\n{query_details['QueryExecution']['Status']['StateChangeReason']}")
        except Exception as e:
            logging.error(f"An error occurred while fetching the query results for stats by filetype.\n{e}")
            raise


def report_count_avg_size_by_filetype(row_data):
    """ Generates a very simple table-like markdown report. This was made intentionally narrow to display better on
    mobile devices.
    Uses the data structure from `get_stats_by_filetype` """
    report_lines = list()
    report_lines.append("*Counts and Average Size in kB by Filetype*  \n")
    report_lines.append("`Filetype  ` `Count     ` `Avg (kB)  `  \n")
    for i in range(1, len(row_data)):
        data = row_data[i]['Data']
        report_lines.append(
            f"`{data[0]['VarCharValue'].ljust(10)}` `{data[1]['VarCharValue'].ljust(10)}` `{data[4]['VarCharValue'].ljust(10)}`  \n")
    return " ".join(report_lines)


def report_user_channel_count_by_filetype(row_data):
    """ Generates a very simple table-like markdown report. This was made intentionally narrow to display better on
    mobile devices.
    Uses the data structure from `get_stats_by_filetype` """
    report_lines = list()
    report_lines.append("*Count of Users having uploaded files and the number channels used by Filetype*  \n")
    report_lines.append("`Filetype  ` `# Users   ` `# Channels`  \n")
    for i in range(1, len(row_data)):
        data = row_data[i]['Data']
        report_lines.append(
            f"`{data[0]['VarCharValue'].ljust(10)}` `{data[2]['VarCharValue'].ljust(10)}` `{data[3]['VarCharValue'].ljust(10)}`  \n")
    return " ".join(report_lines)


def report_earliest_latest_dates_by_filetype(row_data):
    """ Generates a very simple table-like markdown report. This was made intentionally narrow to display better on
    mobile devices.
    Uses the data structure from `get_stats_by_filetype` """
    report_lines = list()
    report_lines.append("*First and Last Upload Dates by Filetype*  \n")
    report_lines.append("`Filetype  ` `First     ` `Last      `  \n")
    for i in range(1, len(row_data)):
        data = row_data[i]['Data']
        report_lines.append(
            f"`{data[0]['VarCharValue'].ljust(10)}` `{data[6]['VarCharValue'].ljust(10)}` `{data[7]['VarCharValue'].ljust(10)}`  \n")
    return " ".join(report_lines)
