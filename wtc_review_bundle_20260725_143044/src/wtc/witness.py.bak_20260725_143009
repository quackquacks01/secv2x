from __future__ import annotations

import hashlib
import time
from typing import Callable

from .commitment import commitment_digest_hex, commitment_message
from .crypto import Signer
from .encoding import canonical_json_bytes
from .models import (
    Commitment,
    EvidenceBundle,
    ProcessResult,
    ResultCode,
    WitnessReceipt,
)


RECEIPT_DOMAIN = b"KPQC-TRAJECTORY-WITNESS-RECEIPT-V1"


class WitnessNode:
    def __init__(
        self,
        *,
        witness_id: str,
        subject_signer: Signer,
        witness_signer: Signer,
        subject_public_keys: dict[str, bytes],
        witness_private_key: bytes,
        witness_public_keys: dict[str, bytes] | None = None,
        now_ms: Callable[[], int] | None = None,
    ):
        self.witness_id = witness_id
        self.subject_signer = subject_signer
        self.witness_signer = witness_signer
        self.subject_public_keys = dict(subject_public_keys)
        self.witness_public_keys = dict(witness_public_keys or {})
        self.witness_private_key = witness_private_key
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))

        self.active_head_cache: dict[
            tuple[str, str, int], Commitment
        ] = {}
        self.latest_by_session = self.active_head_cache
        self.observation_cache: dict[
            tuple[str, str, int, int], dict[str, list[WitnessReceipt]]
        ] = {}
        self.pending_update_cache: dict[
            tuple[str, str, int, int], list[tuple[Commitment, WitnessReceipt]]
        ] = {}
        self.evidence_store: list[EvidenceBundle] = []
        self.evidence_log = self.evidence_store
        self.commits_by_digest: dict[str, Commitment] = {}
        self.receipts_by_consistency_key: dict[
            tuple[str, str, int, int], WitnessReceipt
        ] = {}

    def _verify_subject_signature(self, commitment: Commitment) -> bool:
        public_key = self.subject_public_keys.get(commitment.subject_id)
        if public_key is None:
            return False
        return self.subject_signer.verify(
            commitment_message(commitment),
            commitment.signature,
            public_key,
        )

    def _make_receipt(
        self,
        commitment: Commitment,
        observed_at_ms: int,
        *,
        decision: str = "OBSERVED",
    ) -> WitnessReceipt:
        unsigned = WitnessReceipt(
            witness_id=self.witness_id,
            subject_id=commitment.subject_id,
            session_id=commitment.session_id,
            epoch=commitment.epoch,
            sequence=commitment.sequence,
            merkle_root=commitment.merkle_root,
            commitment_digest=commitment_digest_hex(commitment),
            observed_at_ms=observed_at_ms,
            signature_algorithm=self.witness_signer.algorithm_name,
            decision=decision,
        )
        message = RECEIPT_DOMAIN + canonical_json_bytes(unsigned.unsigned_dict())
        signature = self.witness_signer.sign(
            message,
            self.witness_private_key,
        )
        return unsigned.with_signature(signature)

    def _store_commitment(
        self,
        commitment: Commitment,
        receipt: WitnessReceipt,
        now_ms: int,
        update_active_head: bool = True,
    ) -> None:
        consistency_key = commitment.consistency_key
        self.receipts_by_consistency_key[consistency_key] = receipt
        if update_active_head:
            self.active_head_cache[commitment.session_key] = commitment
        self.commits_by_digest[commitment_digest_hex(commitment)] = commitment

        root_map = self.observation_cache.setdefault(consistency_key, {})
        root_map.setdefault(commitment.merkle_root, []).append(receipt)

    def _resolve_pending_updates(self, commitment: Commitment, now_ms: int) -> None:
        for key, pending_list in list(self.pending_update_cache.items()):
            remaining = []
            for pending_commitment, pending_receipt in pending_list:
                if (
                    pending_commitment.parent_root == commitment.merkle_root
                    and pending_commitment.sequence == commitment.sequence + 1
                ):
                    if pending_commitment.context_digest is None:
                        continue
                    receipt = self._make_receipt(
                        pending_commitment,
                        now_ms,
                        decision="ACCEPTED",
                    )
                    self._store_commitment(pending_commitment, receipt, now_ms)
                    self._resolve_pending_updates(pending_commitment, now_ms)
                else:
                    remaining.append((pending_commitment, pending_receipt))
            if remaining:
                self.pending_update_cache[key] = remaining
            else:
                self.pending_update_cache.pop(key, None)

    def process(self, commitment: Commitment) -> ProcessResult:
        now = self.now_ms()

        # 1. 서명 검증 전에는 어떤 캐시도 갱신하지 않는다.
        if not self._verify_subject_signature(commitment):
            return ProcessResult(
                ResultCode.INVALID_SIGNATURE,
                "subject signature verification failed",
            )

        # 2. 만료된 Commitment 거부
        if commitment.valid_until_ms < now:
            return ProcessResult(
                ResultCode.STALE,
                "commitment validity window has expired",
            )

        key = commitment.consistency_key
        root_map = self.observation_cache.get(key, {})
        duplicate_digest = self.commits_by_digest.get(commitment_digest_hex(commitment))

        # 3. 동일 Commitment Digest 처리
        if duplicate_digest is not None:
            receipt = self.receipts_by_consistency_key.get(duplicate_digest.consistency_key)
            return ProcessResult(
                ResultCode.DUPLICATE,
                "same commitment digest already observed",
                receipt=receipt,
            )

        # 4. 동일 Consistency Key 처리
        if commitment.merkle_root in root_map:
            receipt = root_map[commitment.merkle_root][0]
            return ProcessResult(
                ResultCode.DUPLICATE,
                "same consistency key and same Merkle root",
                receipt=receipt,
            )

        existing_same_key = None
        if root_map:
            # any observed commitment with the same key but different root
            existing_root = next(iter(root_map))
            existing_receipt = root_map[existing_root][0]
            existing_same_key = self.commits_by_digest.get(existing_receipt.commitment_digest)

        if existing_same_key is not None:
            new_receipt = self._make_receipt(commitment, now, decision="OBSERVED_CONFLICT")
            self._store_commitment(commitment, new_receipt, now, update_active_head=False)
            evidence = EvidenceBundle(
                commitment_a=existing_same_key,
                commitment_b=commitment,
                witness_id=self.witness_id,
                detected_at_ms=now,
                receipt_a=existing_receipt,
                receipt_b=new_receipt,
            )
            self.evidence_store.append(evidence)
            return ProcessResult(
                ResultCode.CONFLICT,
                "same consistency key but different validly signed Merkle roots",
                receipt=new_receipt,
                evidence=evidence,
            )

        session_key = commitment.session_key
        latest = self.latest_by_session.get(session_key)

        # 4. 첫 Commitment
        if latest is None:
            if commitment.sequence != 0 or commitment.parent_root is not None:
                return ProcessResult(
                    ResultCode.INVALID_UPDATE,
                    "first commitment must use sequence 0 and parent_root=None",
                )

            receipt = self._make_receipt(
                commitment,
                now,
                decision="ACCEPTED",
            )
            self._store_commitment(commitment, receipt, now)
            self._resolve_pending_updates(commitment, now)
            return ProcessResult(
                ResultCode.ACCEPT,
                "initial commitment accepted",
                receipt=receipt,
            )

        # 5. 이미 처리한 sequence보다 과거인 경우
        if commitment.sequence <= latest.sequence:
            return ProcessResult(
                ResultCode.STALE,
                "sequence is older than or equal to the latest accepted sequence",
            )

        # 6. 정확한 단조 증가 확인
        if commitment.sequence == latest.sequence + 1:
            if commitment.parent_root != latest.merkle_root:
                return ProcessResult(
                    ResultCode.INVALID_UPDATE,
                    "parent_root does not match the latest accepted Merkle root",
                )
            if commitment.context_digest is None:
                return ProcessResult(
                    ResultCode.INVALID_UPDATE,
                    "updated commitment must include context_digest",
                )
            receipt = self._make_receipt(commitment, now, decision="ACCEPTED")
            self._store_commitment(commitment, receipt, now)
            self._resolve_pending_updates(commitment, now)
            return ProcessResult(
                ResultCode.VALID_UPDATE,
                "re-commitment chain is valid",
                receipt=receipt,
            )

        if commitment.sequence > latest.sequence + 1:
            if commitment.parent_root == latest.merkle_root:
                return ProcessResult(
                    ResultCode.INVALID_UPDATE,
                    "sequence jump is invalid",
                )
            receipt = self._make_receipt(commitment, now, decision="PENDING")
            self.pending_update_cache.setdefault(key, []).append((commitment, receipt))
            return ProcessResult(
                ResultCode.PENDING_UPDATE,
                "parent commitment has not arrived yet",
                receipt=receipt,
            )

        return ProcessResult(
            ResultCode.INVALID_UPDATE,
            "sequence jump is invalid",
        )

    def process_gossip(
        self,
        commitment: Commitment | None,
        witness_receipt: WitnessReceipt | None,
        witness_public_key: bytes | None,
    ) -> ProcessResult:
        if commitment is None or witness_receipt is None:
            return ProcessResult(
                ResultCode.UNVERIFIED_GOSSIP,
                "gossip payload is incomplete",
            )

        witness_public_key = self.witness_public_keys.get(witness_receipt.witness_id)
        if witness_public_key is None:
            return ProcessResult(
                ResultCode.UNVERIFIED_GOSSIP,
                "unknown witness public key",
            )

        message = RECEIPT_DOMAIN + canonical_json_bytes(witness_receipt.unsigned_dict())
        if not self.witness_signer.verify(
            message,
            witness_receipt.signature,
            witness_public_key,
        ):
            return ProcessResult(
                ResultCode.UNVERIFIED_GOSSIP,
                "receipt signature verification failed",
            )

        if witness_receipt.subject_id != commitment.subject_id:
            return ProcessResult(
                ResultCode.UNVERIFIED_GOSSIP,
                "receipt subject does not match the commitment",
            )
        if witness_receipt.session_id != commitment.session_id:
            return ProcessResult(
                ResultCode.UNVERIFIED_GOSSIP,
                "receipt session does not match the commitment",
            )
        if witness_receipt.epoch != commitment.epoch:
            return ProcessResult(
                ResultCode.UNVERIFIED_GOSSIP,
                "receipt epoch does not match the commitment",
            )
        if witness_receipt.sequence != commitment.sequence:
            return ProcessResult(
                ResultCode.UNVERIFIED_GOSSIP,
                "receipt sequence does not match the commitment",
            )
        if witness_receipt.merkle_root != commitment.merkle_root:
            return ProcessResult(
                ResultCode.UNVERIFIED_GOSSIP,
                "receipt Merkle root does not match the commitment",
            )
        if witness_receipt.commitment_digest != commitment_digest_hex(commitment):
            return ProcessResult(
                ResultCode.UNVERIFIED_GOSSIP,
                "receipt commitment digest does not match the commitment",
            )

        if not self._verify_subject_signature(commitment):
            return ProcessResult(
                ResultCode.UNVERIFIED_GOSSIP,
                "commitment signature verification failed",
            )

        key = commitment.consistency_key
        root_map = self.observation_cache.get(key, {})

        if commitment.merkle_root in root_map:
            receipt = root_map[commitment.merkle_root][0]
            return ProcessResult(
                ResultCode.DUPLICATE,
                "same consistency key and same Merkle root",
                receipt=receipt,
            )

        if root_map:
            existing_root = next(iter(root_map))
            existing_receipt = root_map[existing_root][0]
            existing_same_key = self.commits_by_digest.get(existing_receipt.commitment_digest)
            if existing_same_key is not None:
                now = self.now_ms()
                new_receipt = self._make_receipt(
                    commitment,
                    now,
                    decision="OBSERVED_CONFLICT",
                )
                self._store_commitment(commitment, new_receipt, now, update_active_head=False)
                evidence = EvidenceBundle(
                    commitment_a=existing_same_key,
                    commitment_b=commitment,
                    witness_id=self.witness_id,
                    detected_at_ms=now,
                    receipt_a=existing_receipt,
                    receipt_b=new_receipt,
                )
                self.evidence_store.append(evidence)
                return ProcessResult(
                    ResultCode.CONFLICT,
                    "same consistency key but different validly signed Merkle roots",
                    receipt=new_receipt,
                    evidence=evidence,
                )

        receipt = self._make_receipt(commitment, self.now_ms(), decision=witness_receipt.decision)
        self._store_commitment(commitment, receipt, self.now_ms())
        self._resolve_pending_updates(commitment, self.now_ms())
        return ProcessResult(
            ResultCode.ACCEPT,
            "gossip verification succeeded",
            receipt=receipt,
        )
