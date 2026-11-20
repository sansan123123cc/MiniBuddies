#!/bin/bash
# ev_build.sh <기본폴더(예: elysia@basic)> <xmas|hanbok|halloween|valentine> [ref칸@비율]
# evsheets/<기본폴더>_<종류>.png (4x2) → chars_ev/chars/<기본폴더>/<번호>.png + meta_event.json
ID=$1; K=$2; REF=${3:-0@1.0}; [ "$K" = hanbok ] && [ -z "$3" ] && REF=2@1.0; W=/home/claude/pet; SK=$(ls -d /root/.claude/skills/synced/*/desktop-pet-maker/scripts)
case $K in xmas) OFF=130;; hanbok) OFF=138;; halloween) OFF=146;; valentine) OFF=154;; *) echo bad kind; exit 1;; esac
T=$W/tmp_ev/$ID-$K; rm -rf $T; mkdir -p $T
OUT=$T python3 $SK/make_frames.py $W/evsheets/${ID}_$K.png 4x2 $REF >/dev/null || exit 1
python3 $W/devkit/despill.py $T >/dev/null
D=$W/chars_ev/chars/$ID; mkdir -p $D
python3 - "$T" "$D" $OFF "$ID" "$K" <<'PY'
import sys, json, shutil, os
from PIL import Image
t, d, off, i, k = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
m = json.load(open(os.path.join(t, "meta.json")))["frames"]
p = os.path.join(d, "meta_event.json")
out = json.load(open(p))["frames"] if os.path.exists(p) else {}
for n in range(8):
    shutil.copy(os.path.join(t, f"{n}.png"), os.path.join(d, f"{off+n}.png")); out[str(off+n)] = m[str(n)]
json.dump({"frames": out}, open(p, "w"), indent=1)
c = Image.new('RGBA', (160*8, 160), (60, 60, 70, 255))
for n in range(8):
    c.alpha_composite(Image.open(f'{d}/{off+n}.png').convert('RGBA').resize((160, 160)), (160*n, 0))
c.convert('RGB').save(f'/home/claude/pet/check/ev_{i}_{k}.png')
print(i, k, {n: round((v['bottom']-v['top'])*256) for n, v in out.items() if off <= int(n) < off+8})
PY
