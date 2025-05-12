#!/usr/bin/env python

import asyncio
import argparse
import colorlog

SNMP_UDP_PORT = 161
COMMAND_UDP_PORT = 54925  # Brother expects this and nothing else
ADVERTISE_INTERVAL = 30
RESOLUTION = 200
RETRIES = 2

log = colorlog.getLogger("brscan_multipage")


async def main(args):
    log.info("Hello world")


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
