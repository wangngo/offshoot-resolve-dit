#!/bin/bash
# Dùng: scripts/lab/mkfoot.sh /Volumes/A001/PRIVATE/M4ROOT/CLIP /Volumes/SOUND01 — rồi dot_clean -m từng ổ (exFAT sinh ._*)
# Tạo footage giả: $1 = thư mục CLIP (thẻ cam), $2 = thư mục thẻ sound
set -e
C=$1; S=$2; mkdir -p $C $S
# clip: tên, TC bắt đầu (giây từ nửa đêm), độ dài
clip() { # name start_s dur
  local n=$1 st=$2 d=$3
  local tc=$(printf "%02d:%02d:%02d:00" $((st/3600)) $((st%3600/60)) $((st%60)))
  ffmpeg -loglevel error -y -f lavfi -i "testsrc2=s=640x360:r=25:d=$d" \
    -f lavfi -i "sine=f=440:d=$d:sample_rate=48000" -f lavfi -i "aevalsrc='if(between(t,3,3.02),0.9,0)':d=$d:s=48000" \
    -filter_complex "[1]volume=0.1[a];[a][2]amix=inputs=2:normalize=0[o]" -map 0:v -map "[o]" \
    -c:v libx264 -pix_fmt yuv420p -g 25 -c:a aac -ac 1 -timecode $tc $C/$n.MP4
  echo "<NonRealTimeMeta><LtcChangeTable tcFps=\"25\"><LtcChange frameCount=\"0\" value=\"$tc\"/></LtcChangeTable></NonRealTimeMeta>" > $C/${n}M01.XML
}
# wav: tên, start_s, dur, clap_offsets(giây tuyệt đối từ nửa đêm, cách nhau dấu phẩy), bext(1/0)
wav() {
  local n=$1 st=$2 d=$3 claps=$4 bext=$5 expr="0"
  for c in ${claps//,/ }; do expr="$expr+if(between(t,$((c-st)),$((c-st)).02),0.9,0)"; done
  local args=(); [[ $bext == 1 ]] && args=(-write_bext 1 -metadata time_reference=$((st*48000)))
  ffmpeg -loglevel error -y -f lavfi -i "sine=f=1000:d=$d:sample_rate=48000" -f lavfi -i "aevalsrc='$expr':d=$d:s=48000" \
    -filter_complex "[0]volume=0.1[a];[a][1]amix=inputs=2:normalize=0" -c:a pcm_s24le -ac 1 "${args[@]}" $S/$n.WAV
}
# 10:00:00, 10:00:20, 10:00:40 — clap tại +3s
clip A001C001 36000 10; clip A001C002 36020 10; clip A001C003 36040 10
wav S001T01 35998 14 36003 1           # sớm 2s, phủ C001
wav S001T02 36018 34 36023,36043 1     # 1 WAV dài phủ C002 + C003
