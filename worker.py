from __future__ import annotations

import logging

from livekit.agents import cli, WorkerOptions, JobContext, AgentSession
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from agents.seller import SellerAgent
from agents.customer import CustomerAgent
from config.settings import settings
from config.logging_config import configure_logging

# Configure logging for the application. Similar to configuring Log4j or SLF4J in Java.
configure_logging()

# In Python, dictionaries (like a HashMap<String, Class> in Java) can store class references (types).
# Since Python treats classes as first-class objects, we can look them up dynamically
# and instantiate them later, avoiding a bulky if/else or switch block.
AGENT_REGISTRY = {
    "seller":   SellerAgent,
    "customer": CustomerAgent,
}


async def entrypoint(ctx: JobContext):
    """
    The main asynchronous entrypoint that is called whenever a new job (like a user 
    connecting to a room) is assigned to this worker.
    
    In Java terms, think of this as the `handle(Request req)` method of an 
    asynchronous request handler or a WebSocket connection lifecycle listener.
    
    Args:
        ctx (JobContext): The context for the current job, giving you access to the LiveKit room.
    """
    
    # settings.AGENT_NAME retrieves an environment variable or config value.
    # AGENT_REGISTRY.get() fetches the class reference from our dictionary/HashMap.
    agent_cls = AGENT_REGISTRY.get(settings.AGENT_NAME)
    if agent_cls is None:
        # In Python, ValueError is a built-in exception similar to IllegalArgumentException.
        raise ValueError(
            f"Unknown AGENT_NAME={settings.AGENT_NAME!r}. "
            f"Valid options: {list(AGENT_REGISTRY)}"
        )

    # Get a logger instance specifically for this agent name.
    log = logging.getLogger(settings.AGENT_NAME)
    log.info(f"session_start room={ctx.room.name}")

    # Connect the agent to the LiveKit room. 'await' is used for async operations, 
    # similar to `CompletableFuture.join()` or yielding in a reactive Java stream.
    await ctx.connect()

    # AgentSession manages the media flow (audio in/out) for the AI agent.
    session = AgentSession(
        # Voice Activity Detection (VAD) determines when the user is speaking.
        vad=silero.VAD.load(
            activation_threshold=0.7,
            min_speech_duration=0.15,
            min_silence_duration=0.6,
        ),
        # Turn detection figures out when it's the AI's turn to speak versus the user's turn.
        turn_detection=MultilingualModel(),

        # NOTE: stt (Speech-To-Text), llm (Language Model), and tts (Text-To-Speech)
        # are configured separately (e.g. inside the agent's class lifecycle methods).
    )

    @session.on("user_input_transcribed")
    def on_user_transcript(ev):
        if ev.is_final:
            log.info(f"[USER] {ev.transcript}")

    @session.on("conversation_item_added")
    def on_conversation_item(ev):
        msg = ev.item
        if msg.role == "assistant" and msg.text_content:
            log.info(f"[AGENT] {msg.text_content}")

    # Start the session. agent_cls() instantiates the class we got from AGENT_REGISTRY.
    # In Java, this would look roughly like: `agentCls.getDeclaredConstructor().newInstance()`.
    await session.start(
        room=ctx.room,
        agent=agent_cls(),
        capture_run=True,
    )

    log.info("session_end")


# This is Python's direct equivalent to Java's `public static void main(String[] args)`.
# It checks if this specific file is being run directly as a script (e.g., `python worker.py`).
if __name__ == "__main__":
    # Start the CLI application provided by LiveKit.
    # It registers our `entrypoint` function and handles connecting to the LiveKit Cloud websocket infrastructure.
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name=settings.AGENT_NAME))
