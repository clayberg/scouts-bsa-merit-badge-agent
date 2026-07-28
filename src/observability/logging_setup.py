"""Structured JSON Logging, Intent vs. Outcome capture, and PII redaction layer.

This module implements:
1. Structured JSON logging via python-json-logger.
2. Explicit PII redaction before sinks (scrubbing Counselor email & phone).
3. Intent vs. Outcome wrappers for agent tool calls.
"""

import logging
import time
import re
from typing import Callable, Dict, Any
from pythonjsonlogger import jsonlogger

# ==============================================================================
# PII REDACTION BEFORE SINK (OBSERVABILITY RUBRIC CATEGORY 4)
# ==============================================================================

EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
PHONE_REGEX = re.compile(r'\b(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b')

def scrub_pii_before_sink(text: str) -> str:
    """Scrubs PII (email addresses and phone numbers) before emitting to log sinks.
    
    Args:
        text: Raw text or stringified JSON payload.
        
    Returns:
        str: Redacted string safe for external observability and eval sinks.
    """
    if not isinstance(text, str):
        text = str(text)
    text = EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)
    text = PHONE_REGEX.sub("[REDACTED_PHONE]", text)
    return text

# ==============================================================================
# STRUCTURED JSON LOGGER SETUP
# ==============================================================================

class PIIRedactingJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter that redacts PII fields before serializing log records."""
    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return scrub_pii_before_sink(formatted)

def get_structured_logger(name: str = "scouts_bsa_agent") -> logging.Logger:
    """Configures and returns a structured JSON logger with PII scrubbing.
    
    Args:
        name: Logger name.
        
    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = PIIRedactingJsonFormatter(
            '%(asctime)s %(levelname)s %(name)s %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

logger = get_structured_logger()

# ==============================================================================
# INTENT VS. OUTCOME EXECUTION WRAPPER
# ==============================================================================

def execute_tool_with_observability(
    tool_name: str,
    arguments: Dict[str, Any],
    execute_fn: Callable[..., Any],
    **kwargs
) -> Any:
    """Executes a tool while capturing Intent before and Outcome after execution.
    
    Args:
        tool_name: Specific domain name of the tool being executed.
        arguments: Keyword arguments passed to the tool.
        execute_fn: Target tool function to execute.
        **kwargs: Additional context variables for logging.
        
    Returns:
        Any: Result of execute_fn(**arguments).
        
    Raises:
        Exception: Re-raises any exception after logging the error outcome.
    """
    scrubbed_args = {k: scrub_pii_before_sink(str(v)) for k, v in arguments.items()}
    
    # 1. Log INTENT before execution
    logger.info("Tool execution intent", extra={
        "event_type": "tool_intent",
        "tool_name": tool_name,
        "intended_arguments": scrubbed_args,
    })
    
    start_time = time.time()
    try:
        result = execute_fn(**arguments)
        duration_ms = int((time.time() - start_time) * 1000)
        
        # 2. Log OUTCOME (SUCCESS) after execution
        logger.info("Tool execution outcome", extra={
            "event_type": "tool_outcome",
            "tool_name": tool_name,
            "status": "SUCCESS",
            "latency_ms": duration_ms,
            "result_summary": scrub_pii_before_sink(str(result)[:200]),
        })
        return result
    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        
        # 3. Log OUTCOME (ERROR) after failure
        logger.error("Tool execution error", extra={
            "event_type": "tool_outcome",
            "tool_name": tool_name,
            "status": "ERROR",
            "latency_ms": duration_ms,
            "error_message": scrub_pii_before_sink(str(exc)),
        })
        raise
