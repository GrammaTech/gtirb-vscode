#!/usr/local/bin/python3
#
import json
import os
import sys
from collections import defaultdict

import gtirb

argnum = len(sys.argv) - 1
if argnum < 1:
    print("no filename.")
    print("\nUsage: %s configfile\n" % sys.argv[0])
    quit()

asmfile = sys.argv[1]
gtirbfile = os.path.splitext(asmfile)[0]
xreffile = asmfile + ".json"

print("GTIRB file:            %s" % gtirbfile)
print("Assembly file:         %s" % asmfile)
print("Cross reference file:  %s" % xreffile)

try:
    ir = gtirb.IR.load_protobuf(gtirbfile)
except Exception as inst:
    print(inst)
    print("Unable to load gtirb file %s." % gtirbfile)
    quit()

modules = ir.modules
module = next(iter(modules))
symbols = module.symbols
symlist = []
for symbol in symbols:
    symlist.append(symbol.name)

refs = defaultdict(list)
defs = {}
try:
    with open(asmfile, "r") as f:
        for i, line in enumerate(f):
            # if this is a definition, a symbol followed by a comma is the whole line
            if len(line) > 2:
                line_minus_last = line[:-2]
                if line_minus_last in symlist:
                    defs[line_minus_last] = i
                    # print("found def of %s at %d" % (line_minus_last, i))

            # parse the tokens to see if any are a symbol
            for word in line.strip().split():
                if word in symlist:
                    # print("found reference to %s at line %d" % (word, i))
                    refs[word].append(i)
except Exception as inst:
    print(inst)
    print("Unable to load assembly file %s." % asmfile)
    quit()

# for key in refs:
#    line = f"{key} {' '.join(map(str,refs[key]))}"
#    print(line)

x = {"gtirb": gtirbfile, "asm": asmfile, "xref": refs, "def": defs}
# print(json.dumps(x))
try:
    with open(xreffile, "w") as out:
        json.dump(x, out, indent=4)
except Exception as inst:
    print(inst)
    print("Unable to write cross-reference file %s." % xreffile)
    quit()
print("\nWrote cross reference file: %s.\n" % xreffile)
