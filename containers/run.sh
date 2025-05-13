#!/usr/bin/env bash

set -eux

python brscan_multipage.py \
    --device "brother4:net1;dev0" \
    --advertised-host "$HOST_IP" \
    --loglevel "${LOGLEVEL:-info}" \
    "$SCANNER_IP" \
    0.0.0.0 \
    /output
