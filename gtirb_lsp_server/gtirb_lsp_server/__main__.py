# -*- coding: utf-8 -*-

import argparse
import logging

from .server import gtirb_stdio_server, gtirb_tcp_server

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
    logging_setup = False

    if args.verbose:
        logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
        logging_setup = True

    if args.very_verbose:
        logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)
        logging_setup = True

    if not logging_setup:
        logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.WARN)

    if args.tcp:
        gtirb_tcp_server(host=args.host, port=args.port)
    else:
        gtirb_stdio_server()


if __name__ == "__main__":
    main()
