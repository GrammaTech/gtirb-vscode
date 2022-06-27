# -*- coding: utf-8 -*-
# Copyright (C) 2022 GrammaTech, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# This project is sponsored by the Office of Naval Research, One Liberty
# Center, 875 N. Randolph Street, Arlington, VA 22203 under contract #
# N68335-17-C-0700.  The content of the information does not necessarily
# reflect the position or policy of the Government and no official
# endorsement should be inferred.

import argparse
import logging

from .server import run_gtirb_server

DEFAULT_PORT = 3036
DEFAULT_HOST = "127.0.0.1"
DEFAULT_TCP_FLAG = False
DEFAULT_STDIO_FLAG = True
DEFAULT_FORCE_REMOTE = False


def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tcp",
        action="store_true",
        default=DEFAULT_TCP_FLAG,
        help="Run server in TCP mode.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=DEFAULT_HOST,
        help="Server IP addr",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Port to listen for requests on.",
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
    parser.add_argument(
        "--force-remote",
        action="store_true",
        default=DEFAULT_FORCE_REMOTE,
        help="Assume client's filesystem is not directly accessible, even when run in STDIO mode.",
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
        run_gtirb_server("tcp", host=args.host, port=args.port)
    elif args.force_remote:
        run_gtirb_server("stdio_remote")
    else:
        run_gtirb_server("stdio")


if __name__ == "__main__":
    main()
