#!/usr/bin/env python3
"""Bounded EGIF/CGIF qualification for Arisbe.

This is implementation behavior, not ISO/IEC 24707 conformance and not an
independent authority for EGIF semantics.  It deliberately keeps parser
acceptance, canonical fixed-point behavior, and known information-loss controls
as separate observations.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from canonical_signature import compute_canonical_signatures
from cgif_generator_dau import generate_cgif
from cgif_parser_dau import CGIFParser
from egif_generator_dau import generate_egif
from egif_parser_dau import EGIFParser, parse_egif

OUT = ROOT / "qualification" / "egif" / "evidence"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_cgif(text: str):
    return CGIFParser(text).parse()


def fingerprint(graph):
    vertex, edge, cut = compute_canonical_signatures(graph)
    return {
        "vertices": sorted(repr(v) for v in vertex.values()),
        "edges": sorted(repr(v) for v in edge.values()),
        "cuts": sorted(repr(v) for v in cut.values()),
        "relation_names": sorted(graph.rel.values()),
        "vertex_count": len(graph.V),
        "edge_count": len(graph.E),
        "cut_count": len(graph.Cut),
    }


def surfaces(graph):
    return {"egif": generate_egif(graph), "cgif": generate_cgif(graph)}


def qualify_egif_parser():
    positive = {
        "relation-variable": "(human *x)",
        "cut": "~[(human *x)]",
        "constant": '(human "Socrates")',
        "identity": "(human *x) (mortal x)",
    }
    negative = {
        "unclosed-relation": "(human *x",
        "unclosed-cut": "~[(human *x)",
        "undefined-bound": "(human x)",
        "duplicate-definition": "(human *x) (mortal *x)",
    }
    rows = []
    for name, text in positive.items():
        g0 = EGIFParser(text).parse()
        generated = generate_egif(g0)
        g1 = EGIFParser(generated).parse()
        fp0, fp1 = fingerprint(g0), fingerprint(g1)
        assert fp0 == fp1, (name, generated, fp0, fp1)
        rows.append({
            "name": name, "expected": "accept", "outcome": "accept",
            "generated": generated, "fingerprint": fp0,
        })
    for name, text in negative.items():
        try:
            EGIFParser(text).parse()
        except Exception as exc:
            rows.append({
                "name": name, "expected": "reject", "outcome": "reject",
                "error": f"{type(exc).__name__}: {exc}",
            })
        else:
            raise AssertionError(f"{name}: malformed EGIF unexpectedly accepted")
    return rows


def bridge_case(name: str, source_format: str, source: str, expected_counts: tuple[int,int,int]):
    g0 = parse_egif(source) if source_format == "egif" else parse_cgif(source)
    s0 = surfaces(g0)
    fp0 = fingerprint(g0)
    observed = (fp0["vertex_count"], fp0["edge_count"], fp0["cut_count"])
    assert observed == expected_counts, (name, observed, expected_counts)

    if source_format == "egif":
        crossed = parse_cgif(s0["cgif"])
        crossed_via = "cgif"
    else:
        crossed = parse_egif(s0["egif"])
        crossed_via = "egif"
    s1 = surfaces(crossed)
    fp1 = fingerprint(crossed)
    assert fp1["vertex_count"] == expected_counts[0]
    assert fp1["edge_count"] == expected_counts[1]
    assert fp1["cut_count"] == expected_counts[2]
    assert s1 == s0, (name, s0, s1)

    fixed = parse_egif(s1["egif"]) if source_format == "egif" else parse_cgif(s1["cgif"])
    assert surfaces(fixed) == s0
    return {
        "name": name,
        "source_format": source_format,
        "source": source,
        "crossed_via": crossed_via,
        "canonical_fixed_point": True,
        "canonical_egif": s0["egif"],
        "canonical_cgif": s0["cgif"],
        "canonical_cgif_sha256": sha256_text(s0["cgif"]),
        "fingerprint": fp0,
    }


def qualify_bridge():
    specs = [
        ("egif-constant","egif",'(human "Socrates")',(1,1,0)),
        ("egif-binary","egif",'(loves *x "Socrates")',(2,1,0)),
        ("egif-shared-identity","egif","(human *x) (mortal x)",(1,2,0)),
        ("egif-cross-cut","egif","(human *x) ~[(mortal x)]",(1,2,1)),
        ("egif-two-boundary","egif","(human *x) ~[~[(mortal x)]]",(1,2,2)),
        ("cgif-constant","cgif","[human: Socrates]",(1,1,0)),
        ("cgif-shared-identity","cgif","[human: *x] [mortal: ?x]",(1,2,0)),
        ("cgif-binary","cgif","[*x] (loves ?x Socrates)",(2,1,0)),
        ("cgif-cross-cut","cgif","[human: *x] ~[[mortal: ?x]]",(1,2,1)),
        ("cgif-two-boundary","cgif","[human: *x] ~[~[[mortal: ?x]]]",(1,2,2)),
    ]
    return [bridge_case(*spec) for spec in specs]


def qualify_loss_controls():
    rows = []

    universal_src = "[Person: @every *x]"
    universal = parse_cgif(universal_src)
    universal_preserved = "Person" in universal.rel.values() and len(universal.V) > 0
    assert not universal_preserved
    rows.append({
        "name":"cgif-universal-not-preserved",
        "source":universal_src,
        "classification":"recognized-by-parser-grammar-but-lost-in-egi-conversion",
        "preserved":False,
        "fingerprint":fingerprint(universal),
    })

    numeral_src = "(age 42)"
    numeral = parse_cgif(numeral_src)
    fp = fingerprint(numeral)
    arity = fp["edge_count"] and len(numeral.nu.get(next(iter(numeral.E)).id, ()))
    numeral_preserved = arity == 1 and len(numeral.V) == 1
    assert not numeral_preserved
    rows.append({
        "name":"cgif-numeral-argument-not-preserved",
        "source":numeral_src,
        "classification":"recognized-by-parser-grammar-but-dropped-from-relation-egi-arguments",
        "preserved":False,
        "fingerprint":fp,
        "observed_arity":arity,
    })
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    parser = qualify_egif_parser()
    bridge = qualify_bridge()
    loss = qualify_loss_controls()
    receipt = {
        "schema_version":1,
        "generated_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repository":"phaneroscopy-society/arisbe",
        "source_commit":"c8c35eb43764fd204b72853e6d56737e053dd970",
        "normative_conformance_claim":False,
        "egif_parser_cases":parser,
        "bridge_cases":bridge,
        "loss_controls":loss,
        "claim":"bounded Arisbe implementation qualification for EGIF parsing and a shared-EGI EGIF<->CGIF first-order slice",
    }
    receipt_path = OUT / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    (OUT / "receipt.sha256").write_text(
        hashlib.sha256(receipt_path.read_bytes()).hexdigest()+"  receipt.json\n",
        encoding="utf-8",
    )
    print(f"PASS EGIF parser controls: {len(parser)}")
    print(f"PASS EGIF<->CGIF bridge cases: {len(bridge)}")
    print(f"PASS information-loss falsifiers: {len(loss)}")
    print("ARISBE_EGIF_QUALIFICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
