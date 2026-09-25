# Uses a tool-calling model to retrieve relevant conversation evidence
# for a draft, with a bounded number of tool calls.
#
# After retrieval, a structured-output model selects up to six useful
# message IDs from the returned tool results.
#
# The server then deduplicates IDs, rejects unknown/hallucinated IDs,
# and returns the verified messages in chronological order.
from uuid import UUID

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama
from pydantic import BaseModel, ConfigDict, Field

from app.domain.message import Message


class _ConversationContextSelection(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    selected_message_ids: list[UUID] = Field(
        default_factory=list,
        max_length=6,
    )


class OllamaConversationContextRetrievalAgent:
    _MAX_TOOL_CALLS = 3

    def __init__(
        self,
        model_name: str,
    ) -> None:
        model = ChatOllama(
            model=model_name,
            temperature=0,
        )

        self._model = model
        self._selection_model = model.with_structured_output(
            _ConversationContextSelection,
        )

        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
You retrieve relevant evidence for a conversational
coaching system.

The draft has not been sent. Use the available tools to find
messages relevant to understanding the draft's interpersonal
context. You may call one or more tools.

Do not give coaching advice. Do not answer the draft. Do not
invent messages. After tool use is complete, select at most six
message IDs from the tool results that best explain the context.
""",
                ),
                (
                    "human",
                    """
Draft written by the current user:

{draft}
""",
                ),
            ],
        )

    async def retrieve_context(
        self,
        draft: str,
        tools: list[BaseTool],
        messages_by_id: dict[UUID, Message],
    ) -> list[Message]:
        tool_model = self._model.bind_tools(tools)
        messages: list[BaseMessage] = (
            self._prompt.format_messages(draft=draft)
        )
        tools_by_name = {
            tool.name: tool
            for tool in tools
        }
        tool_call_count = 0

        while True:
            response = await tool_model.ainvoke(messages)

            if not isinstance(response, AIMessage):
                raise RuntimeError(
                    "Retrieval model did not return an AI message.",
                )

            messages.append(response)

            if not response.tool_calls:
                break

            tool_call_count += len(response.tool_calls)

            if tool_call_count > self._MAX_TOOL_CALLS:
                raise RuntimeError(
                    "Retrieval agent exceeded the tool-call limit.",
                )

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool = tools_by_name.get(tool_name)

                if tool is None:
                    raise RuntimeError(
                        f"Retrieval agent requested unknown tool: "
                        f"{tool_name}",
                    )

                tool_result = await tool.ainvoke(tool_call)

                if not isinstance(tool_result, ToolMessage):
                    raise RuntimeError(
                        "Retrieval tool did not return a tool message.",
                    )

                messages.append(tool_result)

        selection = await self._selection_model.ainvoke(
            messages
            + [
                HumanMessage(
                    content=(
                        "Select only message IDs returned by the "
                        "tools. Return an empty list if no retrieved "
                        "message is useful."
                    ),
                ),
            ],
        )

        return self._select_messages(
            selected_message_ids=selection.selected_message_ids,
            messages_by_id=messages_by_id,
        )

    @staticmethod
    def _select_messages(
        selected_message_ids: list[UUID],
        messages_by_id: dict[UUID, Message],
    ) -> list[Message]:
        selected_messages: list[Message] = []
        seen_message_ids: set[UUID] = set()

        for message_id in selected_message_ids:
            if message_id in seen_message_ids:
                continue

            message = messages_by_id.get(message_id)

            if message is None:
                continue

            seen_message_ids.add(message_id)
            selected_messages.append(message)

        return sorted(
            selected_messages,
            key=lambda message: (
                message.created_at,
                str(message.message_id),
            ),
        )