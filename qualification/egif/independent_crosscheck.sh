#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
Q="$ROOT/qualification/egif"
V="$Q/vectors"
OUT="$Q/evidence/independent"
WORK="$Q/.work"
rm -rf "$OUT" "$WORK"
mkdir -p "$OUT/cogitant" "$OUT/amine" "$WORK"

python3 - "$V/manifest.json" "$V" <<'PY'
import hashlib,json,sys,pathlib
m=json.load(open(sys.argv[1],encoding='utf-8')); root=pathlib.Path(sys.argv[2])
for v in m['vectors']:
    p=root/v['file']; got=hashlib.sha256(p.read_bytes()).hexdigest()
    if got!=v['sha256']: raise SystemExit(f"{v['id']}: vector sha mismatch {got} != {v['sha256']}")
print(f"PASS frozen vector hashes: {len(m['vectors'])}")
PY

# Cogitant 5.3.2
COG_ARCHIVE="$WORK/cogitant-5.3.2.tar.gz"
curl -fL --retry 4 --retry-delay 2 https://downloads.sourceforge.net/project/cogitant/cogitant/5.3.2/cogitant-5.3.2.tar.gz -o "$COG_ARCHIVE"
echo "a89abf373a898f4466d2d041d65548d284c950686b080559634ec8f27fa59968  $COG_ARCHIVE" | sha256sum -c -
mkdir "$WORK/cogitant"
tar -xzf "$COG_ARCHIVE" -C "$WORK/cogitant" --strip-components=1
cmake -S "$WORK/cogitant" -B "$WORK/cogitant/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF >/dev/null
cmake --build "$WORK/cogitant/build" --target cogitant -j2 >/dev/null
g++ -std=c++11 -O2 -I"$WORK/cogitant/include" -I"$WORK/cogitant/build/include" \
  "$WORK/cogitant/samples/converter/converter.cpp" "$WORK/cogitant/build/src/libcogitant.a" -o "$WORK/cogitant-converter"

python3 - "$V/manifest.json" "$V" "$OUT/cogitant" "$WORK/cogitant-converter" <<'PY'
import json,subprocess,sys,pathlib,tempfile
manifest=json.load(open(sys.argv[1],encoding='utf-8')); root=pathlib.Path(sys.argv[2]); out=pathlib.Path(sys.argv[3]); conv=sys.argv[4]
rows=[]
for v in manifest['vectors']:
    p=root/v['file']
    pr=subprocess.run([conv,'-at','-ai','-gi',str(p)],capture_output=True,text=True)
    row={'id':v['id'],'parse_exit_code':pr.returncode,'parse_stdout':pr.stdout,'parse_stderr':pr.stderr}
    if pr.returncode==0:
        row['parse']='accept'
        with tempfile.TemporaryDirectory() as td:
            o=pathlib.Path(td)/'a.cgif'
            wr=subprocess.run([conv,'-at','-ai','-gi',str(p),'-vo','3','-go',str(o)],capture_output=True,text=True)
            row['writer_exit_code']=wr.returncode; row['writer_stderr']=wr.stderr
            if wr.returncode < 0: row['preservation']='writer_crash'
            elif wr.returncode != 0 or not o.exists(): row['preservation']='writer_reject'
            else:
                first=o.read_text(errors='replace'); o2=pathlib.Path(td)/'b.cgif'
                wr2=subprocess.run([conv,'-at','-ai','-gi',str(o),'-vo','3','-go',str(o2)],capture_output=True,text=True)
                if wr2.returncode < 0: row['preservation']='second_writer_crash'
                elif wr2.returncode != 0 or not o2.exists(): row['preservation']='second_writer_reject'
                else: row['preservation']='stable_roundtrip' if ' '.join(first.split())==' '.join(o2.read_text(errors='replace').split()) else 'changed_roundtrip'
                row['generated']=first
    else: row['parse']='crash' if pr.returncode<0 else 'reject'
    rows.append(row)
(out/'receipt.json').write_text(json.dumps({'tool':'Cogitant','version':'5.3.2','results':rows},indent=2,sort_keys=True)+'\n')
for r in rows: print('COGITANT',r['id'],r['parse'],r.get('preservation','-'))
PY

