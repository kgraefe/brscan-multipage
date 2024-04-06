#!/bin/sh

set -x
set -u

brsaneconfig4 -a name="Brother" model="$SCANNER_MODEL" ip="$SCANNER_IP"

mkdir -p /output
python brscan_multipage.py \
    --device "brother4:net1;dev0" \
    --advertised-host "$HOST_IP" \
    "$SCANNER_IP" \
    0.0.0.0 \
    /output
