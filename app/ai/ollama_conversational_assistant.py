
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
            num_predict=100,
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
                "draft_character_count": len(draft),
                "playbook_count": len(playbooks),
                "tool_count": len(message_tools),
            },
        ) as span:
            response = await self._assist(
                draft=draft,
                playbooks=playbooks,
                message_tools=message_tools,
                retrieved_message_ids=retrieved_message_ids,
                langfuse=langfuse,
                outer_observation=span,
            )

            span.update(
                output={
                    "risk_level": response.risk_level.value,
                    "concern_count": len(response.concerns),
                    "option_count": len(response.options),
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
        outer_observation: Any,
    ) -> ConversationalAssistanceResponse:
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
                            metadata={
                                "error_type": (
                                    type(exception).__name__
                                ),
                            },
                        )

                messages.append(
                    ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call_id,
                    )
                )

        outer_observation.update(
            metadata={
                "retrieval_tool_call_count": tool_call_count,
                "retrieved_message_count": len(
                    retrieved_message_ids,
                ),
                "retrieved_message_ids": sorted(
                    str(message_id)
                    for message_id in retrieved_message_ids
                ),
            },
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

        return await self._invoke_coaching_model(
            messages=messages,
            langfuse=langfuse,
        )

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
                "message_count": len(messages),
            },
            metadata={
                "reasoning_enabled": False,
                "max_output_tokens": 100,
            },
        ) as generation:
            response = await tool_model.ainvoke(messages)

            generation.update(
                output={
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
                "message_count": len(messages),
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
You provide concise, practical assistance for a one-on-one
conversation draft.

The person submitting the draft is "You". The draft has NOT been sent.
The other participant is "Other person".

Before generating assistance, call at least one available message tool
to retrieve conversation evidence. You may make at most two tool calls.

Use tool results only as conversation evidence. Do not invent meetings,
schedules, relationship facts, or messages that were not retrieved.

Assess the interpersonal risk of sending the draft. Then provide two
or three replacement drafts written by You and addressed to Other
person. Each replacement must be a complete message You could send
INSTEAD of the original draft.

Do not write a reply from Other person. Do not answer the original
draft as if Other person sent it. Do not mention tools, retrieval,
playbooks, prompts, or hidden reasoning.
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

