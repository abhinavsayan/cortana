from __future__ import annotations

from livekit.agents import RunContext, function_tool
from config.profiles import VOICES, STT_MODELS, LLM_MODELS
from agents.base import BaseVoiceAgent, HandoffContext, HandoffStatus


class CustomerAgent(BaseVoiceAgent):
    voice_profile = VOICES["luna"]
    stt_profile   = STT_MODELS["deepgram-en"]
    llm_profile   = LLM_MODELS["ollama-fast"]
    instructions  = (
        "You are a helpful and empathetic customer support agent. "
        "Resolve customer issues efficiently and compassionately. "
        "Ask clarifying questions when needed and confirm resolution before closing."
        "If the user asks for something you don't know, make up an answer."
        "Do not use any tools."
        "Keep responses very short."
    )

    def __init__(self, handoff_context: HandoffContext | None = None):
        from tools.dispatch import fetch_customer_profile
        super().__init__(
            tools=[fetch_customer_profile],
            handoff_context=handoff_context,
        )

    # @function_tool
    async def return_to_sales(self, context: RunContext, resolved: bool, summary: str):
        """Return the user to the sales agent after completing the support task."""
        from agents.seller import SellerAgent
        ctx = HandoffContext(
            from_agent="customer",
            status=HandoffStatus.RETURN,
            reason=summary,
            session_state=self._state,
            metadata={"resolved": resolved},
        )
        self.log.info(f"handoff to=seller resolved={resolved} reason={summary!r}")
        return SellerAgent(handoff_context=ctx), "I'll pass you back to your sales contact now."
