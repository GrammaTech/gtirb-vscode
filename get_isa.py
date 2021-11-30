#!/usr/bin/python3
#
import sys
import gtirb


def infer_isa(filename):
    ir = gtirb.IR.load_protobuf(filename)

    module = next(iter(ir.modules))
    if module.isa == gtirb.Module.ISA.X64:
        return "x64"
    elif module.isa == gtirb.Module.ISA.IA32:
        return "x86"
    elif module.isa == gtirb.Module.ISA.ARM:
        return "arm"
    elif module.isa == gtirb.Module.ISA.MIPS32:
        return "mips"
    elif module.isa == gtirb.Module.ISA.PPC32:
        return "ppc"
    elif module.isa == gtirb.Module.ISA.ARM64:
        return "arm64"
    elif module.isa == gtirb.Module.ISA.MIPS64:
        return "mips64"
    elif module.isa == gtirb.Module.ISA.PPC64:
        return "ppc64"
    else:
        return "unkown"


if __name__ == "__main__":
    argnum = len(sys.argv) - 1
    if argnum < 1:
        print("no filename.")
        quit()
    filename = sys.argv[1]
    isa = "unknown"
    try:
        isa = infer_isa(filename)
    except Exception as inst:
        print(inst)
        print("Unable to load %s." % filename)
        quit()
    print(isa)
