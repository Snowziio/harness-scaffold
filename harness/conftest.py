"""Harness pytest plugin: read acm-registry.yaml and skip non-active ACs.

Tests under harness/tests/REQ-<REQ-ID>/ are discovered by filesystem, but
their actual CI participation is gated by acm-registry.yaml:

- status=active        → run normally
- status=superseded_by → skip with reason, still show in report for audit
- status=retired       → skip with reason
- status=shell_patched → run normally (test code was patched with approval)

Tests under harness/tests/_system/ always run (system-level, not AC-bound).
Tests under harness/tests/.REQ-template/ are NEVER collected.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "acm-registry.yaml"
TESTS_ROOT = REPO_ROOT / "harness" / "tests"

REQ_DIR_RE = re.compile(r"^REQ-[A-Z0-9]+-\d+$")


def _load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"requirements": {}, "retirements": {}}
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        # yaml optional at collection time; fail open (everything runs).
        return {"requirements": {}, "retirements": {}}
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    data.setdefault("requirements", {})
    data.setdefault("retirements", {})
    return data


def _ac_status(registry: dict, req_id: str, ac_id: str | None) -> tuple[str, str]:
    """Return (status, reason) for a given REQ/AC combo.

    If ac_id is None (REQ-level test without AC marker), we apply the
    "all-or-nothing" rule: any REQ-level retirement marks the whole REQ
    retired; otherwise active.
    """
    reqs = registry.get("requirements", {})
    entry = reqs.get(req_id, {})
    acs = entry.get("acs", {}) or {}
    if ac_id and ac_id in acs:
        ac = acs[ac_id]
        status = ac.get("status", "active")
        by = ac.get("by", "")
        reason = ac.get("reason", "")
        human = f"{status}" + (f" by {by}" if by else "") + (f": {reason}" if reason else "")
        return status, human
    # Check retirements batch-mark
    for retire_id, retire in registry.get("retirements", {}).items():
        for spec in retire.get("retires", []) or []:
            if spec == f"{req_id}#{ac_id}" or spec == req_id:
                return "retired", f"retired by {retire_id}: {retire.get('reason', '')}"
    return "active", ""


def pytest_collection_modifyitems(config, items):
    registry = _load_registry()
    for item in items:
        path = Path(str(item.fspath))
        try:
            rel = path.relative_to(TESTS_ROOT)
        except ValueError:
            continue  # outside harness/tests/
        parts = rel.parts
        if not parts:
            continue
        top = parts[0]
        # _system/ and .REQ-template/ have their own rules
        if top.startswith("_") or top.startswith("."):
            continue
        if not REQ_DIR_RE.match(top):
            continue
        req_id = top
        # AC id convention: pytest marker @pytest.mark.ac("AC-3") on the test,
        # else None (REQ-level).
        ac_id = None
        for marker in item.iter_markers(name="ac"):
            if marker.args:
                ac_id = str(marker.args[0])
                break
        status, reason = _ac_status(registry, req_id, ac_id)
        if status in ("superseded_by", "retired"):
            item.add_marker(pytest.mark.skip(reason=f"[{status}] {reason}"))


def pytest_configure(config):
    config.addinivalue_line("markers", "ac(id): declare the AC id this test covers")
