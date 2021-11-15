# -*- coding: utf-8 -*-

import os
import json
import logging
import argparse
import gtirb
import uuid
import re
from collections import defaultdict
from typing import List, Optional, Union, Tuple
from pygls.server import LanguageServer
from pygls.protocol import LanguageServerProtocol
from pygls.lsp.methods import (
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_CLOSE,
    TEXT_DOCUMENT_DID_SAVE,
    TEXT_DOCUMENT_DID_CHANGE,
    DEFINITION,
    REFERENCES,
    HOVER
)
from pygls.lsp.types import (
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    DidCloseTextDocumentParams,
    DidChangeTextDocumentParams,
    Location,
    LocationLink,
    Position,
    Range,
    DefinitionParams,
    DefinitionOptions,
    ReferenceParams,
    ReferenceOptions,
    ReferenceContext,
    Hover,
    HoverOptions,
    HoverParams,
    MarkupKind,
    MarkupContent
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

DEFAULT_PORT = 3036
DEFAULT_TCP_FLAG = False
DEFAULT_STDIO_FLAG = True

StringList = List[str]
LocationList = List[Location]

current_gtirbs = {}
current_indexes = {}
current_documents = {}

# https://stackoverflow.com/questions/36588126/uuid-is-not-json-serializable
class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            # if the obj is uuid, we simply return the value of uuid
            return obj.hex
        return json.JSONEncoder.default(self, obj)

def line_to_offset(document_uri: str, line: int) -> Optional[gtirb.Offset]:
    try:
        return current_indexes[document_uri][0][line]
    except:
        return None

def offset_to_line(document_uri: str, offset: gtirb.Offset) -> Optional[int]:
    try:
        return current_indexes[document_uri][1][offset]
    except:
        return None

def offset_to_comment(document_uri: str, offset: gtirb.Offset) -> Optional[str]:
    try:
        return current_gtirbs[document_uri].modules[0].aux_data['comments'][offset]
    except:
        return None

# Local class allows addition  of a configuration section
# See pygls example: json language server
class GtirbLanguageServer(LanguageServer):
    CONFIGURATION_SECTION = 'gtirbServer'

    def __init__(self):
        super().__init__()

def get_byte_interval_from_block(module, thisblock):
    for section in module.sections:
        for byte_interval in section.byte_intervals:
            for block in byte_interval.blocks:
                if (block == thisblock):
                    return byte_interval
    return None

def get_block_address(module, block):
    if type(block) is gtirb.block.CodeBlock or type(block) is gtirb.block.DataBlock:
        byte_interval = get_byte_interval_from_block(module, block)
        if byte_interval is not None:
            return hex(byte_interval.address + block.offset)
    return None


#
# chars to strip out so as to leave a line consisting of actual tokens
delims = ['+', '-', '[', ']', ':', '{', '}', '*', ',']
def replace_delims(line):
    for ch in delims:
        line = line.replace(ch, ' ')
    return line


def isolate_token(line: str, pos: int) -> str:
    if pos < 0 or pos >= len(line):
        return ""
    p = re.compile('[^ \t\n\r\f\v]+')
    for m in p.finditer(replace_delims(line)):
        if pos >= m.start() and pos < m.start()+len(m.group()):
            return m.group()
    return ""


def get_line_offset(ir: gtirb, text: str) -> List[Tuple[int, Tuple[int, int]]]:
    """Process ASM listing string TEXT with respect to GTIRB IR to return a
    list of line numbers and associated offsets."""

    # Process the assembly code file to create a list of (address, line_number).
    addr_re = re.compile("# EA: (0x[0-9a-f]+)$")
    address_lines = list(map(lambda pair: (int(pair[0], 16), pair[1]),
                             filter(lambda x: x[0],
                                    map(lambda line: ((addr_re.search(line[1]) or [None, None])[1],
                                                      line[0]),
                                        enumerate(text.splitlines())))))
    address_lines.sort(key=lambda x: x[0])

    # Process the gtirb file to create a list of (address, UUID).
    address_uuids = list(map(lambda b: (b.address, b.uuid), ir.byte_blocks))
    address_uuids.sort(key=lambda x: x[0])

    # Walk the lists building up a map of line_number <-> (uuid, offset).
    line_offsets = []
    last = None
    # Lowest address in file should be in a block.
    assert(address_lines[0][0] >= address_uuids[0][0])
    for (address, line_number) in address_lines:
        # Check if we're into the next block.
        if(address >= address_uuids[0][0]):
            last = address_uuids.pop(0)
        line_offsets += [(line_number, (last[1], address - last[0]))]

    return line_offsets

def ensure_index(text_document):
    path_list = text_document.uri.split('//')

    if len(path_list) > 1 and path_list[0] == 'file:':
        asmfile = path_list[1]
        cachedir = os.path.dirname(os.path.dirname(asmfile))
        cachedir_base = os.path.basename(cachedir)
        if cachedir_base.startswith(".vscode."):
            gtirbfile_base = cachedir_base[8:]
            gtirbfile = os.path.join(os.path.dirname(cachedir), gtirbfile_base)
            logger.info(f"gtirbfile: {gtirbfile}")
            jsonfile = asmfile+'.json'
    else:
        logger.error(f"error in text document path: {text_document.uri}")
        return

    try:
        ir = gtirb.IR.load_protobuf(gtirbfile)
    except Exception as inst:
        logger.error(inst)
        logger.error("Unable to load gtirb file %s." % gtirbfile)
        return

    line_offsets = None
    if os.path.exists(jsonfile):
        logger.info(f"Loading (line-number,offset(UUID,int)) map from JSON file: {jsonfile}")
        # Convert UUIDs back from hex to UUIDs.
        line_offsets = list(map(lambda el: (el[0],(uuid.UUID(hex=el[1][0]),el[1][1])),
                                json.load(open(jsonfile,'r'))))

    else:
        logger.info(f"Populating (line-number,offset(UUID,int)) map to JSON file: {jsonfile}")
        line_offsets = get_line_offset(ir, text_document.text)

        # Store the resulting map into a JSON file.
        json.dump(line_offsets, open(jsonfile,'w'), cls=UUIDEncoder)

    # Create maps from line_uuids going both ways.
    line_to_offset = {}
    offset_to_line = {}
    for (line, offset) in line_offsets:
        # Convert (uuid,displacement) tuples to actual GTIRB offsets.
        offset = gtirb.Offset(ir.get_by_uuid(offset[0]), offset[1])
        line_to_offset[line] = offset
        offset_to_line[offset] = line

    # Add to current indexes
    current_indexes[text_document.uri] = (line_to_offset, offset_to_line)

server = GtirbLanguageServer()

@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls, params: DidChangeTextDocumentParams):
    """Text document did change notification."""
    logger.info(f"Text Document Did Change notification, uri: {params.text_document.uri}")
    # extraneous # return None


