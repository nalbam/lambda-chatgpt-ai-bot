import boto3
import datetime
import json
import os
import re
import sys
import time
import base64
import requests

from slack_bolt import App, Say
from slack_bolt.adapter.aws_lambda import SlackRequestHandler

from openai import OpenAI

BOT_CURSOR = os.environ.get("BOT_CURSOR", ":robot_face:").strip()

# Set up Slack API credentials
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"].strip()
SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"].strip()

# Keep track of conversation history by thread and user
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "chatgpt-ai-bot-dev").strip()

# Set up ChatGPT API credentials
OPENAI_ORG_ID = os.environ["OPENAI_ORG_ID"].strip()
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"].strip()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1").strip()

IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "dall-e-3").strip()
IMAGE_SIZE = os.environ.get("IMAGE_SIZE", "1024x1024").strip()

# Set up System messages
SYSTEM_MESSAGE = os.environ.get("SYSTEM_MESSAGE", "None").strip()

MAX_LEN_SLACK = int(os.environ.get("MAX_LEN_SLACK", 3000))
MAX_LEN_OPENAI = int(os.environ.get("MAX_LEN_OPENAI", 4000))

KEYWARD_IMAGE = os.environ.get("KEYWARD_IMAGE", "그려줘").strip()
KEYWARD_EMOJI = os.environ.get("KEYWARD_EMOJI", "이모지").strip()

MSG_PREVIOUS = "이전 대화 내용 확인 중... " + BOT_CURSOR
MSG_IMAGE_DESCRIBE = "이미지 감상 중... " + BOT_CURSOR
MSG_IMAGE_GENERATE = "이미지 생성 준비 중... " + BOT_CURSOR
MSG_IMAGE_DRAW = "이미지 그리는 중... " + BOT_CURSOR
MSG_RESPONSE = "응답 기다리는 중... " + BOT_CURSOR

COMMAND_DESCRIBE = "Describe the image in great detail as if viewing a photo."
COMMAND_GENERATE = "Convert the above sentence into a command for DALL-E to generate an image within 1000 characters. Just give me a prompt."

CONVERSION_ARRAY = [
    ["**", "*"],
    # ["#### ", "🔸 "],
    # ["### ", "🔶 "],
    # ["## ", "🟠 "],
    # ["# ", "🟡 "],
]


# Initialize Slack app
app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET,
    process_before_response=True,
)

handler = SlackRequestHandler(app=app)

bot_id = app.client.api_call("auth.test")["user_id"]

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

# Initialize OpenAI
openai = OpenAI(
    organization=OPENAI_ORG_ID if OPENAI_ORG_ID != "None" else None,
    api_key=OPENAI_API_KEY,
)


# Get the context from DynamoDB
def get_context(thread_ts, user, default=""):
    if thread_ts is None:
        item = table.get_item(Key={"id": user}).get("Item")
    else:
        item = table.get_item(Key={"id": thread_ts}).get("Item")
    return (item["conversation"]) if item else (default)


# Put the context in DynamoDB
def put_context(thread_ts, user, conversation=""):
    expire_at = int(time.time()) + 3600  # 1h
    expire_dt = datetime.datetime.fromtimestamp(expire_at).isoformat()
    if thread_ts is None:
        table.put_item(
            Item={
                "id": user,
                "conversation": conversation,
                "expire_dt": expire_dt,
                "expire_at": expire_at,
            }
        )
    else:
        table.put_item(
            Item={
                "id": thread_ts,
                "conversation": conversation,
                "expire_dt": expire_dt,
                "expire_at": expire_at,
            }
        )


# Replace text
def replace_text(text):
    for old, new in CONVERSION_ARRAY:
        text = text.replace(old, new)
    return text


# Update the message in Slack
def chat_update(say, channel, thread_ts, latest_ts, message="", continue_thread=False):
    # print("chat_update: {}".format(message))

    if sys.getsizeof(message) > MAX_LEN_SLACK:
        split_key = "\n\n"
        if "```" in message:
            split_key = "```"

        parts = message.split(split_key)

        last_one = parts.pop()

        if len(parts) % 2 == 0:
            text = split_key.join(parts) + split_key
            message = last_one
        else:
            text = split_key.join(parts)
            message = split_key + last_one

        text = replace_text(text)

        # Update the message
        app.client.chat_update(channel=channel, ts=latest_ts, text=text)

        if continue_thread:
            text = replace_text(message) + " " + BOT_CURSOR
        else:
            text = replace_text(message)

        # New message
        result = say(text=text, thread_ts=thread_ts)
        latest_ts = result["ts"]
    else:
        if continue_thread:
            text = replace_text(message) + " " + BOT_CURSOR
        else:
            text = replace_text(message)

        # Update the message
        app.client.chat_update(channel=channel, ts=latest_ts, text=text)

    return message, latest_ts


