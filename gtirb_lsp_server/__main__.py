# -*- coding: utf-8 -*-

import argparse
import logging

from .server import gtirb_stdio_server, gtirb_tcp_server, logger

DEFAULT_PORT = 3036
DEFAULT_HOST = "127.0.0.1"
DEFAULT_TCP_FLAG = False
DEFAULT_STDIO_FLAG = True


def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tcp", action="store_true", default=DEFAULT_TCP_FLAG, help="Run server in TCP mode.",
    )
    parser.add_argument(
        "--host", type=str, default=DEFAULT_HOST, help="Server IP addr",
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Port to listen for requests on.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose log output.")
    parser.add_argument(
        "-vv", "--very-verbose", action="store_true", help="Very verbose log output."
    )
    parser.add_argument(
        "--stdio",
        action="store_true",
        default=DEFAULT_STDIO_FLAG,
        help="Run server in STDIO mode.",
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.INFO)

    if args.very_verbose:
        logger.setLevel(logging.DEBUG)

    if args.tcp:
        gtirb_tcp_server(host=args.host, port=args.port)
    else:
        gtirb_stdio_server()


if __name__ == "__main__":
    main()
