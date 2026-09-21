from uuid import UUID

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from app.domain.message import Message
from app.models.conversation_playbook import (
    ConversationPlaybook,
)
from app.schemas.conversational_assistance import (
    ConversationalAssistanceResponse,
)
from app.observability.langfuse_client import create_langfuse_client

# Conversational assistant safeguards:
# - Restricts assistance to authenticated DM participants.
# - Uses the client cursor as a watermark, waiting briefly until
#   Cassandra contains the requested conversation state.
# - Labels messages as "You" or "Other person" from author IDs,
#   so the model can generate a replacement written by the user.
# - Retrieves relevant playbooks with embeddings and pgvector RAG.
# - Validates structured risk assessments and replacement drafts.
# - Traces end-to-end and Ollama generation latency in Langfuse
#   without sending raw DM content to observability metadata.
class OllamaConversationalAssistant:
    def __init__(
        self,
        model_name: str,
    ) -> None:
        self._model_name = model_name
        model = ChatOllama(
            model=model_name,
            temperature=0,
            reasoning=False,
            keep_alive="30m",
            num_predict=500,
        )

        self._structured_model = model.with_structured_output(
            ConversationalAssistanceResponse,
            include_raw=True,
        )

        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
You provide concise, practical assistance for a one-on-one
conversation draft.

The person submitting the draft is labeled "You" in the conversation.
The draft has NOT been sent yet.

Assess the interpersonal risk of sending the draft. Then provide two
or three replacement drafts written by You and addressed to Other
person. Each replacement must be a complete message You could send
INSTEAD of the original draft.

Do not write a reply from Other person. Do not answer the original
draft as if Other person sent it. Do not invent meetings, schedules,
or relationship facts that are not present in the context.

Ground the risk assessment and every replacement draft in concrete
facts from the recent conversation. Use the supplied playbooks only
as internal guidance. Do not mention playbooks, retrieval, prompts,
or hidden reasoning in the response.
""",
                ),
                (
                    "human",
                    """
Recent conversation, oldest to newest:
{conversation_context}

Internal guidance:
{playbook_context}

Original unsent draft written by You:
{draft}

Generate replacement messages that You could send to Other person
instead of this draft.

Critical rule for every option.draft:

- Write only from You's perspective.
- Each option.draft replaces the original unsent draft.
- Address Other person directly.
- Do not write a reply that Other person would send.
- Do not make You apologize for actions or missed plans caused by
  Other person.
- Preserve the concrete immediate situation in the original draft.
""",
                ),
            ],
        )

    def assist(
            self,
            draft: str,
            messages: list[Message],
            playbooks: list[ConversationPlaybook],
            current_user_id: UUID,
    ) -> ConversationalAssistanceResponse:
        conversation_context = self._format_messages(
            messages,
            current_user_id,
        )
        playbook_context = self._format_playbooks(
            playbooks,
        )

        chain = self._prompt | self._structured_model
        langfuse = create_langfuse_client()

        with langfuse.start_as_current_observation(
                as_type="generation",
                name="conversational-assistance",
                model=self._model_name,
                input={
                    "draft_character_count": len(draft),
                    "context_message_count": len(messages),
                    "context_character_count": len(
                        conversation_context,
                    ),
                    "playbook_count": len(playbooks),
                    "playbook_character_count": len(
                        playbook_context,
                    ),
                },
                metadata={
                    "reasoning_enabled": False,
                    "max_output_tokens": 250,
                },
        ) as generation:
            result = chain.invoke(
                {
                    "conversation_context": conversation_context,
                    "playbook_context": playbook_context,
                    "draft": draft,
                },
            )

            parsed_response = result["parsed"]

            if parsed_response is None:
                raise RuntimeError(
                    "Ollama returned an invalid structured response."
                ) from result["parsing_error"]

            response_metadata = result["raw"].response_metadata

            generation.update(
                output={
                    "risk_level": parsed_response.risk_level.value,
                    "concern_count": len(
                        parsed_response.concerns,
                    ),
                    "option_count": len(
                        parsed_response.options,
                    ),
                },
                metadata={
                    "ollama_load_duration_ms": round(
                        response_metadata["load_duration"] / 1_000_000,
                        2,
                    ),
                    "ollama_prompt_eval_duration_ms": round(
                        response_metadata["prompt_eval_duration"] / 1_000_000,
                        2,
                    ),
                    "ollama_eval_duration_ms": round(
                        response_metadata["eval_duration"] / 1_000_000,
                        2,
                    ),
                    "ollama_total_duration_ms": round(
                        response_metadata["total_duration"] / 1_000_000,
                        2,
                    ),
                    "ollama_prompt_eval_count": response_metadata[
                        "prompt_eval_count"
                    ],
                    "ollama_eval_count": response_metadata["eval_count"],
                },
            )

        return parsed_response

    @staticmethod
    def _format_messages(
        messages: list[Message],
        current_user_id: UUID,
    ) -> str:
        return "\n".join(
            (
                f"{'You' if message.author_id == current_user_id else 'Other person'}: "
                f"{message.message_content or '[attachment only]'}"
            )
            for message in messages
        )

    @staticmethod
    def _format_playbooks(
        playbooks: list[ConversationPlaybook],
    ) -> str:
        return "\n\n".join(
            f"{playbook.title}\n{playbook.content}"
            for playbook in playbooks
        )