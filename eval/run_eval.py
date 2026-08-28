"""Measure rules_engine.evaluate()'s content-analysis checks (checks 9 and 10)
against the held-out eval/malicious.json and eval/benign.json sets.

Measurement only. Does not modify rules_engine.py or any detection logic.

Usage: python3 eval/run_eval.py
(run from the repo root)
"""

import json
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = REPO_ROOT / "backend"
# app.rules_engine re-exports from the standalone mandate-guard package;
# add its src/ so this script runs without the package being pip-installed.
GUARD_SRC_DIR = REPO_ROOT / "packages" / "mandate-guard" / "src"

sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(GUARD_SRC_DIR))

from app.domain import Mandate, TransactionRequest  # noqa: E402
from app.rules_engine import evaluate  # noqa: E402

NOW = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)

# Permissive mandate: high caps, broad allowlist, full-day window, active,
# far-future expiry. Only checks 9 (hard injection block) and 10 (soft
# override flag) are exercised — every earlier check (status/expiry, replay,
# per-txn/window/lifetime caps, merchant/category allowlist, time window)
# is deliberately made a pass-through so it cannot contribute to the result.
PERMISSIVE_MANDATE = Mandate(
    mandate_id="eval-mandate",
    user_id="eval-user",
    agent_id="eval-agent",
    agent_platform="eval-platform",
    agent_display_name="Eval Harness Agent",
    created_at=NOW - timedelta(days=365),
    expires_at=NOW + timedelta(days=3650),
    status="active",
    max_amount_per_txn=10**12,
    max_amount_per_window=10**12,
    window_duration=10**9,
    max_amount_total=10**12,
    merchant_allowlist=["eval-merchant"],
    category_allowlist=["eval-category"],
    allowed_time_window=(time(0, 0), time(23, 59, 59)),
    original_intent_text="__eval_harness_sentinel_intent__",
    user_facing_summary="Eval harness permissive mandate.",
)

PERMISSIVE_CONTEXT = {
    "now": NOW,
    "seen_transaction_ids": set(),
    "window_total": 0.0,
    "lifetime_total": 0.0,
}


def make_txn(entry_index: int, source_content: str) -> TransactionRequest:
    return TransactionRequest(
        transaction_id=f"eval-txn-{entry_index}",
        mandate_id=PERMISSIVE_MANDATE.mandate_id,
        proposed_amount=1.0,
        merchant_id="eval-merchant",
        category="eval-category",
        timestamp=NOW,
        source_content=source_content,
        agent_reasoning="",
    )


def classify_decision(decision) -> str:
    """Map a Decision to 'block' | 'flag' | 'allow'."""
    if decision.outcome == "BLOCK":
        return "block"
    if decision.flagged:
        return "flag"
    return "allow"


def is_detected(expected: str, actual: str) -> bool:
    """For malicious entries, block or flag both count as detected."""
    if expected in ("block", "flag"):
        return actual in ("block", "flag")
    return actual == expected


def run_set(entries: list[dict], source_file: str) -> list[dict]:
    results = []
    for i, entry in enumerate(entries):
        txn = make_txn(i, entry["source_content"])
        decision = evaluate(txn, PERMISSIVE_MANDATE, dict(PERMISSIVE_CONTEXT))
        actual = classify_decision(decision)
        expected = entry["expected_result"]
        result = {
            "index": i,
            "input_file": source_file,
            "source_content": entry["source_content"],
            "expected_result": expected,
            "actual_result": actual,
            "decision_outcome": decision.outcome,
            "decision_reason": decision.reason,
            "decision_flagged": decision.flagged,
            "decision_flag_reason": decision.flag_reason,
            "match": is_detected(expected, actual),
        }
        if "attack_type" in entry:
            result["attack_type"] = entry["attack_type"]
        if "benign_reason" in entry:
            result["benign_reason"] = entry["benign_reason"]
        results.append(result)
    return results


def main() -> None:
    malicious = json.loads((EVAL_DIR / "malicious.json").read_text())
    benign = json.loads((EVAL_DIR / "benign.json").read_text())

    malicious_results = run_set(malicious, "malicious")
    benign_results = run_set(benign, "benign")
    all_results = malicious_results + benign_results

    (EVAL_DIR / "results.json").write_text(json.dumps(all_results, indent=2))

    n_malicious = len(malicious_results)
    n_benign = len(benign_results)

    tp = sum(1 for r in malicious_results if r["match"])
    fn_entries = [r for r in malicious_results if not r["match"]]
    fn = len(fn_entries)
    recall = tp / n_malicious if n_malicious else 0.0

    tn = sum(1 for r in benign_results if r["match"])
    fp_entries = [r for r in benign_results if not r["match"]]
    fp = len(fp_entries)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    fpr = fp / n_benign if n_benign else 0.0

    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    print(f"Malicious set (n={n_malicious})")
    print(f"  True positives (blocked or flagged): {tp}")
    print(f"  False negatives (passed as clean allow): {fn}")
    print(f"  Recall: {recall:.4f}")
    print()
    print(f"Benign set (n={n_benign})")
    print(f"  True negatives (correctly allowed clean): {tn}")
    print(f"  False positives (wrongly blocked/flagged): {fp}")
    print(f"  Precision: {precision:.4f}")
    print(f"  False positive rate: {fpr:.4f}")
    print()
    print(f"Overall F1: {f1:.4f}")

    write_report(
        n_malicious, n_benign, tp, fn, recall, tn, fp, precision, fpr, f1,
        fn_entries, fp_entries,
    )
    print()
    print(f"Wrote {EVAL_DIR / 'results.json'}")
    print(f"Wrote {EVAL_DIR / 'REPORT.md'}")


