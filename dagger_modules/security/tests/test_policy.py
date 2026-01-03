from pathlib import Path

from security_module import policy


def test_policy_counts_bandit(tmp_path):
    bandit_path = Path(tmp_path) / "bandit.json"
    bandit_path.write_text(
        """
        {
            "results": [
                {"issue_severity": "HIGH"},
                {"issue_severity": "MEDIUM"}
            ]
        }
        """,
        encoding="utf-8",
    )
    counts = policy.collect_severity_counts(Path(tmp_path))
    assert counts["high"] == 1
    assert counts["medium"] >= 1


def test_policy_enforces_thresholds(tmp_path):
    # Write DAST placeholder results
    (Path(tmp_path) / "dast-results.json").write_text(
        """
        {"findings": [{"severity": "high"}, {"severity": "medium"}]}
        """,
        encoding="utf-8",
    )
    thresholds = {"high": 0, "medium": 1}
    violations = policy.enforce_thresholds(Path(tmp_path), thresholds)
    assert violations, "violations should be returned when counts exceed thresholds"
