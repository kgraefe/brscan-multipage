#!/usr/bin/env bash

set -eux

# Install scanner
brsaneconfig4 -a name="Brother" model="$SCANNER_MODEL" ip="$SCANNER_IP"
#
# Ensure /output is available 
mkdir -p /output

if [ "$(id -u)" != 0 ]; then
    # running in a rootless container, don't bother with permissions.
    # Note: exec does not return.
    exec "$@"
fi

# Map user / group ID
map_uidgid() {
    local -r usermap_original_uid=$(id -u brscan)
    local -r usermap_original_gid=$(id -g brscan)
    local -r usermap_new_uid=${USERMAP_UID:-$usermap_original_uid}
    local -r usermap_new_gid=${USERMAP_GID:-${usermap_original_gid:-$usermap_new_uid}}
    if [[ ${usermap_new_uid} != "${usermap_original_uid}" || ${usermap_new_gid} != "${usermap_original_gid}" ]]; then
        echo "Mapping UID and GID for brscan:brscan to $usermap_new_uid:$usermap_new_gid"
        usermod -o -u "${usermap_new_uid}" brscan
        groupmod -o -g "${usermap_new_gid}" brscan
    fi
}
map_uidgid

# Ensure /output is available and writeable
mkdir -p /output
chown "brscan:brscan" /output

# Drop root and run CMD
exec gosu brscan:brscan "$@"
