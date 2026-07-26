from wtc.merkle import MerkleTree
from wtc.models import TrajectoryEnvelope


def item(index: int) -> TrajectoryEnvelope:
    return TrajectoryEnvelope(
        segment_index=index,
        t_start_ms=index * 100,
        t_end_ms=(index + 1) * 100,
        road_id="R",
        lane_id="1",
        pos_min_mm=index * 1000,
        pos_max_mm=index * 1000 + 100,
        v_min_mmps=1000,
        v_max_mmps=2000,
        a_min_mmps2=-100,
        a_max_mmps2=100,
        behavior_code="KEEP",
    )


def test_merkle_proof_accepts_original_leaf():
    items = [item(i) for i in range(5)]
    tree = MerkleTree(items)
    proof = tree.proof(3)
    assert MerkleTree.verify(items[3], proof, tree.root_hex)


def test_merkle_proof_rejects_modified_leaf():
    items = [item(i) for i in range(5)]
    tree = MerkleTree(items)
    proof = tree.proof(3)
    modified = TrajectoryEnvelope(
        **{
            **items[3].__dict__,
            "lane_id": "2",
        }
    )
    assert not MerkleTree.verify(modified, proof, tree.root_hex)
