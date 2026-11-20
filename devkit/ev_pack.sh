#!/bin/bash
# ev_pack.sh <name> <id...> → /mnt/user-data/uploads/ev_<name>.zip + ev_done.txt 갱신
N=$1; shift; W=/home/claude/pet
cd $W/chars_ev && rm -f /tmp/ev_$N.zip && zip -qr /tmp/ev_$N.zip $(for i in "$@"; do echo chars/$i; done) && cp /tmp/ev_$N.zip /mnt/user-data/uploads/ev_$N.zip
for i in "$@"; do grep -q "^$i	" $W/devkit/ev_done.txt || printf "%s\txmas hanbok halloween valentine\t%s\n" "$i" "$(date +%F)" >> $W/devkit/ev_done.txt; done
mkdir -p /mnt/user-data/uploads/devkit_ev && cp $W/devkit/ev_done.txt /mnt/user-data/uploads/devkit_ev/ev_done.txt
ls -la /tmp/ev_$N.zip | awk '{print $5}'; wc -l < $W/devkit/ev_done.txt
