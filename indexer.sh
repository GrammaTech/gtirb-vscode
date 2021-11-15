#!/usr/bin/env bash
#
DEBUG=false
CONTINUE=true

PWD=$(dirname $(realpath $0))
if [[ $# -lt 1 ]]; then
	MESSAGE="No file. Usage: $0 <gtirb-file-name>"
	CONTINUE=false
fi

if ${CONTINUE} 
then
	FS_PATH=$1
	if [[ -f ${PWD}/get-isa.py ]]; then
		ISA=$(${PWD}/get-isa.py ${FS_PATH})
	else
		MESSAGE="${PWD}/get-isa.py script not found."
		CONTINUE=false
	fi
fi

if ${CONTINUE} 
then
	if [[ "${ISA}" == "x86" || "${ISA}" == "x64" || "${ISA}" == "mips" || "${ISA}" == "arm" ]]; then
		GTIRB_FOLDER=`dirname $FS_PATH`
		GTIRB_FILE=`basename $FS_PATH`
		CACHE_PATH="${GTIRB_FOLDER}/.vscode.${GTIRB_FILE}"
		GTIRB_BASE=${GTIRB_FILE%.*}
		ISA_DIR=${CACHE_PATH}/${ISA}
		ASM_FILE="${ISA_DIR}/${GTIRB_BASE}.gtasm"

		if ${DEBUG} 
		then
			echo "GTIRB file path: ${FS_PATH}" > ${GTIRB_FOLDER}/log.txt
			echo "GTIRB_FOLDER: ${GTIRB_FOLDER}" >> ${GTIRB_FOLDER}/log.txt
			echo "GTIRB_FILE: ${GTIRB_FILE}" >> ${GTIRB_FOLDER}/log.txt
			echo "CACHE_PATH: ${CACHE_PATH}" >> ${GTIRB_FOLDER}/log.txt
			echo "ISA_DIR: ${ISA_DIR}" >> ${GTIRB_FOLDER}/log.txt
			echo "ASM_FILE: ${ASM_FILE}" >> ${GTIRB_FOLDER}/log.txt
		fi
	else
		MESSAGE="Bad ISA: ${ISA}."
		CONTINUE=false
	fi
fi


if ${CONTINUE} 
then
	if [[ -d ${ISA_DIR} && -f ${ASM_FILE} ]]; then
		MESSAGE="Using existing assembly file ${ASM_FILE}"
		CONTINUE=false
	else
		# IFF it doesn't exist, create a subdir for caching files
		if [[ ! -d ${ISA_DIR} ]]; then
			mkdir -p ${ISA_DIR}
		fi
		if [[ ! -d ${ISA_DIR} ]]; then
			MESSAGE="Failed to create cache subdir ${ISA_DIR}"
			CONTINUE=false
		fi
	fi
fi

if ${CONTINUE} 
then
	gtirb-pprinter --ir ${FS_PATH} --asm ${ASM_FILE} --listing-mode ui 
	if [[ ! -f ${ASM_FILE} ]]; then
		MESSAGE="Failed to create ASM FILE ${ASM_FILE}"
	fi
fi

echo "${MESSAGE}"
