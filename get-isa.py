#!/usr/local/bin/python3
#
import sys

import gtirb

argnum = len(sys.argv) - 1
if argnum < 1:
    print("no filename.")
    quit()

filename = sys.argv[1]

try:
    ir = gtirb.IR.load_protobuf(filename)
except Exception as inst:
    print(inst)
    print("Unable to load %s." % filename)
    quit()

module = next(iter(ir.modules))
if module.isa == gtirb.Module.ISA.X64:
    print("x64")
elif module.isa == gtirb.Module.ISA.IA32:
    print("x86")
elif module.isa == gtirb.Module.ISA.ARM:
    print("arm")
elif module.isa == gtirb.Module.ISA.MIPS32:
    print("mips")
elif module.isa == gtirb.Module.ISA.PPC32:
    print("ppc")
elif module.isa == gtirb.Module.ISA.ARM64:
    print("arm64")
elif module.isa == gtirb.Module.ISA.MIPS64:
    print("mips64")
elif module.isa == gtirb.Module.ISA.PPC64:
    print("ppc64")
else:
    print("unkown")