# Reply to the message
def reply_text(messages, say, channel, thread_ts, latest_ts, user):
    stream = openai.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        stream=True,
        user=user,
    )

    counter = 0
    message = ""
    for part in stream:
        reply = part.choices[0].delta.content or ""

        if reply:
            message += reply

        if counter % 16 == 1:
            message, latest_ts = chat_update(
                say, channel, thread_ts, latest_ts, message, True
            )

        counter = counter + 1

    chat_update(say, channel, thread_ts, latest_ts, message)

    return message


# Reply to the image
def reply_image(prompt, say, channel, thread_ts, latest_ts):
    response = openai.images.generate(
        model=IMAGE_MODEL,
        prompt=prompt,
        size=IMAGE_SIZE,
        n=1,
    )

    print("reply_image: {}".format(response))

    revised_prompt = response.data[0].revised_prompt
    image_url = response.data[0].url

    file_ext = image_url.split(".")[-1].split("?")[0]
    filename = "{}.{}".format(IMAGE_MODEL, file_ext)

    file = get_image_from_url(image_url)

    response = app.client.files_upload_v2(
        channel=channel, filename=filename, file=file, thread_ts=thread_ts
    )

    print("reply_image: {}".format(response))

    chat_update(say, channel, thread_ts, latest_ts, revised_prompt)

    return image_url


# Get reactions
def get_reactions(reactions):
    try:
        reaction_map = {}
        reaction_users_cache = {}
        for reaction in reactions:
            reaction_name = ":" + reaction.get("name").split(":")[0] + ":"
            if reaction_name not in reaction_map:
                reaction_map[reaction_name] = []
            reaction_users = reaction.get("users", [])
            for reaction_user in reaction_users:
                if reaction_user not in reaction_users_cache:
                    reaction_user_info = app.client.users_info(user=reaction_user)
                    reaction_users_cache[reaction_user] = (
                        reaction_user_info.get("user")
                        .get("profile")
                        .get("display_name")
                    )
                reaction_map[reaction_name].append(reaction_users_cache[reaction_user])
        reaction_text = ""
        for reaction_name, reaction_users in reaction_map.items():
            reaction_text += "[{} '{}' reaction users: {}] ".format(
                KEYWARD_EMOJI, reaction_name, ",".join(reaction_users)
            )
        return reaction_text
    except Exception as e:
        print("get_reactions: {}".format(e))
        return ""


# Get thread messages using conversations.replies API method
def conversations_replies(channel, ts, client_msg_id, messages=[], type=""):
    try:
        response = app.client.conversations_replies(channel=channel, ts=ts)

        print("conversations_replies: {}".format(response))

        if not response.get("ok"):
            print(
                "conversations_replies: {}".format(
                    "Failed to retrieve thread messages."
                )
            )

        res_messages = response.get("messages", [])
        first_ts = str(res_messages[0].get("ts"))

        res_messages.reverse()
        res_messages.pop(0)  # remove the first message

        for message in res_messages:
            if message.get("client_msg_id", "") == client_msg_id:
                continue

            role = "user"
            if message.get("bot_id", "") != "":
                role = "assistant"

            # prompt 에 이모지 키워드가 있고, 첫번째 메시지에 리액션이 있으면 리액션을 추가
            if type == "emoji" and first_ts == str(message.get("ts")):
                reactions = get_reactions(message.get("reactions", []))
                if reactions != "":
                    messages.append(
                        {
                            "role": role,
                            "content": "reactions {}".format(reactions),
                        }
                    )

            # 메세지에 유저 이름을 추가
            user_info = app.client.users_info(user=message.get("user"))
            user_name = user_info.get("user").get("profile").get("display_name")
            content = "{}: {}".format(user_name, message.get("text", ""))

            messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

            # print("conversations_replies: messages size: {}".format(sys.getsizeof(messages)))

            if sys.getsizeof(messages) > MAX_LEN_OPENAI:
                messages.pop(0)  # remove the oldest message
                break

    except Exception as e:
        print("conversations_replies: {}".format(e))

    if SYSTEM_MESSAGE != "None":
        messages.append(
            {
                "role": "system",
                "content": SYSTEM_MESSAGE,
            }
        )

    print("conversations_replies: {}".format(messages))

    return messages


