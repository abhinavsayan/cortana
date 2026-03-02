from __future__ import annotations

from livekit.agents import RunContext, function_tool
from config.profiles import VOICES, STT_MODELS, LLM_MODELS
from agents.base import BaseVoiceAgent, HandoffContext, HandoffStatus


class SellerAgent(BaseVoiceAgent):
    voice_profile = VOICES["asteria"]
    stt_profile   = STT_MODELS["deepgram-en"]
    llm_profile   = LLM_MODELS["anthropic-smart"]
    instructions  = (
        "You are a friendly and knowledgeable sales assistant. "
        "Help customers understand products and services, answer questions, "
        "and guide them toward the best solution for their needs. "
        "Be warm, professional, and concise."
    )

    def __init__(self, handoff_context: HandoffContext | None = None):
        # Import here to avoid circular imports
        from tools.dispatch import send_follow_up_email, fetch_customer_profile
        super().__init__(
            tools=[send_follow_up_email, fetch_customer_profile],
            handoff_context=handoff_context,
        )

    async def greet(self, ctx: HandoffContext | None) -> None:
        if ctx is None:
            self.session.generate_reply(
                instructions="Greet the user warmly and introduce yourself as the sales team."
            )
        else:
            await super().greet(ctx)

    @function_tool
    async def transfer_to_support(self, context: RunContext):
        """Transfer the user to the customer support agent."""
        from agents.customer import CustomerAgent
        ctx = HandoffContext(
            from_agent="seller",
            status=HandoffStatus.NEW,
            reason="Customer needs help with a support issue.",
            session_state=self._state,
        )
        self.log.info(f"handoff to=customer reason={ctx.reason!r}")
        return CustomerAgent(handoff_context=ctx), "Let me bring in our support team."
