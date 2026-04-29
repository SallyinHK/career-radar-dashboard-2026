from __future__ import annotations

import re
from typing import Any


def _job_text(job: dict[str, Any]) -> str:
    parts = [
        job.get("title", ""),
        job.get("company", ""),
        job.get("source", ""),
        job.get("description", ""),
        " ".join(job.get("reasons", []) if isinstance(job.get("reasons"), list) else []),
        job.get("company_quality_reason", ""),
    ]
    return " ".join(str(x or "") for x in parts).lower()


def required_years_exceeds(job: dict[str, Any], config: dict[str, Any]) -> bool:
    """
    Hard exclude roles requiring more experience than allowed.

    Default: exclude roles requiring 3+ years of experience.
    This avoids false positives like "1 year contract" because the pattern
    focuses on years + experience / at least / minimum contexts.
    """
    max_allowed = int(config.get("filters", {}).get("max_required_years", 2))
    text = _job_text(job)

    patterns = [
        # at least 5 years / minimum of 4 yrs / over 3 years
        r"\b(?:at\s+least|min(?:imum)?(?:\s+of)?|over|more\s+than|no\s+less\s+than)\s+(\d{1,2})\+?\s*(?:years?|yrs?)\b",

        # 5+ years of experience / 4 years relevant experience / 3 yrs exp
        r"\b(\d{1,2})\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:relevant\s+)?(?:work\s+)?(?:experience|exp)\b",

        # 3-5 years of experience
        r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\s*(?:years?|yrs?)\s+(?:of\s+)?(?:relevant\s+)?(?:work\s+)?(?:experience|exp)\b",
    ]

    for pattern in patterns:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            nums = [int(x) for x in m.groups() if x and x.isdigit()]
            if not nums:
                continue

            required = min(nums)
            if required > max_allowed:
                return True

    return False


def hard_exclude_reason(job: dict[str, Any], config: dict[str, Any]) -> str:
    if required_years_exceeds(job, config):
        return "Role requires more years of experience than allowed."
    return ""


def is_hard_excluded(job: dict[str, Any], config: dict[str, Any]) -> bool:
    return bool(hard_exclude_reason(job, config))
