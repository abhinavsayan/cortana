from __future__ import annotations

import asyncio
import logging

from subagents.base import BaseSubAgent, SubAgentMode

log = logging.getLogger(__name__)


# This CRMSubAgent represents a totally different concept from the `BaseVoiceAgent` we saw earlier.
# While the "Voice Agents" handle the direct speaking/listening Loop with the user over WebRTC,
# "Sub-Agents" execute background tasks (like hitting a database or calling an external API).
# 
# In Java terms, think of Voice Agents as a `websocket.OnMessage` handler, 
# and Sub-Agents as `@Async` Spring services or `Callable<T>` tasks submitted to an `ExecutorService`.
class CRMSubAgent(BaseSubAgent):
    
    # These class-level variables (ClassVar) configure the job.
    task_type = "crm"
    mode      = SubAgentMode.REQUEST_RESPONSE
    timeout   = 8.0 # Fails the task if it takes more than 8 seconds (like a Future.get(8, TimeUnit.SECONDS) timeout)

    # In Python, an `async def` function returns an awaitable coroutine (similar to Java's `CompletableFuture<Map>`).
    # payload: dict is the equivalent of taking a `Map<String, Object>` or a JSON Request DTO.
    async def run(self, payload: dict) -> dict:
        
        # We safely extract the "customer_id" from the dictionary, providing "" as a fallback if it doesn't exist.
        customer_id = payload.get("customer_id", "")
        log.info(f"crm lookup customer_id={customer_id!r}")

        # POC: return stub data. Replace with real CRM API call later.
        
        # `asyncio.sleep` pauses THIS specific async task without blocking the underlying OS thread.
        # This is EXACTLY like Java's `Thread.sleep()` inside virtual threads (Project Loom),
        # or `Mono.delay()` in Spring WebFlux. It simulates the network latency of a database call.
        await asyncio.sleep(0.1)  

        # Return a dictionary containing the fetched data.
        # This dictionary gets serialized back into JSON and returned to whoever called this sub-agent 
        # (usually a Voice Agent that invoked this as a 'tool call' from the LLM).
        return {
            "customer_id":   customer_id,
            "name":          "John Smith",
            "since":         "2022-03-15",
            "plan":          "Pro",
            "open_tickets":  0,
            "last_contact":  "2026-02-01",
        }
