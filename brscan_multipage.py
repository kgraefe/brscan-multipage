#!/usr/bin/env python

import asyncio
import argparse
import colorlog
import pysnmp.hlapi.v1arch.asyncio as snmp

SNMP_UDP_PORT: int = 161
COMMAND_UDP_PORT: int = 54925  # Brother expects this and nothing else
ADVERTISE_INTERVAL: int = 30
RESOLUTION = 200
RETRIES = 2

log = colorlog.getLogger("brscan_multipage")


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
    try:
        await advertise(args.scanner_addr, host=args.advertised_host or args.listen_addr)
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