@server.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls, params: DidOpenTextDocumentParams):
    """Text document did open notification."""
    logger.info(f"Text Document Did Open notification, uri: {params.text_document.uri}")
    splitpath = os.path.splitext(params.text_document.uri)
    ext = splitpath[1]

    # This is where to check the extension
    if ext == '.gtasm':
        # Maybe make this a store of split lines so only needs to be split once
        current_documents[params.text_document.uri] = params.text_document
        logger.info('Added to document list')
        ensure_index(params.text_document)
        logger.info('finished indexing')


@server.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(ls, params: DidCloseTextDocumentParams):
    """Text document did close notification."""
    logger.info(f"Text Document Did Close notification, uri: {params.text_document.uri}")
    if params.text_document.uri in current_documents:
        del current_documents[params.text_document.uri]
        del current_indexes[params.text_document.uri]
        del current_gtirbs[params.text_document.uri]
        logger.info("removed document from list of current documents")

@server.feature(DEFINITION, DefinitionOptions())
def get_definition(ls, params: DefinitionParams) -> Optional[Union[Location, List[Location], List[LocationLink]]]:
    """Text document definition request."""
    logger.info(f"Definition request received uri: {params.text_document.uri}")
    current_line: str = ""
    current_text: str = ""
    current_token: str = ""
    current_lines: StringList = []
    if params.text_document.uri in current_documents:
        text_document = current_documents[params.text_document.uri]
        current_text = text_document.text
        current_lines = current_text.splitlines()
        current_line = current_lines[params.position.line]
        current_token = isolate_token(current_line, params.position.character)
        if current_token == None or len(current_token) == 0:
            return None
    else:
        # Load the cached index here if it exists?
        ls.show_message(f" document {params.text_document.uri} is not in the current document store.")
        return None

    if params.text_document.uri in current_indexes:
        index = current_indexes[params.text_document.uri]
        if current_token in index.defs:
            adef = index.defs[current_token]
        else:
            return None
        # Expecting only one def
        definition_line: str = current_lines[adef]
        location = Location(
            uri = params.text_document.uri,
            range = Range(
                start = Position(line = adef,
                    character = definition_line.find(current_token)),
                end = Position(line = adef,
                    character = definition_line.find(current_token) + len(current_token))))
    else:
        ls.show_message(f" document {params.text_document.uri} is not in the current index store.")
        return None

    return location

# remove async ? test code does not have.
#    async def get_references(ls, params: ReferenceParams):
    # returns Optional[List[Location]]
@server.feature(REFERENCES, ReferenceOptions())
def get_references(ls, params: ReferenceParams) -> Optional[List[Location]]:
    """Text document references request."""
    logger.info(f"References request received uri: {params.text_document.uri}")
    # put decl here so they func-global, will need them later
    # "current_text" is the text of the whole document
    current_line: str = ""
    current_text: str = ""
    current_token: str = ""
    current_lines: StringList = []
    locations: LocationList = []
    if params.text_document.uri in current_documents:
        text_document = current_documents[params.text_document.uri]
        current_text = text_document.text
        current_lines = current_text.splitlines()
        current_line = current_lines[params.position.line]
        current_token = isolate_token(current_line, params.position.character)
        if current_token == None or len(current_token) == 0:
            return None
    else:
        # Check if cache exists ono file system?
        ls.show_message(f" document {params.text_document.uri} is not in the current document store.")
        return None

    if params.text_document.uri in current_indexes:
        index = current_indexes[params.text_document.uri]
        refs = index.xref[current_token]
        if refs == None or len(refs) == 0:
            return None
        for ref in refs:
            reference_line: str = current_lines[ref]
            locations.append(Location(
                uri = params.text_document.uri,
                range = Range(
                    start = Position(line = ref,
                        character = reference_line.find(current_token)),
                    end = Position(line = ref,
                        character = reference_line.find(current_token) + len(current_token)))))
    else:
        ls.show_message(f" document {params.text_document.uri} is not in the current index store.")
        return None

    return locations

@server.feature(HOVER, HoverOptions())
def get_hover(ls, params: HoverParams) -> Optional[Hover]:
    logger.info(f"Hover request received uri: {params.text_document.uri}")
    offset = line_to_offset(params.text_document.uri, params.position.line)

    if offset:
        return Hover(
            contents=MarkupContent(
                kind=MarkupKind.PlainText,
                value=offset_to_comment(offset)
            )
        )
    else:
        return None

def gtirb_tcp_server(host: str, port: int) -> None:
    server.start_tcp(host, port)


def gtirb_stdio_server() -> None:
    server.start_io()
