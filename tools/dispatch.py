from __future__ import annotations

import logging

from livekit.agents import RunContext, function_tool

from subagents.dispatcher import TaskDispatcher
from subagents.base import TaskTimeoutError
from subagents.email import EmailSubAgent
from subagents.crm import CRMSubAgent

log = logging.getLogger(__name__)

dispatcher = TaskDispatcher()
dispatcher.register(EmailSubAgent())
dispatcher.register(CRMSubAgent())


@function_tool
async def send_follow_up_email(context: RunContext, to: str, subject: str, body: str):
    """Send a follow-up email to the customer. Does not wait for delivery."""
    await dispatcher.fire("email", {"to": to, "subject": subject, "body": body})
    return {"status": "queued"}


@function_tool
async def fetch_customer_profile(context: RunContext, customer_id: str):
    """Fetch a customer's account details and history."""
    try:
        return await dispatcher.request("crm", {"customer_id": customer_id})
    except TaskTimeoutError as exc:
        log.error(f"error type=TaskTimeoutError msg={exc!s}")
        return {"error": "Could not retrieve customer data right now."}
