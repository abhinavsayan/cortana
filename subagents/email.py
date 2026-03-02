from __future__ import annotations

import logging

from subagents.base import BaseSubAgent, SubAgentMode

log = logging.getLogger(__name__)


class EmailSubAgent(BaseSubAgent):
    task_type = "email"
    mode      = SubAgentMode.FIRE_AND_FORGET

    async def run(self, payload: dict) -> dict:
        to      = payload.get("to", "")
        subject = payload.get("subject", "")
        body    = payload.get("body", "")

        # POC: log only. Replace with real email provider (SendGrid, SES, etc.) later.
        log.info(f"email to={to!r} subject={subject!r} body_len={len(body)}")

        return {"status": "sent", "to": to}