# Handle the chatgpt conversation
def conversation(say: Say, thread_ts, content, channel, user, client_msg_id, type=None):
    print("conversation: {}".format(json.dumps(content)))

    # Keep track of the latest message timestamp
    result = say(text=BOT_CURSOR, thread_ts=thread_ts)
    latest_ts = result["ts"]

    messages = []
    messages.append(
        {
            "role": "user",
            "content": content,
        },
    )

    # Get the thread messages
    if thread_ts != None:
        chat_update(say, channel, thread_ts, latest_ts, MSG_PREVIOUS)

        messages = conversations_replies(
            channel, thread_ts, client_msg_id, messages, type
        )

        messages = messages[::-1]  # reversed

    # Send the prompt to ChatGPT
    try:
        print("conversation: {}".format(messages))

        # Send the prompt to ChatGPT
        message = reply_text(messages, say, channel, thread_ts, latest_ts, user)

        # print("conversation: {}".format(message))

    except Exception as e:
        print("conversation: Error handling message: {}".format(e))
        print("conversation: OpenAI Model: {}".format(OPENAI_MODEL))

        message = f"```{e}```"

        chat_update(say, channel, thread_ts, latest_ts, message)


# Handle the image generation
def image_generate(say: Say, thread_ts, content, channel, client_msg_id, type=None):
    print("image_generate: {}".format(content))

    # Keep track of the latest message timestamp
    result = say(text=BOT_CURSOR, thread_ts=thread_ts)
    latest_ts = result["ts"]

    prompt = content[0]["text"]

    prompts = []

    # Get the thread messages
    if thread_ts != None:
        chat_update(say, channel, thread_ts, latest_ts, MSG_PREVIOUS)

        replies = conversations_replies(channel, thread_ts, client_msg_id, [], type)

        replies = replies[::-1]  # reversed

        prompts = [
            f"{reply['role']}: {reply['content']}"
            for reply in replies
            if reply["content"].strip()
        ]

    # Get the image content
    if len(content) > 1:
        chat_update(say, channel, thread_ts, latest_ts, MSG_IMAGE_DESCRIBE)

        content[0]["text"] = COMMAND_DESCRIBE

        messages = []
        messages.append(
            {
                "role": "user",
                "content": content,
            },
        )

        try:
            print("image_generate: {}".format(messages))

            response = openai.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
            )

            # print("image_generate: {}".format(response))

            prompts.append(response.choices[0].message.content)

        except Exception as e:
            print("image_generate: OpenAI Model: {}".format(OPENAI_MODEL))
            print("image_generate: Error handling message: {}".format(e))

    # Send the prompt to ChatGPT
    prompts.append(prompt)

    # Prepare the prompt for image generation
    try:
        chat_update(say, channel, thread_ts, latest_ts, MSG_IMAGE_GENERATE)

        prompts.append(COMMAND_GENERATE)

        messages = []
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "\n\n\n".join(prompts),
                    }
                ],
            },
        )

        print("image_generate: {}".format(messages))

        response = openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
        )

        # print("image_generate: {}".format(response))

        prompt = response.choices[0].message.content

        chat_update(say, channel, thread_ts, latest_ts, prompt + " " + BOT_CURSOR)

    except Exception as e:
        print("image_generate: OpenAI Model: {}".format(OPENAI_MODEL))
        print("image_generate: Error handling message: {}".format(e))

    # Generate the image
    try:
        print("image_generate: {}".format(prompt))

        # Send the prompt to ChatGPT
        message = reply_image(prompt, say, channel, thread_ts, latest_ts)

        print("image_generate: {}".format(message))

        # app.client.chat_delete(channel=channel, ts=latest_ts)

    except Exception as e:
        print("image_generate: OpenAI Model: {}".format(IMAGE_MODEL))
        print("image_generate: Error handling message: {}".format(e))

        message = f"```{e}```"

        chat_update(say, channel, thread_ts, latest_ts, message)


