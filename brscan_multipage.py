#!/usr/bin/env python

import os
import asyncio
import datetime
import argparse
import colorlog
import img2pdf
import pysnmp.hlapi.v1arch.asyncio as snmp

SNMP_UDP_PORT: int = 161
COMMAND_UDP_PORT: int = 54925  # Brother expects this and nothing else
ADVERTISE_INTERVAL: int = 30
RESOLUTION: int = 200

log = colorlog.getLogger("brscan_multipage")


class Scanner:
    def __init__(self, output_dir: str | os.PathLike, device: str | None):
        self._queue = asyncio.Queue(maxsize=10)
        self._pages = []
        self._output_dir = output_dir
        self._device = device

    def enqueue(self, appnum: int):
        try:
            self._queue.put_nowait(appnum)
        except asyncio.QueueFull as e:
            self.warning(f"Dropping appnum command {appnum}: {e}")

    async def process(self):
        while True:
            appnum = await self._queue.get()

            # appnum must match the appnum in the advertisement (array index + 1)
            match appnum:
                case 1:
                    log.info("Scanning multi page")
                    await self._scan_multipage()
                case 2:
                    log.info("Scanning last page")
                    await self._scan_last_page()
                case 3:
                    log.info("Finishing multi page")
                    await self._finish_multipage()
                case 4:
                    log.info("Aborting multi page")
                    await self._abort_multipage()
                case _:
                    log.warning(f"Ignoring unknown appnum {appnum}")

    async def _scan_page(self, dummy: bool = False, retry: bool = False):
        # scanimage failed on my Brother DCP-7070DW when invoking it too fast
        # after receiving the first event. Hence we need to add a little sleep
        # here. Maybe we could wait for the second event but that defeats the
        # purpose of sending it twice (in case one is lost). In my observation
        # 1 second were sufficient most of the time but sometimes not.
        # Therefore we retry once on failure.
        if not retry:
            await asyncio.sleep(1)

        # fmt: off
        cmd = [
            "scanimage",
            "--resolution", f"{RESOLUTION}",
            "-x", "1" if dummy else "210",
            "-y", "1" if dummy else "297",
            "--format", "jpeg",
        ]
        # fmt: on

        if self._device is not None:
            cmd += ["--device", self._device]

        log.debug("Run " + " ".join(cmd))
        scanimage = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await scanimage.communicate()

        if scanimage.returncode != 0:
            stderr = stderr.decode(errors="replace").strip()
            if retry:
                log.error(f"scanimage failed with {scanimage.returncode}: {stderr}")
            else:
                log.warning(f"Retrying as scanimage failed with {scanimage.returncode}: {stderr}")
                await self._scan_page(dummy, retry=True)
        else:
            self._pages.append(stdout)

    def _save_document(self):
        filename = f"SCAN_{datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S')}.pdf"
        log.info(f"Saving {len(self._pages)} pages to {filename}")
        with open(os.path.join(self._output_dir, filename), "wb") as f:
            f.write(img2pdf.convert(self._pages))
        self._pages = []

    async def _scan_last_page(self):
        await self._scan_page()
        self._save_document()

    async def _scan_multipage(self):
        await self._scan_page()
        log.info(f"Buffered {len(self._pages)} pages")

    async def _finish_multipage(self):
        # when the device sends us an event it expects us to do some scanning.
        # otherwise it won't clear the display for quite some time.
        await self._scan_page(dummy=True)
        self._save_document()

    async def _abort_multipage(self):
        # when the device sends us an event it expects us to do some scanning.
        # otherwise it won't clear the display for quite some time.
        await self._scan_page(dummy=True)
        log.info(f"Discarding {len(self._pages)} pages")
        self._pages = []