def _fn_note(attack_type: str) -> str:
    notes = {
        "authority_claim": "No hard/soft pattern targets false-authority phrasing "
            "(\"pre-cleared\", \"blanket authorization\", \"clearance\"); "
            "would need an authority-claim lexicon.",
        "social_engineering": "No pattern targets persuasion/urgency framing "
            "(\"just process it\", \"complete it now, verify after\"); "
            "would need a social-engineering/pressure lexicon.",
        "embedded_system_message": "No pattern detects embedded role/system-message "
            "structures (JSON \"role\": \"system\", HTML comments, "
            "[[POLICY_CONTEXT]] blocks); would need a structural scan for "
            "embedded message-like payloads, not just phrase matching.",
        "misdirection": "No pattern targets amount/field misdirection language "
            "(\"the real total is\", \"use the reconciled balance instead\"); "
            "would need semantic detection of a stated field being overridden "
            "by a second conflicting value in the same content.",
        "unicode_trick": "No normalization step (NFKC / zero-width-char stripping / "
            "homoglyph mapping) runs before pattern matching, so lookalike "
            "characters and fullwidth digits evade every regex untouched.",
        "price_manipulation": "No pattern detects a stated price being overridden "
            "by a second, larger amount elsewhere in the same content "
            "(\"amount to authorize is X, not the displayed price\"); "
            "purely regex-based checks have no notion of amount fields at all.",
        "recipient_swap": "No pattern detects payee/beneficiary-account substitution "
            "language (\"our banking relationship moved to\", \"current beneficiary "
            "is now\"); would need a payee-change lexicon or cross-check against "
            "the mandate's known merchant identity.",
        "urgency_pressure": "No pattern targets time-pressure/scarcity framing "
            "(\"expires in\", \"complete now, review after\") absent an explicit "
            "override/bypass keyword.",
    }
    return notes.get(attack_type, "No existing hard or soft pattern matches this content.")


def write_report(
    n_malicious, n_benign, tp, fn, recall, tn, fp, precision, fpr, f1,
    fn_entries, fp_entries,
) -> None:
    lines = []
    lines.append("# Eval Report: rules_engine.evaluate() checks 9 and 10")
    lines.append("")
    lines.append("Measurement against the held-out eval/malicious.json and eval/benign.json sets.")
    lines.append("")
    lines.append("## Numbers")
    lines.append("")
    lines.append(f"- Malicious set: n={n_malicious}")
    lines.append(f"  - True positives (blocked or flagged): {tp}")
    lines.append(f"  - False negatives (passed as clean allow): {fn}")
    lines.append(f"  - Recall: {recall:.4f}")
    lines.append(f"- Benign set: n={n_benign}")
    lines.append(f"  - True negatives (correctly allowed clean): {tn}")
    lines.append(f"  - False positives (wrongly blocked/flagged): {fp}")
    lines.append(f"  - Precision: {precision:.4f}")
    lines.append(f"  - False positive rate: {fpr:.4f}")
    lines.append(f"- Overall F1: {f1:.4f}")
    lines.append("")
    lines.append("## False negatives")
    lines.append("")
    if not fn_entries:
        lines.append("None.")
    else:
        for r in fn_entries:
            lines.append(f"- index {r['index']} ({r['attack_type']})")
            lines.append(f"  - source_content: {r['source_content']!r}")
            lines.append(f"  - actual_result: {r['actual_result']} (reason: {r['decision_reason']})")
            lines.append(f"  - why likely missed: {_fn_note(r['attack_type'])}")
    lines.append("")
    lines.append("## False positives")
    lines.append("")
    if not fp_entries:
        lines.append("None.")
    else:
        for r in fp_entries:
            lines.append(f"- index {r['index']}")
            lines.append(f"  - source_content: {r['source_content']!r}")
            lines.append(f"  - actual_result: {r['actual_result']} (reason: {r['decision_reason']}, "
                          f"flag_reason: {r['decision_flag_reason']})")
            lines.append(f"  - benign_reason: {r['benign_reason']}")
    lines.append("")

    (EVAL_DIR / "REPORT.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
