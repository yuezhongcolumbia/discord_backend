import asyncio
import selectors

from sqlalchemy import select

from app.ai.ollama_text_embedder import OllamaTextEmbedder
from app.core.config import settings
from app.db.session import async_session_factory
from app.models.conversation_playbook import (
    ConversationPlaybook,
)


PLAYBOOKS = [
    (
        "De-escalate emotional tension",
        """
Use this when the other person sounds hurt, frustrated, defensive, or
overwhelmed.

First acknowledge the emotional impact before explaining your intent.
Use calm, concrete language and lower the pressure of the exchange.
Ask one focused question to understand what matters most to them.

Avoid debating whether their feeling is justified, responding point by
point while they are upset, sarcasm, or demanding an immediate
resolution. A useful response often validates first, clarifies second,
and proposes a small next step last.
""",
    ),
    (
        "Clarify ambiguity before assuming intent",
        """
Use this when a short reply, delayed response, changed tone, or vague
statement could have multiple meanings.

Describe the observable fact without assigning motive. Ask a neutral,
specific question and leave room for an innocent explanation. Focus on
understanding the situation rather than proving an interpretation.

Avoid treating uncertainty as rejection, hostility, dishonesty, or lack
of interest. Do not use accusations disguised as questions, such as
"Why are you ignoring me?" Prefer language such as "I may be reading
this wrong, but I wanted to check what you meant."
""",
    ),
    (
        "State needs and boundaries without blame",
        """
Use this when you need more clarity, consistency, respect, time, or a
change in behavior.

Frame the message around your experience: the situation, its impact on
you, and a specific request or boundary. Make the request realistic and
give the other person room to respond honestly.

Avoid absolute language such as "always" and "never," labels about the
other person's character, threats, or trying to force an immediate
commitment. A boundary should explain what you need or will do, not
control the other person.
""",
    ),
    (
        "Repair after a misstep",
        """
Use this when your wording, timing, joke, assumption, or action may
have made the other person uncomfortable.

Apologize for the specific action and acknowledge its likely impact.
Keep the apology short, take responsibility without over-explaining,
and state what you will do differently. Then give the other person
space rather than demanding reassurance.

Avoid conditional apologies such as "I'm sorry if you felt that way,"
turning the apology into a defense of your intent, repeatedly asking
whether they forgive you, or making them manage your guilt.
""",
    ),
    (
        "Match warmth, pace, and investment",
        """
Use this when the conversation is positive but the level of interest or
pace is uncertain.

Match the other person's approximate warmth, detail, responsiveness, and
initiative. Show interest clearly, but make invitations and next steps
easy to decline. Let reciprocity, rather than anxiety, determine how
much you escalate the conversation.

Avoid sudden emotional intensity, repeated follow-ups without a reply,
large declarations that the conversation has not earned, or trying to
secure certainty too early. Interest is stronger when it is clear and
low-pressure.
""",
    ),
    (
        "Address delayed replies and availability",
        """
Use this when response timing has become emotionally charged or is
causing confusion.

Assume that people have independent schedules unless there is a clear
pattern that needs discussion. If the pattern affects you, describe the
practical impact and ask for a communication expectation that is simple
and realistic.

Avoid monitoring language, scorekeeping, sending multiple messages to
force a response, or interpreting one delay as a relationship verdict.
The goal is mutual clarity about availability, not control over another
person's time.
""",
    ),
    (
        "Turn disagreement into a concrete next step",
        """
Use this when both people have different needs, expectations, or views
and the discussion is starting to repeat itself.

Separate the underlying goal from the current argument. Summarize what
you believe each person needs, identify one decision that can be made
now, and propose a small, reversible next step. Confirm whether your
summary is accurate.

Avoid trying to solve every historical issue at once, winning the
argument, reopening unrelated grievances, or pushing for a permanent
answer before enough information exists.
""",
    ),
    (
        "Make a low-pressure invitation or proposal",
        """
Use this when you want to suggest meeting, continuing a conversation,
or taking a relationship step without creating pressure.

Be direct about what you would enjoy, offer a concrete but flexible
option, and make declining easy. A good invitation has a clear ask,
reasonable timing, and no hidden emotional penalty for saying no.

Avoid vague pressure such as "we should hang out sometime," excessive
justification, repeated persuasion, or framing acceptance as proof of
interest. Respectful clarity is more effective than trying to make the
request impossible to refuse.
""",
    ),
]


async def main() -> None:
    embedder = OllamaTextEmbedder(
        settings.ollama_text_embedding_model_name,
    )

    async with async_session_factory() as session:
        result = await session.scalars(
            select(ConversationPlaybook.title),
        )
        existing_titles = set(result.all())

    playbooks_to_insert = [
        (title, content)
        for title, content in PLAYBOOKS
        if title not in existing_titles
    ]

    if not playbooks_to_insert:
        print("Conversation playbooks already exist.")
        return

    playbooks = []

    for title, content in playbooks_to_insert:
        embedding = await asyncio.to_thread(
            embedder.embed,
            content,
        )

        playbooks.append(
            ConversationPlaybook(
                title=title,
                content=content,
                embedding=embedding,
            )
        )

    async with async_session_factory.begin() as session:
        session.add_all(playbooks)

    print(
        f"Inserted {len(playbooks)} conversation playbooks.",
    )


def create_selector_event_loop() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop(
        selectors.SelectSelector(),
    )


if __name__ == "__main__":
    asyncio.run(
        main(),
        loop_factory=create_selector_event_loop,
    )