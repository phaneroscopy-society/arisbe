#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, shutil
from pathlib import Path

PATTERN = re.compile(r"(?P<prefix>/?D:[\\\\/]samples[\\\\/]ontology[\\\\/])(?P<suffix>[^<>\"'\\r\\n]+?\\.xml)", re.IGNORECASE)

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("source",type=Path); ap.add_argument("destination",type=Path); ap.add_argument("receipt",type=Path)
    a=ap.parse_args()
    src=a.source.resolve(); dst=a.destination.resolve(); rec=a.receipt.resolve()
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(src,dst)
    rows=[]; unresolved=[]
    for xml in sorted(dst.rglob("*.xml")):
        text=xml.read_text(encoding="utf-8")
        matches=list(PATTERN.finditer(text))
        if not matches: continue
        refs=[]
        for m in matches:
            suffix=m.group("suffix").replace("\\\\","/")
            target=(dst/suffix).resolve()
            refs.append({"original":m.group(0),"suffix":suffix,"target":str(target),"target_exists":target.exists()})
            if not target.exists(): unresolved.append(str(target))
        def repl(m):
            return (dst/m.group("suffix").replace("\\\\","/")).resolve().as_posix()
        out,count=PATTERN.subn(repl,text)
        xml.write_text(out,encoding="utf-8")
        rows.append({"file":str(xml.relative_to(dst)),"replacement_count":count,"references":refs})
    data={"source":str(src),"destination":str(dst),"replacement_files":rows,"unresolved_targets":unresolved}
    rec.parent.mkdir(parents=True,exist_ok=True); rec.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if unresolved: raise SystemExit("unresolved ontology targets: "+repr(unresolved))
    print(f"normalized {sum(r['replacement_count'] for r in rows)} ontology reference(s)")
    return 0
if __name__=="__main__": raise SystemExit(main())