# Amine 10.5
AMINE_ARCHIVE="$WORK/aminePlatform10.5.zip"
curl -fL --retry 4 --retry-delay 3 https://downloads.sourceforge.net/project/amine-platform/AminePlatform10.5/aminePlatform10.5.zip -o "$AMINE_ARCHIVE"
echo "c3fbb0ff50efa52e66744032609de7d6d068b329afa27f19322845451a597f48  $AMINE_ARCHIVE" | sha256sum -c -
mkdir "$WORK/amine"
unzip -q "$AMINE_ARCHIVE" -d "$WORK/amine"
CLASSES="$(find "$WORK/amine" -type d -path '*/build/classes' -print -quit)"
test -n "$CLASSES"
DIST="${CLASSES%/build/classes}"
CP="$CLASSES"
while IFS= read -r jar; do CP="$CP:$jar"; done < <(find "$DIST" -type f -name '*.jar' | sort)
python3 "$Q/normalize_ontology_paths.py" "$DIST/samples/ontology" "$WORK/ontology-normalized" "$OUT/amine/ontology-normalization.json"
ONTOLOGY="$WORK/ontology-normalized/ManOntology2.xml"
PROGRAM="$DIST/samples/prologPlusCG/CGPrograms/citizenExple.prlg"
HARNESS="$WORK/amine-harness"
mkdir "$HARNESS"
javac -cp "$CP" -d "$HARNESS" "$Q/AmineCgifProbe.java"

python3 - "$V/manifest.json" "$V" "$OUT/amine" "$HARNESS:$CP" "$ONTOLOGY" "$PROGRAM" <<'PY'
import json,subprocess,sys,pathlib,os
manifest=json.load(open(sys.argv[1],encoding='utf-8')); root=pathlib.Path(sys.argv[2]); out=pathlib.Path(sys.argv[3]); cp=sys.argv[4]; ontology=sys.argv[5]; program=sys.argv[6]
rows=[]
for v in manifest['vectors']:
    cmd=['xvfb-run','-a','java','-cp',cp,'AmineCgifProbe',ontology,program,str(root/v['file']),v['amine_seed']]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
    row={'id':v['id'],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    if p.returncode==0:
        row['parse']='accept'
        marker=next((ln.split('=',1)[1] for ln in p.stdout.splitlines() if ln.startswith('PRESERVATION=')), 'not_checked')
        row['preservation']=marker
    elif p.returncode==2: row['parse']='reject'
    else: row['parse']='crash'
    rows.append(row)
(out/'receipt.json').write_text(json.dumps({'tool':'Amine','version':'10.5','results':rows},indent=2,sort_keys=True)+'\n')
for r in rows: print('AMINE',r['id'],r['parse'],r.get('preservation','-'))
PY

python3 - "$V/manifest.json" "$OUT/cogitant/receipt.json" "$OUT/amine/receipt.json" "$OUT/receipt.json" <<'PY'
import hashlib,json,sys
manifest=json.load(open(sys.argv[1],encoding='utf-8')); cog=json.load(open(sys.argv[2])); am=json.load(open(sys.argv[3]))
tools={'Cogitant':{r['id']:r for r in cog['results']},'Amine':{r['id']:r for r in am['results']}}
rows=[]; failures=[]
for v in manifest['vectors']:
    entry={'id':v['id'],'source_egif':v['source_egif'],'canonical_cgif_sha256':v['sha256'],'tools':{}}
    for name,data in tools.items():
        r=data[v['id']]; entry['tools'][name]={'parse':r['parse'],'preservation':r.get('preservation')}
        if r['parse'] not in {'accept','reject'}: failures.append(f"{v['id']}/{name}: {r['parse']}")
        if r['parse']=='accept' and not r.get('preservation'): failures.append(f"{v['id']}/{name}: accepted without preservation observation")
    rows.append(entry)
receipt={'schema_version':1,'claim_boundary':'independent CGIF implementation behavior on frozen EGIF-origin vectors; not EGIF semantic authority or ISO conformance','vectors':rows,'failures':failures}
data=json.dumps(receipt,indent=2,sort_keys=True)+'\n'
open(sys.argv[4],'w').write(data)
open(sys.argv[4]+'.sha256','w').write(hashlib.sha256(data.encode()).hexdigest()+'  receipt.json\n')
if failures:
    print('\n'.join('FAIL '+x for x in failures),file=sys.stderr); raise SystemExit(1)
print("INDEPENDENT_CGIF_CROSSCHECK=PASS")
for row in rows: print(row['id'],row['tools'])
PY