# Get image from URL
def get_image_from_url(image_url, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(image_url, headers=headers)

    if response.status_code == 200:
        return response.content
    else:
        print("Failed to fetch image: {}".format(image_url))

    return None


# Get image from Slack
def get_image_from_slack(image_url):
    return get_image_from_url(image_url, SLACK_BOT_TOKEN)


# Get encoded image from Slack
def get_encoded_image_from_slack(image_url):
    image = get_image_from_slack(image_url)

    if image:
        return base64.b64encode(image).decode("utf-8")

    return None


# Replace the emoji pattern
def replace_emoji_pattern(text):
    # 패턴: :로 시작하고, 문자 그룹이 있고, :가 오고, 문자 그룹이 있고, :로 끝나는 패턴
    pattern = r":([^:]+):([^:]+):"

    # 첫 번째 그룹만 유지하고 두 번째 그룹은 제거
    replacement = r":\1:"

    # 치환 실행
    result = re.sub(pattern, replacement, text)
    return result


# Extract content from the message
def content_from_message(prompt, event, user=None):
    type = "text"

    if KEYWARD_IMAGE in prompt:
        type = "image"
    elif KEYWARD_EMOJI in prompt:
        type = "emoji"
        prompt = replace_emoji_pattern(prompt)

    if user != None:
        user_info = app.client.users_info(user=user)
        print("user_info: {}".format(user_info))

        user_name = user_info.get("user").get("profile").get("display_name")

        text = "{}: {}".format(user_name, prompt)
    else:
        text = prompt

    content = []
    content.append({"type": "text", "text": text})

    if "files" in event:
        files = event.get("files", [])
        for file in files:
            mimetype = file["mimetype"]
            if mimetype.startswith("image"):
                image_url = file.get("url_private")
                base64_image = get_encoded_image_from_slack(image_url)
                if base64_image:
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                # "url": image_url,
                                "url": f"data:{mimetype};base64,{base64_image}"
                            },
                        }
                    )

    return content, type


# Handle the app_mention event
@app.event("app_mention")
def handle_mention(body: dict, say: Say):
    # print("handle_mention: {}".format(body))

    event = body["event"]

    # if "bot_id" in event:
    #     # Ignore messages from the bot itself
    #     return

    thread_ts = event["thread_ts"] if "thread_ts" in event else event["ts"]
    prompt = re.sub(f"<@{bot_id}>", "", event["text"]).strip()
    channel = event["channel"]
    user = event["user"]
    client_msg_id = event["client_msg_id"]

    content, type = content_from_message(prompt, event, user)

    if type == "image":
        image_generate(say, thread_ts, content, channel, client_msg_id, type)
    else:
        conversation(say, thread_ts, content, channel, user, client_msg_id, type)


# Handle the DM (direct message) event
@app.event("message")
def handle_message(body: dict, say: Say):
    # print("handle_message: {}".format(body))

    event = body["event"]

    if "bot_id" in event:
        # Ignore messages from the bot itself
        return

    thread_ts = None
    prompt = event["text"].strip()
    channel = event["channel"]
    user = event["user"]
    client_msg_id = event["client_msg_id"]

    content, type = content_from_message(prompt, event, None)

    # Use thread_ts=None for regular messages, and user ID for DMs
    if type == "image":
        image_generate(say, thread_ts, content, channel, client_msg_id)
    else:
        conversation(say, thread_ts, content, channel, user, client_msg_id)


# Handle the Lambda function
def lambda_handler(event, context):
    body = json.loads(event["body"])

    if "challenge" in body:
        # Respond to the Slack Event Subscription Challenge
        return {
            "statusCode": 200,
            "headers": {"Content-type": "application/json"},
            "body": json.dumps({"challenge": body["challenge"]}),
        }

    print("lambda_handler: {}".format(body))

    # Duplicate execution prevention
    if "event" not in body or "client_msg_id" not in body["event"]:
        return {
            "statusCode": 200,
            "headers": {"Content-type": "application/json"},
            "body": json.dumps({"status": "Success"}),
        }

    # Get the context from DynamoDB
    token = body["event"]["client_msg_id"]
    prompt = get_context(token, body["event"]["user"])

    if prompt != "":
        return {
            "statusCode": 200,
            "headers": {"Content-type": "application/json"},
            "body": json.dumps({"status": "Success"}),
        }

    # Put the context in DynamoDB
    put_context(token, body["event"]["user"], body["event"]["text"])

    # Handle the event
    return handler.handle(event, context)
