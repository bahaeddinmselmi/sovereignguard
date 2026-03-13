import json
from pathlib import Path

from sovereignguard.audit.immutable_logger import ImmutableAuditLogger


def test_immutable_audit_chain_verification(tmp_path):
    log_path = tmp_path / "immutable_audit.jsonl"
    logger = ImmutableAuditLogger(str(log_path))

    logger.log("TEXT_MASKED", session_id="s1", entity_count=2)
    logger.log("TEXT_RESTORED", session_id="s1", tokens_restored=2)

    report = logger.verify_chain()
    assert report["valid"] is True
    assert report["entries_checked"] == 2


def test_immutable_audit_detects_tampering(tmp_path):
    log_path = tmp_path / "immutable_audit_tamper.jsonl"
    logger = ImmutableAuditLogger(str(log_path))

    logger.log("TEXT_MASKED", session_id="s1", entity_count=1)
    logger.log("TEXT_RESTORED", session_id="s1", tokens_restored=1)

    # Tamper with first line
    lines = log_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["data"]["entity_count"] = 999  # tamper
    lines[0] = json.dumps(first)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = logger.verify_chain()
    assert report["valid"] is False
    assert report["first_broken_at"] is not None
    assert len(report["errors"]) >= 1
