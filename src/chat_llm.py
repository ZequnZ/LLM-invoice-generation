import json
import os
from enum import Enum
from typing import TypedDict

from dotenv import load_dotenv
from openai import AzureOpenAI
from pydantic import BaseModel

load_dotenv()  # Load environment variables from .env file


class Role(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(TypedDict):
    role: Role
    content: str


# ref: https://platform.openai.com/docs/api-reference/chat
class Thread:
    client = AzureOpenAI(
        # This is the default and can be omitted
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )

    def __init__(self, sys_prompt: str = "an assistant"):
        self.message_stack = [Message(role="system", content=sys_prompt)]
        self.model = "gpt-4.1"
        self.total_tokens = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.temperature = 1.0
        self.top_p = 1.0

    def _client_send_message(
        self,
        message_stack: list[Message],
        verbose: bool = False,
        response_format: BaseModel | None = None,
    ):
        try:
            if response_format is None:
                send_request = self.client.chat.completions.create(
                    messages=message_stack,
                    model=self.model,
                    temperature=self.temperature,
                    top_p=self.top_p,
                )
            else:
                # ref: https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/structured-outputs?
                send_request = self.client.beta.chat.completions.parse(
                    messages=message_stack,
                    model=self.model,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    response_format=response_format,
                )
            response_body = json.loads(send_request.to_json())
            # finish_reason = response_body['choices'][0]['finish_reason']
            total_tokens, prompt_tokens, completion_tokens = (
                response_body["usage"]["total_tokens"],
                response_body["usage"]["prompt_tokens"],
                response_body["usage"]["completion_tokens"],
            )
            self.total_tokens += total_tokens
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens

            if verbose:
                print(
                    f"Using prompt tokens: {prompt_tokens}, completion token: {completion_tokens}"
                )
            return Message(
                role=response_body["choices"][0]["message"]["role"],
                content=response_body["choices"][0]["message"]["content"],
            )
        except Exception as e:
            print(f"An error occurred while sending the message: {e}")

    def send_message(
        self,
        content: str,
        save_message: bool,
        show_all: bool = False,
        verbose: bool = False,
        response_format: BaseModel | None = None,
    ) -> str:
        message = Message(role="user", content=content)
        self.message_stack.append(message)

        response_message = self._client_send_message(
            self.message_stack, verbose, response_format
        )

        if save_message:
            self.message_stack.append(response_message)
        else:
            self.message_stack.pop()

        if show_all:
            for message in self.message_stack:
                print(f"role: {message['role']}\n\n content:{message['content']}")
        else:
            if verbose:
                print(f"Input:\n {content}\n")
                print(f"Output:\n {response_message['content']}")

        return response_message
