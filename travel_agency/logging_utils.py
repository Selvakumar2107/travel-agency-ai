"""Structured, privacy-conscious logging for SK Holidays Multi-Agent System."""

import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger("sk_holidays.agents")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [Agent:%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class AgentExecutionLogger:
    """Helper to record agent timing, events, and metrics without logging sensitive PII or API keys."""

    def __init__(self, agent_name: str, step_name: str):
        self.agent_name = agent_name
        self.step_name = step_name
        self.start_time = 0.0
        self.end_time = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        logger.info(f"START - Agent: '{self.agent_name}' | Step: '{self.step_name}'")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        if exc_type:
            logger.error(
                f"FAILED - Agent: '{self.agent_name}' | Step: '{self.step_name}' | "
                f"Duration: {duration_ms}ms | Error: {exc_val}"
            )
        else:
            logger.info(
                f"COMPLETE - Agent: '{self.agent_name}' | Step: '{self.step_name}' | "
                f"Duration: {duration_ms}ms"
            )
        return False

    @property
    def duration_ms(self) -> float:
        if self.end_time > 0:
            return round((self.end_time - self.start_time) * 1000, 2)
        return round((time.perf_counter() - self.start_time) * 1000, 2)


def log_optimization_event(pass_number: int, action: str, previous_cost: float, new_cost: float, savings: float):
    """Logs budget optimization pass without sensitive details."""
    logger.info(
        f"OPTIMIZATION PASS {pass_number}: {action} | "
        f"Prev: ₹{previous_cost:,.2f} -> New: ₹{new_cost:,.2f} | Savings: ₹{savings:,.2f}"
    )


def log_fallback_event(agent_name: str, reason: str):
    """Logs when deterministic fallback is used instead of LLM."""
    logger.info(f"FALLBACK USED - Agent: '{agent_name}' | Reason: {reason}")
