import json
import logging
import mimetypes
import os
from io import BytesIO
import boto3
import requests
from botocore.exceptions import ClientError
from botocore.exceptions import NoCredentialsError
from openai import OpenAI

# to retrieve the file data from the Slack private URL set the following environment variables
# SLACK_BOT_TOKEN
# SLACK_SIGNING_SECRET

# to access OpenAi set the following environment variable
# OPENAI_API_KEY

# set env var DEBUG_LOGGING_ENABLED to true or false
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

S3_FILE_BUCKET = 'file-slacker-bucket'
S3_METADATA_FOLDER = 'meta'

s3 = boto3.client('s3', 'us-east-2')
open_ai = OpenAI()
ENABLE_AI_ANALYSIS = True


def lambda_handler(event, context):
    """ The AWS Lambda Handler. This handles the events from Slack via the HTTP Gateway.
    TODO: This method is currently doing too much. Since it's not acknowledging a
    success within 3 seconds the Slack API is re-sending events. Should considering
    an asynchronous call/event to another Lambda so we can return a success immediately."""
    try:
        logger.debug(f'fileSlacker.lambda_handler -- event:\n{json.dumps(event)}')
        logger.debug(f'fileSlacker.lambda_handler -- context:\n{str(context)}')

        if checkForInvalidEvent(event):
            # do nothing, just return success
            logger.warning(f"invalid event: \n{str(event)}")
            return {
                'statusCode': 200,
            }

        slack_metadata = build_slack_metadata(event)

        # uncomment to verify the Slack Request URL from a new Slack app
        '''
        if slack_event['type'] == 'url_verification':
            return {
                'statusCode': 200,
                'body': f'{slack_event['challenge']}'
            }
        '''

        file = upload_file_to_s3(slack_metadata)
        if ENABLE_AI_ANALYSIS:
            analyzeUploadedFile(slack_metadata, file)
        upload_metadata_to_s3(slack_metadata)
    except Exception as err:
        logger.error(f"An error occurred.\n{err}")


def checkForInvalidEvent(event):
    """ If we have a valid Slack-originated event, check if we already have processed the file in s3.
     This still misses the scenario of the long processing time of the first event and sometime two
     responses will show up in the thread, especially if the ai analyzing of files is enabled. """
    slack_json = event['body']
    slack_event = json.loads(slack_json)
    if 'files' in slack_event['event']:
        # check for existence of file in s3
        results = s3.list_objects(Bucket=S3_FILE_BUCKET,
                                  Prefix=f'{S3_METADATA_FOLDER}/{slack_event['event']['files'][0]['id']}.json')
        # if Contents exist, then the file exists in s3
        return 'Contents' in results
    else:
        return False


def upload_file_to_s3(metadata):
    """ Transfers the Slack user's attached file (via the Slack private URL) to an S3 bucket."""
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
            return slack_file
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


def analyzeUploadedFile(metadata, file):
    """ First grant temporary public access to the uploaded file (via a presigned URL). Then request OpenAi to
    analyze the file. Store the result in the metadata to be persisted to S3.
    TODO: Look into improving the requests to analyze files to OpenAI """
    ai_analysis = "The file could not be analysed."
    filename = metadata['name']
    try:
        presigned_url = generate_presigned_url(S3_FILE_BUCKET, metadata['s3_key'])
        if metadata['mimetype'].startswith('image'):
            ai_analysis = analyze_image("What’s in this image?", presigned_url)
        else:
            if not (filename.endswith(metadata['file_extension'])):
                filename = metadata['name'] + metadata['file_extension']
            # if (filename.endswith('.csv')):
            #    filename = metadata['name'] + '.txt'
            # TODO: We know the file extensions that will be processed from the OpenAI docs, so we could add .txt
            # to any mimetype starting with text and not in this list of extensions.
            ai_analysis = analyze_file("Analyze and describe the meaning behind this file.", file, filename)
    except Exception as e:
        logger.error(f"Error while analysing file `{filename}` (slack name `{metadata['name']}`)", e)
    metadata.update({'ai_analysis': ai_analysis})


def analyze_image(request, url):
    """ A simple approach to analyzing image content using OpenAI."""
    response = open_ai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{request}"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"{url}",
                        },
                    },
                ],
            }
        ],
        max_tokens=300,
    )
    logger.debug(f"Image analysis: {str(response.choices[0].message.content)}")
    return str(response.choices[0].message.content)


def analyze_file(request, raw_file, filename):
    """  Analyzing the content of text-like files using OpenAI."""
    assistant = open_ai.beta.assistants.create(
        name="Assistant to fileSlackerBot",
        instructions="""You are an expert at analyzing the text within files. Use your knowledge base to summarize the 
        meaning of the text within the given file.""",
        model="gpt-4o",
        tools=[{"type": "file_search"}]
    )

    # Upload the user provided file to OpenAI
    message_file = open_ai.files.create(
        file=(filename, raw_file), purpose="assistants",
    )

    # Create a thread and attach the file to the message
    thread = open_ai.beta.threads.create(
        messages=[
            {
                "role": "user",
                "content": request,
                # Attach the new file to the message.
                "attachments": [
                    {"file_id": message_file.id, "tools": [{"type": "file_search"}]}
                ],
            }
        ]
    )

    # The thread now has a vector store with that file in its tool resources.
    logger.debug(thread.tool_resources.file_search)

    # Use the create and poll SDK helper to create a run and poll the status of
    # the run until it's in a terminal state.

    run = open_ai.beta.threads.runs.create_and_poll(
        thread_id=thread.id, assistant_id=assistant.id
    )

    messages = list(open_ai.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))

    message_content = messages[0].content[0].text
    annotations = message_content.annotations
    citations = []
    for index, annotation in enumerate(annotations):
        message_content.value = message_content.value.replace(annotation.text, f"[{index}]")
        if file_citation := getattr(annotation, "file_citation", None):
            cited_file = open_ai.files.retrieve(file_citation.file_id)
            citations.append(f"[{index}] {cited_file.filename}")

    response = message_content.value
    response += "\n".join(citations)
    return response


def upload_metadata_to_s3(metadata):
    """ Uploads metadata json to a folder, meta, in the S3 bucket. This metadata has the file key and
    can be queried via Athena. """
    logger.debug(f"fileSlacker.upload_metadata_to_s3 -- metadata: {json.dumps(metadata)}")
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
        logging.error(f"A Client Error occurred with saving the `{metadata['filename']}` metadata to S3\n{e}")
        raise
    except Exception as e:
        logging.error(f"An Error occurred with saving the `{metadata['filename']}` metadata to S3\n{e}")
        raise


def build_slack_metadata(event):
    """ Builds the metadata json to be stored in the meta folder of the s3 bucket. """
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
        'slack_orig_ts': f'{slack_event['event']['ts']}',
        'ai_analysis': '_TODO_'
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
        logger.warning("No additional text was found from the user. Nothing may have been entered.", e)
    logger.debug(f'METADATA JSON:\nf{json.dumps(md, indent=4)}')
    return md


def generate_presigned_url(bucket, key):
    """ Create a temporary public-accessible URL for easy access by OpenAi. The ExpiresIn attribute is
    in seconds. """
    try:
        url = s3.generate_presigned_url(ClientMethod='get_object',
                                        Params={'Bucket': bucket,
                                                'Key': key},
                                        ExpiresIn=300
                                        )
        logger.debug("Got presigned URL: %s", url)
    except ClientError as e:
        logger.error(e)
        raise
    return url
