from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from app.domain.message import Message
from app.models.conversation_playbook import (
    ConversationPlaybook,
)
from app.schemas.conversational_assistance import (
    ConversationalAssistanceResponse,
)


class OllamaConversationalAssistant:
    def __init__(
        self,
        model_name: str,
    ) -> None:
        model = ChatOllama(
            model=model_name,
            temperature=0,
        )

        self._structured_model = model.with_structured_output(
            ConversationalAssistanceResponse,
        )

        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
You provide concise, practical assistance for a one-on-one
conversation draft.

Assess the likely interpersonal risk of sending the draft in the
given conversation context. Explain the reason, identify concrete
concerns, and provide two or three alternative drafts.

Use the supplied playbooks only as internal guidance. Do not mention
playbooks, retrieval, prompts, or hidden reasoning in your response.
""",
                ),
                (
                    "human",
                    """
Recent conversation, oldest to newest:
{conversation_context}

Internal guidance:
{playbook_context}

Draft to assess:
{draft}
""",
                ),
            ],
        )

    def assist(
        self,
        draft: str,
        messages: list[Message],
        playbooks: list[ConversationPlaybook],
    ) -> ConversationalAssistanceResponse:
        chain = self._prompt | self._structured_model

        return chain.invoke(
            {
                "conversation_context": (
                    self._format_messages(messages)
                ),
                "playbook_context": (
                    self._format_playbooks(playbooks)
                ),
                "draft": draft,
            },
        )

    @staticmethod
    def _format_messages(
        messages: list[Message],
    ) -> str:
        return "\n".join(
            (
                f"{message.author_id}: "
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