class ScannerProtocol(asyncio.DatagramProtocol):
    def __init__(self, scanner: Scanner):
        asyncio.DatagramProtocol.__init__(self)
        self._scanner = scanner
        self._last_seq = None

    def datagram_received(self, data, addr):
        if len(data) < 4 or data[0] != 2 or data[1] != 0 or data[3] != 0x30:
            log.warning("dropping unknown UDP data")
            return None
        msg = data[4:].decode("utf-8")

        log.debug(f"Received UDP packet: {msg}")

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
            log.warning("dropping UDP packet with no or invalid SEQ")
            return None
        if seq == self._last_seq:
            # the printer sends everything twice, silently discard duplicates
            log.debug("dropping UDP packet with duplicated SEQ")
            return None
        self._last_seq = seq

        if appnum is None or appnum < 1 or appnum > 4:
            log.warning("dropping UDP packet with no or invalid APPNUM")
            return None

        self._scanner.enqueue(appnum)


async def advertise(scanner_addr: str, host: str):
    dispatcher = snmp.SnmpDispatcher()

    try:
        while True:
            log.info(f"Sending advertisements to {scanner_addr}")

            for idx, function in enumerate(
                [
                    "Multipage",
                    "Last page",
                    "Finish MP",
                    "Abort MP",
                ]
            ):
                appnum = idx + 1
                cmdstr = ";".join(
                    [
                        "TYPE=BR",
                        "BUTTON=SCAN",
                        # prepend app number as the menu sorts alphabetically
                        f"USER={appnum} {function}",
                        "FUNC=FILE",
                        f"HOST={host}:{COMMAND_UDP_PORT}",
                        f"APPNUM={appnum}",
                        f"DURATION={ADVERTISE_INTERVAL * 3}",
                        "BRID=",
                    ]
                )

                log.debug(f"cmdstr: {cmdstr}")

                error_indication, error_status, error_index, var_binds = (
                    await snmp.set_cmd(
                        dispatcher,
                        snmp.CommunityData("internal", mpModel=0),
                        await snmp.UdpTransportTarget.create(
                            (scanner_addr, SNMP_UDP_PORT)
                        ),
                        (
                            # See http://www.oidview.com/mibs/2435/BROTHER-MIB.html
                            "1.3.6.1.4.1.2435.2.3.9.2.11.1.1.0",
                            snmp.OctetString(cmdstr),
                        ),
                    )
                )
                if error_indication:
                    log.error(f"SNMP SET failed: {error_indication}")
                elif error_status:
                    location = error_index and var_binds[int(error_index) - 1] or "?"
                    log.error(
                        f"SNMP SET failed: {error_status.prettyPrint()} at {location}"
                    )

            await asyncio.sleep(ADVERTISE_INTERVAL)
    finally:
        dispatcher.transport_dispatcher.close_dispatcher()


async def main(args: argparse.Namespace):
    scanner = Scanner(args.output_dir, args.device)
    try:
        await asyncio.gather(
            scanner.process(),
            asyncio.get_event_loop().create_datagram_endpoint(
                lambda: ScannerProtocol(scanner),
                local_addr=(args.listen_addr, COMMAND_UDP_PORT),
            ),
            advertise(args.scanner_addr, host=args.advertised_host or args.listen_addr),
        )
    except asyncio.exceptions.CancelledError:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="brscan with multipage support")
    parser.add_argument(
        "-l",
        "--loglevel",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="logging level",
    )
    parser.add_argument("-d", "--device", type=str, help="scanner device")
    parser.add_argument(
        "-a",
        "--advertised-host",
        type=str,
        help="""
            Host IP address that should be advertised to the scanner. This defaults to
            listen_addr but might be different in NATed or containered environments.
    """,
    )
    parser.add_argument(
        "scanner_addr", type=str, help="IP address or DNS entry of printer"
    )
    parser.add_argument("listen_addr", type=str, help="local IP address or DNS entry")
    parser.add_argument("output_dir", type=str, help="output directory")
    args = parser.parse_args()

    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(light_black)s%(asctime)s "
            "%(blue)s%(name)s[%(process)d] "
            "%(log_color)s%(levelname)-8s "
            "%(message)s%(reset)s"
        )
    )

    log.setLevel(args.loglevel.upper())
    log.addHandler(handler)

    asyncio.run(main(args))
