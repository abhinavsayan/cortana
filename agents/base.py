from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

from livekit.agents import Agent, RunContext
from config.profiles import VoiceProfile, STTProfile, LLMProfile, build_tts, build_stt, build_llm


# Enums in Python are very similar to Enums in Java. 
# They provide type safety and restricted values.
class HandoffStatus(Enum):
    NEW    = "new"     # incoming handoff — agent introduces itself in context
    RETURN = "return"  # returning from sub-task — agent reaffirms / acknowledges result


# @dataclass is the Python equivalent of Java Records (e.g., `public record HandoffContext(...)`) 
# or using Lombok's @Data annotation. It auto-generates __init__ (constructor), __repr__ (toString), etc.
@dataclass
class HandoffContext:
    from_agent:    str
    status:        HandoffStatus
    reason:        str
    # field(default_factory=...) is how we initialize empty default collections (like `new HashMap<>()`)
    session_state: dict = field(default_factory=dict)  # facts accumulated during session
    metadata:      dict = field(default_factory=dict)  # handoff flags e.g. {"resolved": True}


# BaseVoiceAgent inherits from `Agent` (like `public abstract class BaseVoiceAgent extends Agent`).
# This acts as the parent class for all specific agents (like SellerAgent or CustomerAgent).
class BaseVoiceAgent(Agent):
    
    # ClassVar indicates these fields belong to the Class itself, not the instance.
    # In Java, this is analogous to `protected static final` fields, or requiring subclasses 
    # to implement abstract methods that return these profiles.
    # Subclasses (e.g., SellerAgent) MUST define these.
    voice_profile: ClassVar[VoiceProfile]
    stt_profile:   ClassVar[STTProfile]
    llm_profile:   ClassVar[LLMProfile]
    instructions:  ClassVar[str] = ""

    # __init__ is the constructor.
    def __init__(
        self,
        tools: list | None = None,
        handoff_context: HandoffContext | None = None,
    ):
        # super().__init__() calls the parent builder `Agent(...)` in LiveKit.
        super().__init__(instructions=self.instructions, tools=tools or [])
        self._handoff_context = handoff_context
        # State map used to share facts across agents (like a shared Session context map).
        self._state: dict = handoff_context.session_state if handoff_context else {}
        self._session_start = time.perf_counter()
        
        # self.__class__.__name__ dynamically gets the name of the child class (e.g. "SellerAgent")
        # Equivalent to `this.getClass().getSimpleName()` in Java.
        self.log = logging.getLogger(self.__class__.__name__.lower())

    def update_state(self, **kwargs) -> None:
        """Accumulate structured facts during the conversation."""
        # Equivalent to java map `putAll()` method.
        self._state.update(kwargs)

    def _state_context(self) -> str:
        """Format state for injection into LLM greet instructions."""
        if not self._state:
            return ""
        # String manipulation to format context parameters as a bulleted list for the AI.
        lines = "\n".join(f"  - {k}: {v}" for k, v in self._state.items())
        return f"\n\nKnown context about this customer:\n{lines}"

    # on_enter() is an asynchronous lifecycle hook (like @PostConstruct or a start() override)
    # that is triggered when this specific agent becomes active in the Room.
    async def on_enter(self) -> None:
        ctx = self._handoff_context
        if ctx is None:
            self.log.info("agent_enter handoff=none")
        else:
            self.log.info(
                f"agent_enter handoff={ctx.status.value} from={ctx.from_agent} reason={ctx.reason!r}"
            )

        # Here we finally instantiate the STT, LLM, and TTS models for the session.
        # This resolves the commented-out segment you saw previously in worker.py!
        self._tts = build_tts(self.voice_profile)
        self._stt = build_stt(self.stt_profile)
        self._llm = build_llm(self.llm_profile)
        
        # Trigger the initial greeting message.
        await self.greet(self._handoff_context)

    async def greet(self, ctx: HandoffContext | None) -> None:
        """
        Dynamically constructs the first thing the AI says to the customer, 
        depending on why this agent was spawned.
        """
        state_ctx = self._state_context()

        if ctx is None:
            # First time user joins
            instruction = f"Greet the user warmly and ask how you can help.{state_ctx}"

        elif ctx.status == HandoffStatus.NEW:
            # We were just handed off from another agent (e.g. Support -> Sales)
            instruction = (
                f"You've just been handed this conversation from the {ctx.from_agent} team. "
                f"Reason: {ctx.reason}. "
                f"Introduce yourself briefly and pick up naturally — do not repeat what was already said."
                f"{state_ctx}"
            )

        elif ctx.status == HandoffStatus.RETURN:
            # We handed off to another agent, they finished their job, and gave the user back to us.
            instruction = (
                f"You're resuming this conversation. The {ctx.from_agent} team completed a task. "
                f"Outcome: {ctx.reason}. "
                f"Acknowledge the outcome warmly and reaffirm you're here to help with anything else."
                f"{state_ctx}"
            )

        # Send this system instruction dynamically into the running session.
        self.session.generate_reply(instructions=instruction)

    # on_exit() is the teardown lifecycle hook (like @PreDestroy).
    async def on_exit(self) -> None:
        elapsed = time.perf_counter() - self._session_start
        self.log.info(f"agent_exit active={elapsed:.1f}s")
