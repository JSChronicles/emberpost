import os
import re
from dataclasses import dataclass

import pagerduty


@dataclass(frozen=True)
class PagerDutyOnCall:
    email: str
    name: str


class PagerDutyClient:
    def __init__(self, tenant: str) -> None:
        self.tenant = tenant
        self.client = pagerduty.RestApiV2Client(self._api_key())

    def get_oncalls(self, schedule_ids: list[str]) -> dict[str, PagerDutyOnCall]:
        if not schedule_ids:
            return {}

        response = self.client.jget(
            "oncalls", params={"schedule_ids": schedule_ids, "earliest": True}
        )

        oncalls_by_schedule_id: dict[str, dict] = {}
        user_ids: set[str] = set()

        for oncall in response.get("oncalls", []):
            schedule_id = oncall["schedule"]["id"]
            if schedule_id in oncalls_by_schedule_id:
                continue
            oncalls_by_schedule_id[schedule_id] = oncall
            user_ids.add(oncall["user"]["id"])

        missing_schedule_ids = set(schedule_ids) - set(oncalls_by_schedule_id)
        if missing_schedule_ids:
            missing = ", ".join(sorted(missing_schedule_ids))
            raise ValueError(f"No on-call user found for schedule(s): {missing}")

        users_by_id = {
            user_id: self.client.rget(f"users/{user_id}")
            for user_id in sorted(user_ids)
        }

        return {
            schedule_id: PagerDutyOnCall(
                email=users_by_id[oncall["user"]["id"]]["email"],
                name=oncall["user"]["summary"],
            )
            for schedule_id, oncall in oncalls_by_schedule_id.items()
        }

    def _api_key(self) -> str:
        tenant_env_name = re.sub(r"[^A-Z0-9]", "_", self.tenant.upper())
        env_var = f"PAGERDUTY_API_KEY_{tenant_env_name}"
        api_key = os.getenv(env_var)
        if not api_key:
            raise ValueError(
                f"Missing PagerDuty API key for {self.tenant}. Set {env_var}."
            )
        return api_key
