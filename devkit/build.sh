#!/bin/bash
# build.sh <prefix> <frame-folder-name e.g. dokcake@mk1> [s4ref] [s5ref] [s6ref] [s7ref]
# 필요: $SK = desktop-pet-maker 스킬 scripts 폴더 (make_frames.py, rope_meta.py, contact_sheet.py)
#       $W  = 작업 폴더 (sheets/<prefix>_s1..s7.png 가 있어야 함), NAME = 한글 표시 이름
P=$1; O=$2; R4=${3:-7@0.8}; R5=${4:-5@0.88}; R6=${5:-1}; R7=${6:-5}
D=$W/chars/$O; rm -rf $D; mkdir -p $W/check
cd $SK
OUT=$D python3 make_frames.py $W/sheets/${P}_s1.png 4x2 0 $W/sheets/${P}_s2.png 4x3 4 $W/sheets/${P}_s3.png 4x3 9 $W/sheets/${P}_s4.png 4x3 $R4 $W/sheets/${P}_s5.png 4x2 $R5 $W/sheets/${P}_s6.png 4x2 $R6 $W/sheets/${P}_s7.png 4x2 $R7 2>&1 | tail -1
python3 $W/devkit/despill.py $D >/dev/null
printf '%s' "$NAME" > $D/name.txt
python3 rope_meta.py $D >/dev/null
python3 contact_sheet.py $D $W/check/${P}_all.png >/dev/null
ls $D | wc -l
