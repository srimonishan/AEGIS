"""
Regression test for a real bug: `extra={"args": ...}` in a logging call
raises `KeyError: "Attempt to overwrite 'args' in LogRecord"` because
`args` is a reserved LogRecord attribute -- but ONLY once logging is
actually enabled at INFO level. pytest's root logger defaults to
WARNING, so `logger.info(...)` short-circuits before ever building the
record and the bug is invisible under the normal test suite (including
the full scripted-LLM tool-loop test in test_agent_tool_loop.py, which
never enables INFO logging). This only surfaced by running the real
container end-to-end with real logging configured -- see main.py's
`logging.basicConfig(level=logging.INFO)`.

This test forces INFO logging explicitly so the bug (or any regression
of its shape) fails here, not just in a live container.
"""

import logging
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GEMINI_MODEL", "gemini-3.5-flash")
os.environ.setdefault("META_ACCESS_TOKEN", "x")
os.environ.setdefault("META_PHONE_NUMBER_ID", "x")
os.environ.setdefault("GLOBAL_PATTERN_SALT", "test-salt")
os.environ.setdefault(
    "CONTACT_DIRECTORY_KMS_KEY", "projects/test/locations/us/keyRings/r/cryptoKeys/k"
)
os.environ.setdefault("AEGIS_USER_ID_PEPPER", "test-pepper")

from aegis_agent.agent import _after_tool_callback, _before_tool_callback


def test_before_tool_callback_does_not_crash_with_info_logging_enabled(caplog):
    tool = MagicMock()
    tool.name = "analyze_content"
    tool_context = MagicMock()
    tool_context.state = {"report_id": "r1"}

    with caplog.at_level(logging.INFO, logger="aegis.orchestrator.agent"), patch(
        "firestore_client.append_reasoning_trace"
    ):
        # Must not raise -- this call previously crashed with
        # KeyError: "Attempt to overwrite 'args' in LogRecord" whenever
        # logging was actually enabled.
        _before_tool_callback(
            tool=tool,
            args={"manipulation_patterns": ["urgency"], "confidence": 0.8},
            tool_context=tool_context,
        )

    assert any("tool_call_start" in r.message for r in caplog.records)


def test_after_tool_callback_does_not_crash_with_info_logging_enabled(caplog):
    tool = MagicMock()
    tool.name = "check_sender_reputation"
    tool_context = MagicMock()
    tool_context.state = {"report_id": "r1"}

    with caplog.at_level(logging.INFO, logger="aegis.orchestrator.agent"), patch(
        "firestore_client.append_reasoning_trace"
    ):
        _after_tool_callback(
            tool=tool,
            args={"entity": "http://example.com"},
            tool_context=tool_context,
            tool_response={"prior_sightings": 0},
        )

    assert any("tool_call_end" in r.message for r in caplog.records)
