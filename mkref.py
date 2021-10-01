#!/usr/bin/python3
# 
import os
import sys
import gtirb
import json
from collections import defaultdict

argnum = len(sys.argv) - 1
if argnum < 1:
    print("no filename.")
    print("\nUsage: %s configfile\n" % sys.argv[0])
    quit()

#configfile = sys.argv[1]
asmfile = sys.argv[1]
gtirbfile = os.path.splitext(asmfile)[0];
xreffile = asmfile+'.json' 

##
## read configuration file
##
#gtirbfile = ""
#asmfile = ""
#xreffile = ""
#try:
#    with open(configfile, "r") as config:
#        for line in config:
#            token = ""
#            value = ""
#            split_line = line.split(":")
#            if len(split_line) > 1:
#                token = split_line[0].strip()
#                value = split_line[1].strip()
#                if token == "gtirb":
#                    gtirbfile = value
#                elif token == "asm":
#                    asmfile = value
#                elif token == "xref":
#                    xreffile = value
#except Exception as inst:
#    print(inst)
#    print("Unable to load config file %s." % configfile)
#    quit()
print ("GTIRB file:            %s" % gtirbfile)
print ("Assembly file:         %s" % asmfile)
print ("Cross reference file:  %s" % xreffile)

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
try:
    with open(asmfile, "r") as f:
        for i, line in enumerate(f):
            for word in line.strip().split():
                if word in symlist:
                    #print("found reference to %s at line %d" % (word, i))
                    refs[word].append(i)
except Exception as inst:
    print(inst)
    print("Unable to load assembly file %s." % asmfile)
    quit()

#for key in refs:
#    line = f"{key} {' '.join(map(str,refs[key]))}"
#    print(line)

x = {
    "gtirb": gtirbfile,
    "asm": asmfile,
    "xref": refs
}
#print(json.dumps(x))
try:
    with open(xreffile, "w") as out:
        json.dump(x, out, indent=4)
except Exception as inst:
    print(inst)
    print("Unable to write cross-reference file %s." % xreffile)
    quit()
print("\nWrote cross reference file: %s.\n" % xreffile)
