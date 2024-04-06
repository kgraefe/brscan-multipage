#!/usr/bin/env python

import argparse
import datetime
import os
import time
import socket
import subprocess
import sys
from types import SimpleNamespace
import wand.image
from pysnmp.entity.rfc3413.oneliner import cmdgen
from pysnmp.proto import rfc1902

SNMP_UDP_PORT = 161
COMMAND_UDP_PORT = 54925  # Brother expects this and nothing else
ADVERTISE_INTERVAL = 30
RESOLUTION = 200
RETRIES = 2


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def scan_page(args, document, dummy=False):
    # fmt: off
    cmd = [
        "scanimage",
        "--resolution", f"{RESOLUTION}",
        "-x", "1" if dummy else "210",
        "-y", "1" if dummy else "297",
        "--format", "jpeg",
    ]
    # fmt: on

    if args.device is not None:
        cmd += ["--device", args.device]

    print("+ " + " ".join(cmd))
    scanimage = subprocess.run(cmd, capture_output=True, check=True)

    if dummy:
        return

    with wand.image.Image(blob=scanimage.stdout, resolution=RESOLUTION) as page:
        document.sequence.append(page)


def save_document(args, document):
    filename = f"SCAN_{datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S')}.pdf"
    print(f"+ Saving {len(document.sequence)} pages to {filename}")
    document.save(filename=os.path.join(args.output_dir, filename))
    document.clear()


def scan_last_page(args, document):
    scan_page(args, document)
    save_document(args, document)


def scan_multipage(args, document):
    scan_page(args, document)
    print(f"+ Buffered {len(document.sequence)} pages")


def finish_multipage(args, document):
    # when the device sends us an event it expects us to do some scanning. otherwise it won't
    # clear the display for quite some time.
    scan_page(args, document, dummy=True)
    save_document(args, document)


def abort_multipage(args, document):
    # when the device sends us an event it expects us to do some scanning. otherwise it won't
    # clear the display for quite some time.
    scan_page(args, document, dummy=True)
    print(f"+ Discarding {len(document.sequence)} pages")
    document.clear()


FUNCTIONS = [
    SimpleNamespace(name="Last page", call=scan_last_page),
    SimpleNamespace(name="Multipage", call=scan_multipage),
    SimpleNamespace(name="Finish MP", call=finish_multipage),
    SimpleNamespace(name="Abort MP", call=abort_multipage),
]


def advertise(args):
    cmd = cmdgen.CommandGenerator()
    auth = cmdgen.CommunityData("internal", mpModel=0)
    target = cmdgen.UdpTransportTarget((args.scanner_addr, SNMP_UDP_PORT))

    print(f"Sending advertisements to {args.scanner_addr}")

    for idx, function in enumerate(FUNCTIONS):
        appnum = idx + 1
        cmdstr = ";".join(
            [
                "TYPE=BR",
                "BUTTON=SCAN",
                f"USER={appnum}: {function.name}", # the menu sorts alphabetically
                "FUNC=FILE",
                f"HOST={args.listen_addr}:{COMMAND_UDP_PORT}",
                f"APPNUM={idx + 1}",
                f"DURATION={ADVERTISE_INTERVAL * 3}",
                "BRID=",
            ]
        )

        error_indication, error_status, error_index, var_binds = cmd.setCmd(
            auth,
            target,
            # See http://www.oidview.com/mibs/2435/BROTHER-MIB.html
            ("1.3.6.1.4.1.2435.2.3.9.2.11.1.1.0", rfc1902.OctetString(cmdstr)),
        )

        if error_indication:
            print(error_indication)
        elif error_status:
            location = error_index and var_binds[int(error_index) - 1] or "?"
            print(f"{error_status.prettyPrint()} at {location}")


def receive_command(sock, timeout):

    sock.settimeout(timeout)
    try:
        data, _addr = sock.recvfrom(2048)
    except socket.timeout:
        return None

    if len(data) < 4 or data[0] != 2 or data[1] != 0 or data[3] != 0x30:
        print("Warning: dropping unknown UDP data")
        return None
    msg = data[4:].decode("utf-8")

    appnum = seq = None
    for item in msg.split(";"):
        item = item.split("=", 1)
        if len(item) != 2:
            continue
        key, val = item
        if key == "APPNUM":
            appnum = int(val) if val.isdecimal() else None
        if key == "SEQ":
            seq = int(val) if val.isdecimal() else None

    if seq is None:
        print("Warning: dropping UDP packet with no or invalid SEQ")
        return None
    if seq == receive_command.last_seq:
        # the printer sends everything twice, silently discard duplicates
        return None
    receive_command.last_seq = seq

    if appnum is None or appnum < 1 or appnum >= len(FUNCTIONS) + 1:
        print("Warning: dropping UDP packet with no or invalid APPNUM")
        return None

    return FUNCTIONS[appnum - 1]


# static variable within the function
receive_command.last_seq = None


def main():
    parser = argparse.ArgumentParser(description="brscan with multipage support")
    parser.add_argument("-d", "--device", type=str, help="scanner device")
    parser.add_argument("scanner_addr", type=str, help="IP address or DNS entry of printer")
    parser.add_argument("listen_addr", type=str, help="local IP address or DNS entry")
    parser.add_argument("output_dir", type=str, help="output directory")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.listen_addr, COMMAND_UDP_PORT))

    advertise(args)
    next_ad = time.monotonic() + ADVERTISE_INTERVAL

    document = wand.image.Image()

    try:

        while True:
            if time.monotonic() >= next_ad:
                advertise(args)
                next_ad = time.monotonic() + ADVERTISE_INTERVAL

            function = receive_command(sock, max(next_ad - time.monotonic(), 0))
            if function is not None:
                print(f"Starting function '{function.name}'")

                # scanimage failed on my Brother DCP-7070DW when invoking it too fast after
                # receiving the first event. Hence we need to add a little sleep here. Maybe we
                # could wait for the second event but that defeats the purpose of sending it twice
                # (in case one is lost). 1 second was sufficient when I observed it. However, just
                # to be sure we retry on failure.
                time.sleep(1)
                for _ in range(RETRIES):
                    try:
                        function.call(args, document)
                    except subprocess.CalledProcessError as e:
                        eprint(f"Function '{function.name}' failed: {e}")
                        eprint(e.stderr.decode())
                    else:
                        break
                else:
                    eprint(f"Function '{function.name}' failed {RETRIES} times. Giving up.")

    except KeyboardInterrupt:
        pass

    sock.close()


if __name__ == "__main__":
    main()
