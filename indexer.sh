#!/usr/bin/env bash
#
if [[ $# -gt 0 ]]; then
	GTIRB_FILE=$1
	echo "GTIRB file: ${GTIRB_FILE}"
	ISA=`./get-isa.py ${GTIRB_FILE}`
	if [[ "${ISA}" == "x86" || "${ISA}" == "x64" || "${ISA}" == "mips" || "${ISA}" == "arm" ]]; then
		ASM_FILE=${GTIRB_FILE}.gt${ISA}
		echo "creating asm file ${ASM_FILE}"
		echo "ISA: ${ISA}"
		gtirb-pprinter --ir ${GTIRB_FILE} --asm ${ASM_FILE} 
	else
		echo "BAD ISA: ${ISA}"
	fi
		
	#touch ${ASM_FILE}
else
	echo "no file?"
fi
