from __future__ import annotations

from pathlib import Path

from simulation.experiments.run_baseline_benchmark import (
    run_repetition,
)
from simulation.sumo.controllers.run_wtc_sumo import (
    create_signer_bundle,
)


def test_mock_baseline_accounting_and_validation():
    bundle = create_signer_bundle(
        "mock",
        witness_count=3,
        haetae_dll=Path("unused"),
        aimer_dll=Path("unused"),
    )

    row = run_repetition(
        algorithm="mock",
        slot_count=5,
        witness_count=3,
        signer_bundle=bundle,
        slot_ms=200,
    )

    assert row["baseline_a_valid"]
    assert row["commitment_signature_valid"]
    assert row["disclosures_valid"]
    assert row["receipts_valid"]
    assert row["gossip_valid"]
    assert row["baseline_a_subject_signature_count"] == 5
    assert row["baseline_b_subject_signature_count"] == 1
    assert row["proposed_subject_signature_count"] == 1
    assert row["proposed_witness_signature_count"] == 3
    assert row["proposed_gossip_message_count"] == 6
    assert row["baseline_a_network_tx_bytes"] > 0
    assert row["baseline_b_network_tx_bytes"] > 0
    assert row["proposed_network_tx_bytes"] > 0
