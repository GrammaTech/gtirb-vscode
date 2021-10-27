#!/usr/bin/env bash
#
DEBUG=true

if [[ $# -gt 0 ]]; then
	FS_PATH=$1
	if [[ ${DEBUG} ]]; then
		echo "GTIRB file path: ${FS_PATH}"
	fi
	ISA=`./get-isa.py ${FS_PATH}`
	if [[ "${ISA}" == "x86" || "${ISA}" == "x64" || "${ISA}" == "mips" || "${ISA}" == "arm" ]]; then
		if [[ ${DEBUG} ]]; then
			rm -f ${GTIRB_FOLDER}/log.txt # !!!!!!!!!!!!! tmp of course get rid of
		fi
		GTIRB_FOLDER=`dirname $FS_PATH`
		GTIRB_FILE=`basename $FS_PATH`
		CACHE_PATH="${GTIRB_FOLDER}/.vscode.${GTIRB_FILE}"
		if [[ ${DEBUG} ]]; then
			echo "GTIRB_FOLDER: ${GTIRB_FOLDER}" > ${GTIRB_FOLDER}/log.txt
			echo "GTIRB_FILE: ${GTIRB_FILE}" >> ${GTIRB_FOLDER}/log.txt
			echo "CACHE_PATH: ${CACHE_PATH}" >> ${GTIRB_FOLDER}/log.txt
		fi
		# IFF it doesn't exist, create a subdir for caching files
		if [[ ! -d ${CACHE_PATH} ]]; then
			mkdir ${CACHE_PATH}
		fi
		if [[ ! -d ${CACHE_PATH} && ${DEBUG} ]]; then
			echo "Failed to create work subdir ${CACHE_PATH}" >> ${GTIRB_FOLDER}/log.txt
		else
			ISA_DIR=${CACHE_PATH}/${ISA}
			if [[ ! -d ${ISA_DIR} ]]; then
				mkdir ${ISA_DIR}
			fi 
			if [[ ! -d ${ISA_DIR} && ${DEBUG} ]]; then
				echo "Failed to create ISA subdir ${ISA_DIR}" >> ${GTIRB_FOLDER}/log.txt
			else
				GTIRB_BASE=${GTIRB_FILE%.*}
				ASM_FILE="${ISA_DIR}/${GTIRB_BASE}.gtasm"
				echo "creating asm file ${ASM_FILE}"
				gtirb-pprinter --ir ${FS_PATH} --asm ${ASM_FILE} 
				if [[ ! -f ${ASM_FILE} && ${DEBUG} ]]; then
					echo "Failed to create ASM FILE ${ASM_FILE}" >> ${GTIRB_FOLDER}/log.txt
				fi
			fi
		fi
	else
		if [[ ${DEBUG} ]]; then
			echo "BAD ISA: ${ISA}"
		fi
	fi
		
	#touch ${ASM_FILE}
else
	if [[ ${DEBUG} ]]; then
		echo "no file?"
	fi
fi
