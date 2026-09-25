from typing import Any
from uuid import UUID

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama
from langfuse import Langfuse

from app.models.conversation_playbook import (
    ConversationPlaybook,
)
from app.observability.langfuse_client import (
    create_langfuse_client,
)
from app.schemas.conversational_assistance import (
    ConversationalAssistanceResponse,
)


class OllamaConversationalAssistant:
    def __init__(
        self,
        tool_model_name: str,
        coaching_model_name: str,
    ) -> None:
        self._tool_model_name = tool_model_name
        self._coaching_model_name = coaching_model_name

        self._tool_model = ChatOllama(
            model=tool_model_name,
            temperature=0,
            reasoning=False,
            keep_alive="30m",
            num_predict=300,
        )

        coaching_model = ChatOllama(
            model=coaching_model_name,
            temperature=0,
            reasoning=False,
            keep_alive="30m",
            num_predict=500,
        )

        self._structured_coaching_model = (
            coaching_model.with_structured_output(
                ConversationalAssistanceResponse,
                include_raw=True,
            )
        )

    async def assist(
        self,
        draft: str,
        playbooks: list[ConversationPlaybook],
        message_tools: list[BaseTool],
        retrieved_message_ids: set[UUID],
    ) -> ConversationalAssistanceResponse:
        langfuse = create_langfuse_client()

        with langfuse.start_as_current_observation(
            as_type="span",
            name="conversational-assistance",
            input={
                "draft": draft,
                "playbooks": [
                    {
                        "title": playbook.title,
                        "content": playbook.content,
                    }
                    for playbook in playbooks
                ],
                "draft_character_count": len(draft),
                "playbook_count": len(playbooks),
                "tool_count": len(message_tools),
            },
        ) as span:
            response, retrieval_tool_call_count = (
                await self._assist(
                    draft=draft,
                    playbooks=playbooks,
                    message_tools=message_tools,
                    retrieved_message_ids=retrieved_message_ids,
                    langfuse=langfuse,
                )
            )

            span.update(
                output={
                    "risk_level": response.risk_level.value,
                    "concern_count": len(response.concerns),
                    "option_count": len(response.options),
                    "retrieval_tool_call_count": (
                        retrieval_tool_call_count
                    ),
                    "retrieved_message_count": len(
                        retrieved_message_ids,
                    ),
                    "retrieved_message_ids": sorted(
                        str(message_id)
                        for message_id in retrieved_message_ids
                    ),
                },
            )

            return response

    async def _assist(
        self,
        draft: str,
        playbooks: list[ConversationPlaybook],
        message_tools: list[BaseTool],
        retrieved_message_ids: set[UUID],
        langfuse: Langfuse,
    ) -> tuple[ConversationalAssistanceResponse, int]:
        messages: list[BaseMessage] = [
            SystemMessage(
                content=self._tool_system_prompt(),
            ),
            HumanMessage(
                content=self._initial_user_message(
                    draft=draft,
                    playbooks=playbooks,
                ),
            ),
        ]

        tool_model = self._tool_model.bind_tools(
            message_tools,
            tool_choice="required",
        )
        tools_by_name = {
            message_tool.name: message_tool
            for message_tool in message_tools
        }

        tool_call_count = 0
        max_tool_calls = 2

        while tool_call_count < max_tool_calls:
            response = await self._invoke_tool_model(
                tool_model=tool_model,
                messages=messages,
                langfuse=langfuse,
            )

            messages.append(response)

            if not response.tool_calls:
                break

            for tool_call in response.tool_calls:
                tool_call_id = tool_call["id"]
                tool_name = tool_call["name"]

                if tool_call_count >= max_tool_calls:
                    messages.append(
                        ToolMessage(
                            content=(
                                "Tool call skipped: the maximum "
                                "number of tool calls was reached."
                            ),
                            tool_call_id=tool_call_id,
                        )
                    )
                    continue

                # preventing hallucination(using unknown tools)
                message_tool = tools_by_name.get(
                    tool_name,
                )
                if message_tool is None:
                    messages.append(
                        ToolMessage(
                            content=(
                                f"Unknown tool: {tool_name}."
                            ),
                            tool_call_id=tool_call_id,
                        )
                    )
                    continue

                tool_call_count += 1
                with langfuse.start_as_current_observation(
                    as_type="tool",
                    name=message_tool.name,
                    input=tool_call["args"],
                    metadata={
                        "tool_call_index": tool_call_count,
                    },
                ) as tool_observation:
                    try:
                        tool_result = await message_tool.ainvoke(
                            tool_call["args"],
                        )
                    except Exception as exception:
                        tool_result = (
                            "Tool call failed: "
                            f"{type(exception).__name__}."
                        )
                        tool_observation.update(
                            output=tool_result,
                            metadata={
                                "error_type": (
                                    type(exception).__name__
                                ),
                            },
                        )
                    else:
                        tool_observation.update(
                            output=str(tool_result),
                        )

                messages.append(
                    ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call_id,
                    )
                )

        messages.append(
            HumanMessage(
                content=(
                    "Now generate the final structured coaching "
                    "response. Ground factual claims in the retrieved "
                    "tool results. Do not mention tools, retrieval, "
                    "playbooks, prompts, or hidden reasoning."
                ),
            )
        )

        response = await self._invoke_coaching_model(
            messages=messages,
            langfuse=langfuse,
        )

        return response, tool_call_count

    async def _invoke_tool_model(
        self,
        tool_model: Any,
        messages: list[BaseMessage],
        langfuse: Langfuse,
    ) -> AIMessage:
        with langfuse.start_as_current_observation(
            as_type="generation",
            name="conversation-context-tool-planning",
            model=self._tool_model_name,
            input={
                "messages": [
                    message.model_dump(mode="json")
                    for message in messages
                ],
            },
            metadata={
                "reasoning_enabled": False,
                "max_output_tokens": 100,
            },
        ) as generation:
            response = await tool_model.ainvoke(messages)

            generation.update(
                output={
                    "response": response.model_dump(mode="json"),
                    "tool_call_count": len(response.tool_calls),
                    "tool_names": [
                        tool_call["name"]
                        for tool_call in response.tool_calls
                    ],
                },
                metadata=self._ollama_metadata(response),
            )

            return response

    async def _invoke_coaching_model(
        self,
        messages: list[BaseMessage],
        langfuse: Langfuse,
    ) -> ConversationalAssistanceResponse:
        with langfuse.start_as_current_observation(
            as_type="generation",
            name="conversational-assistance-coaching",
            model=self._coaching_model_name,
            input={
                "messages": [
                    message.model_dump(mode="json")
                    for message in messages
                ],
            },
            metadata={
                "reasoning_enabled": False,
                "max_output_tokens": 500,
            },
        ) as generation:
            result = (
                await self._structured_coaching_model.ainvoke(
                    messages,
                )
            )

            parsed_response = self._parse_coaching_result(
                result,
            )
            raw_response = result["raw"]

            generation.update(
                output={
                    "raw_response": raw_response.model_dump(
                        mode="json",
                    ),
                    "parsed_response": parsed_response.model_dump(
                        mode="json",
                    ),
                    "risk_level": (
                        parsed_response.risk_level.value
                    ),
                    "concern_count": len(
                        parsed_response.concerns,
                    ),
                    "option_count": len(
                        parsed_response.options,
                    ),
                },
                metadata=self._ollama_metadata(
                    raw_response,
                ),
            )

            return parsed_response

    @staticmethod
    def _parse_coaching_result(
        result: dict[str, Any],
    ) -> ConversationalAssistanceResponse:
        parsed_response = result["parsed"]

        if parsed_response is None:
            raise RuntimeError(
                "Ollama returned an invalid structured response.",
            ) from result["parsing_error"]

        return parsed_response

    @staticmethod
    def _ollama_metadata(
        response: AIMessage,
    ) -> dict[str, int | float | None]:
        response_metadata = response.response_metadata

        def duration_ms(
            metadata_name: str,
        ) -> float | None:
            duration_ns = response_metadata.get(
                metadata_name,
            )

            if duration_ns is None:
                return None

            return round(duration_ns / 1_000_000, 2)

        return {
            "ollama_load_duration_ms": duration_ms(
                "load_duration",
            ),
            "ollama_prompt_eval_duration_ms": duration_ms(
                "prompt_eval_duration",
            ),
            "ollama_eval_duration_ms": duration_ms(
                "eval_duration",
            ),
            "ollama_total_duration_ms": duration_ms(
                "total_duration",
            ),
            "ollama_prompt_eval_count": (
                response_metadata.get("prompt_eval_count")
            ),
            "ollama_eval_count": response_metadata.get(
                "eval_count",
            ),
        }

    def _tool_system_prompt(self) -> str:
        return """
You are a retrieval planner for a separate coaching model.

Do not provide coaching, analysis, explanations, or replacement drafts.
Do not answer the draft. Respond only with tool calls when retrieval is
needed.

The person submitting the draft is "You". The other participant is
"Other person". The draft has NOT been sent.

Tool policy:
1. First, call get_recent_messages.
2. After receiving recent messages, call search_messages if they do not
   directly address the draft's topic, concern, or requested action.
3. Use a concise semantic search query focused on the draft topic.
4. You may make at most two tool calls.
5. For search_messages, create a concise semantic query that captures
   the central situation, relevant prior context, and the specific
   fact, concern, expectation, or outcome that earlier messages should
   help verify. Do not merely repeat the draft.

Use only retrieved messages as conversation evidence. Do not invent
conversation facts.
"""

    def _initial_user_message(
        self,
        draft: str,
        playbooks: list[ConversationPlaybook],
    ) -> str:
        return f"""
Internal guidance:
{self._format_playbooks(playbooks)}

Original unsent draft written by You:
{draft}

Retrieve the conversation evidence needed to assess this draft.
"""

    @staticmethod
    def _format_playbooks(
        playbooks: list[ConversationPlaybook],
    ) -> str:
        if not playbooks:
            return "No additional guidance."

        return "\n\n".join(
            f"{playbook.title}\n{playbook.content}"
            for playbook in playbooks
        )