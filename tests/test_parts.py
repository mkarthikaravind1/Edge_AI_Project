from edgevision.decide.parts import PartTracker


def feed(tr, seq):
    out = []
    for present, verdict, trig in seq:
        p = tr.update(present, {"verdict": verdict, "reasons": []} if verdict else None, trig)
        if p:
            out.append(p)
    return out


def test_good_part_passes_and_bad_part_fails() -> None:
    tr = PartTracker(gap=3, min_frames=2)
    seq = [(True, "PASS", False)] * 5 + [(False, None, False)] * 3          # good part
    seq += [(True, "FAIL", False)] * 2 + [(True, "FAIL", True)] + [(False, None, False)] * 3   # defective, reject fired
    parts = feed(tr, seq)
    assert [p.result for p in parts] == ["PASS", "FAIL"] and parts[1].rejected


def test_glitch_is_not_a_part_and_gap_bridges_short_occlusion() -> None:
    tr = PartTracker(gap=3, min_frames=2)
    assert feed(tr, [(True, "PASS", False)] + [(False, None, False)] * 3) == []      # 1-frame glitch
    seq = [(True, "PASS", False)] * 3 + [(False, None, False)] * 2 + [(True, "PASS", False)] * 3 + [(False, None, False)] * 3
    parts = feed(tr, seq)
    assert len(parts) == 1 and parts[0].frames == 6                                   # hand blocked it for 2 frames
