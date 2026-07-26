from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from wtc.models import ResultCode
from wtc.scenarios import NOW, plan
from wtc.scenarios_aimer import build_fixture, default_dll_path


DLL_PATH = default_dll_path()

pytestmark = pytest.mark.skipif(
    os.name != "nt" or not DLL_PATH.is_file(),
    reason="real AIMer-128f Windows DLL is unavailable",
)


def test_real_aimer_detects_equivocation_and_serializes_evidence() -> None:
    factory, witness, private_key = build_fixture(DLL_PATH)

    c0 = factory.create(
        subject_id="Vehicle-A",
        session_id="REAL-AIMER-TEST",
        epoch=1,
        sequence=0,
        valid_from_ms=NOW - 100,
        valid_until_ms=NOW + 10_000,
        envelopes=plan("1", "KEEP", 100_000),
        private_key=private_key,
    )
    assert witness.process(c0).code is ResultCode.ACCEPT

    c1a = factory.create(
        subject_id="Vehicle-A",
        session_id="REAL-AIMER-TEST",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=plan("2", "LEFT", 110_000),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=private_key,
    )
    assert witness.process(c1a).code is ResultCode.VALID_UPDATE

    c1b = factory.create(
        subject_id="Vehicle-A",
        session_id="REAL-AIMER-TEST",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=plan("3", "RIGHT", 110_000),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=private_key,
    )
    result = witness.process(c1b)

    assert result.code is ResultCode.CONFLICT
    assert result.evidence is not None
    json.dumps(result.evidence.to_dict())
