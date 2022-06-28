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
import sys
import gtirb
from pathlib import Path
import subprocess

DEBUG = False

SUPPORTED_ISA = ["ia32", "x64", "mips32", "mips64", "arm"]


def get_isa(filename):
    ir = gtirb.IR.load_protobuf(filename)
    module = next(iter(ir.modules))
    return str(module.isa).lower().split(".")[1]


def index_gtirb(filepath):
    isa = get_isa(filepath)

    if isa in SUPPORTED_ISA:
        gtirb_file = Path(filepath)
        gtirb_dir = gtirb_file.parent
        cache_dir = gtirb_dir.joinpath(f".vscode.{gtirb_file.name}")
        gtirb_base = gtirb_file.stem
        isa_dir = cache_dir.joinpath(isa)
        asm_file = isa_dir.joinpath(f"{gtirb_base}.view")

        if DEBUG:
            lines = [
                f"GTIRB file path: {filepath}\n",
                f"GTIRB_FOLDER: {gtirb_dir}\n",
                f"GTIRB_FILE: {gtirb_file.name}\n",
                f"CACHE_PATH: {cache_dir}\n",
                f"ISA_DIR: {isa_dir}\n",
                f"ASM_FILE: {asm_file}\n",
            ]
            sys.stdout.writelines(lines)
            logpath = gtirb_dir.joinpath("log.txt")
            with logpath.open("w") as log:
                log.writelines(lines)

        if isa_dir.is_dir() and asm_file.is_file():
            print(f"Using existing assembly file {asm_file}")
            return True
        else:
            # IFF it doesn't exist, create a subdir for caching files
            if not isa_dir.is_dir():
                isa_dir.mkdir(parents=True, exist_ok=True)

            if not isa_dir.is_dir():
                print(f"Failed to create cache subdir {isa_dir}")
                return False

            subprocess.run(
                ["gtirb-pprinter", "--ir", filepath, "--asm", asm_file, "--listing-mode", "ui"],
                shell=False,
            )
            if not asm_file.is_file():
                print(f"Failed to create ASM FILE {asm_file}")
                return False
        return True

    else:
        print(f"Bad ISA: {isa}.")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"No file. Usage: {sys.argv[0]} <gtirb-file-name>")
        sys.exit(2)

    if index_gtirb(sys.argv[1]):
        sys.exit(0)
    else:
        sys.exit(1)
