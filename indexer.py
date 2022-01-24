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
        asm_file = isa_dir.joinpath(f"{gtirb_base}.gtasm")

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
            print(f"Using existing assembly file ${asm_file}")
            return True
        else:
            # IFF it doesn't exist, create a subdir for caching files
            if not isa_dir.is_dir():
                isa_dir.mkdir(parents=True, exist_ok=True)

            if not isa_dir.is_dir():
                print(f"Failed to create cache subdir {isa_dir}")
                return False

            subprocess.run(
                ["gtirb-pprinter", "--ir", filepath, "--asm", asm_file, "--listing-mode", "ui"]
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
