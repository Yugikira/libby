"""Unified Serpapi usage policy for all commands."""

from enum import Enum


class SerpapiPolicy(str, Enum):
    """Serpapi usage policy.

    Values:
        - deny: Do not use Serpapi (default, safest)
        - ask: Prompt user for confirmation (single input only)
        - auto: Auto-use Serpapi without confirmation
    """
    deny = "deny"
    ask = "ask"
    auto = "auto"


def parse_serpapi_policy(value: str) -> SerpapiPolicy:
    """Parse serpapi parameter value to policy.

    Args:
        value: One of 'deny', 'ask', 'auto'

    Returns:
        SerpapiPolicy enum

    Raises:
        ValueError: If value is not valid
    """
    try:
        return SerpapiPolicy(value.lower())
    except ValueError:
        valid = [p.value for p in SerpapiPolicy]
        raise ValueError(f"Invalid --serpapi value '{value}'. Valid options: {', '.join(valid)}")


SERPAPI_POLICY_HELP = """Serpapi (Google Scholar) usage policy:
    - deny: Do not use Serpapi (default)
    - ask: Prompt user for confirmation (single input only)
    - auto: Auto-use Serpapi without confirmation

Note: --source serpapi bypasses this policy and uses Serpapi directly."""