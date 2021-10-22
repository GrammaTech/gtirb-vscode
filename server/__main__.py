# -*- coding: utf-8 -*- 

import logging
import argparse
from .server import gtirb_server

DEFAULT_PORT = 3036
DEFAULT_TCP_FLAG = True
DEFAULT_STDIO_FLAG = False

def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tcp",
        action="store_true",
        default=DEFAULT_TCP_FLAG,
        help="Run server in TCP mode.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Port to listen for requests on.",
    )
    # (see pygls example)
    parser.add_argument(
        "--stdio",
        action="store_true",
        default=DEFAULT_STDIO_FLAG,
        help="Run server in STDIO mode.",
    )

    args = parser.parse_args()
    logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
    gtirb_server(port = args.port)

if __name__ == "__main__":
    main()
