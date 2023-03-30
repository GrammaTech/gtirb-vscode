# -*- coding: utf-8 -*-
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

import asyncio
import tempfile
import hashlib
import base64
import json
import logging
import os
import re
import uuid
from typing import Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse, unquote

import gtirb

from pygls.lsp.methods import (
    DEFINITION,
    HOVER,
    REFERENCES,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_CLOSE,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_SAVE,
)

from pygls.server import LanguageServer
from pygls.protocol import LanguageServerProtocol
from pygls.workspace import Document

from pygls.lsp.types import (
    DefinitionOptions,
    DefinitionParams,
    DidChangeTextDocumentParams,
    DidSaveTextDocumentParams,
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    Hover,
    HoverOptions,
    HoverParams,
    Location,
    MarkupContent,
    MarkupKind,
    Position,
    Range,
    ReferenceOptions,
    ReferenceParams,
)

from pygls.lsp.types import TextDocumentItem

from pydantic import BaseModel
from concurrent.futures import Future
import importlib
import sys

# # Might be useful at some point but keeping commented now to avoid hurting our test coverage.
# #
# # From https://towardsdatascience.com/a-simple-way-to-trace-code-in-python-a15a25cbbf51
#
# import functools
#
# def tracefunc(func):
#     """Decorates a function to show its trace."""
#
#     @functools.wraps(func)
#     def tracefunc_closure(*args, **kwargs):
#         """The closure."""
#         result = func(*args, **kwargs)
#         logger.debug(f"{func.__name__}(args={args}, kwargs={kwargs}) => {result}")
#         return result
#
#     return tracefunc_closure


logger = logging.getLogger(__name__)

DEFAULT_PORT = 3036
DEFAULT_TCP_FLAG = False
DEFAULT_STDIO_FLAG = True

StringList = List[str]
LocationList = List[Location]

#
# Manage the index information for currently opened documents:
# These are dicts whose key is a text document URI, added to
# when that document is opened and removed when it is closed.
#
# GTIRB IR of currently opened documents
current_gtirbs = {}

#
# Indexes, a tuple. [0] is a map from line to Offset, [1] is the inverse.
current_indexes = {}

#
# Offsets with pending edits.
modified_blocks = {}

#
# Locations for gtirbfile and indexing (json) for each document
# For a remote-mode server they don't have a fixed location
# relative to the listing file.
gtirbfile_path_map = {}
indexfile_path_map = {}

#
# Always act like a remote server, even in STDIO mode.
# This means that we do not assume any direct access to the client filesystem,
# and will always request file contents be sent over LSP when needed.
# This could be useful if, for example, the user wishes to start this server
# over SSH, in Docker, or as a different user on the same system.
force_remote = False


class GtirbPushParams(BaseModel):
    uri: str
    content: str


# The LSP server object
# This is a customizatino of the pygls language server, adding
# configuration section, custom commands, and properties.
# See pygls example: json language server
class GtirbLanguageServer(LanguageServer):
    """GTIRB LSP Server
    A language server implementation customized for GTIRB,
    including transferring gtirb files between client and server.
    """

    CONFIGURATION_SECTION = "gtirbServer"
    # Custom commands
    # These will be registered with the client when it connects with the server.
    # To be available to the client they must be listed in the manifest.
    CMD_GET_LINE_FROM_ADDRESS = "gtirbGetLineFromAddress"
    CMD_GET_ADDRESS_OF_SYMBOL = "gtirbGetAddressOfSymbol"
    CMD_GET_LINE_ADDRESS_LIST = "gtirbGetLineAddressList"
    CMD_GET_FUNCTION_LOCATIONS = "gtirbGetFunctionLocations"
    CMD_GET_MODULE_NAME = "gtirbGetModuleName"
    # Custom requests
    # Must match a registered handler in the client
    REQ_GET_GTIRB_FILE = "gtirbGetGtirbFile"
    REQ_PUSH_GTIRB_FILE = "gtirbPushGtirbFile"

    def __init__(self, loop=None, protocol_cls=LanguageServerProtocol, max_workers: int = 2):
        super().__init__(loop, protocol_cls, max_workers)
        self.rewrite_enabled = True
        self.gtirb_types_imported = False
        self.server_remote = False
        self.host = None
        self.port = None

    def can_rewrite(self) -> bool:
        """Returns whether server has ability to rewrite GTIRB files"""
        return self.rewrite_enabled

    def disable_rewrite(self) -> None:
        """Disables server GTIRB rewriting"""
        self.rewrite_enabled = False

    def set_remote(self, host, port) -> None:
        """Sets server to remote mode"""
        self.host = host
        self.port = port
        self.server_remote = True

    def is_remote(self) -> bool:
        """Returns whether server is in remote mode"""
        return self.server_remote or force_remote

    def get_gtirb_content(self, params: str, callback=None) -> Future:
        """Sends gtirb file request to the client.

        Args:
            params(str): GTIRB file path
        Returns:
            concurrent.futures.Future object that will be resolved once a
            response has been received
        """
        return self.lsp.send_request(self.REQ_GET_GTIRB_FILE, params, callback)

    def get_gtirb_content_async(self, params: str) -> asyncio.Future:
        """Calls `get_gtirb_file` method but designed to use with coroutines.

        Args:
            params(str): GTIRB file path
        Returns:
            concurrent.futures.Future object that will be resolved once a
            response has been received
        """
        return asyncio.wrap_future(self.get_gtirb_content(params))

    def push_gtirb_content(self, uri: str, content: str, callback=None) -> Future:
        """Sends gtirb file content to the client.

        Args:
            uri(str): URI of GTIRB file on the client
            content(str): GTIRB content in base64 encoding
        Returns:
            concurrent.futures.Future object that will be resolved once a
            response has been received
        """
        return self.lsp.send_request(
            self.REQ_PUSH_GTIRB_FILE, GtirbPushParams(uri=uri, content=content), callback
        )

    def push_gtirb_content_async(self, uri: str, content: str) -> asyncio.Future:
        """Calls `push_gtirb_file` method but designed to use with coroutines.

        Args:
            uri(str): URI of GTIRB file on the client
            content(str): GTIRB content in base64 encoding
        Returns:
            concurrent.futures.Future object that will be resolved once a
            response has been received
        """
        return asyncio.wrap_future(self.push_gtirb_content(uri, content))


class NonTerminatingLanguageServerProtocol(LanguageServerProtocol):
    """
    A language server protocol implementation which ignores
    exit/shutdown/connection_lost messages from the client,
    unless the server is running as a subprocess.
    """

    def bf_exit(self, *args) -> None:
        """Stops the server process."""
        pass

    def bf_shutdown(self, *args) -> None:
        """Request from client which asks server to shutdown."""
        pass


def get_symbol_by_referent(ir, uuid):
    """Get a function name based on the block it references"""
    block = ir.get_by_uuid(uuid)
    if type(block) is not gtirb.block.CodeBlock:
        logger.info("new get symbol by reference failed to get block.")
        return None
    for ref in block.references:
        if ref._payload.uuid == uuid:
            return ref.name
    return None


def load_prototype_table(ir, types, c_str):
    """Load a table of prototypes from aux data, if possible"""
    aux_data: gtirb.AuxData = ir.modules[0].aux_data
    function_names_data: Dict = aux_data.get("functionNames", gtirb.AuxData({}, "")).data
    prototype_table_data: Dict = aux_data.get("prototypeTable", gtirb.AuxData({}, "")).data
    type_table_data: Dict = aux_data.get("typeTable", gtirb.AuxData({}, "")).data

    function_to_prototype = {}
    for key in prototype_table_data:
        if key in function_names_data:
            function_name = function_names_data[key].name
        else:
            continue
        function_type = prototype_table_data[key]
        if function_type in type_table_data:
            function_to_prototype[function_name] = c_str(types.get_type(function_type))
    return function_to_prototype


# Symbolic references may appear at addresses not represented by offsets in the
# line to offset map, so a limited interval search is allowed to find an Offset
# mapping to a line in the document.
# This sets the size of that interval and may need to be adjusted for optimal results
DISPLACEMENT_INTERVAL = 5


def offset_to_line(line_by_offset: Dict[int, gtirb.Offset], offset: gtirb.Offset) -> Optional[int]:
    """Lookup OFFSET in the current indexes to return the associated LINE"""
    for i in range(offset.displacement, max(-1, (offset.displacement - DISPLACEMENT_INTERVAL)), -1):
        line = line_by_offset.get(gtirb.Offset(offset.element_id, i))
        if line and isinstance(line, int):
            return line
    return None


def offset_to_predecessors(ir: gtirb, offset: gtirb.Offset) -> Optional[List[gtirb.Offset]]:
    """Return all edges in to the given offset"""
    return map(lambda edge: gtirb.Offset(edge.source, 0), ir.cfg.in_edges(offset.element_id))


def offset_to_successors(ir: gtirb, offset: gtirb.Offset) -> Optional[List[gtirb.Offset]]:
    """Return all edges out of the given offset"""
    return map(lambda edge: gtirb.Offset(edge.target, 0), ir.cfg.out_edges(offset.element_id))


def all_symbolic_expression_symbols(ir: gtirb) -> Set[Tuple[int, gtirb.Symbol]]:
    """Return a set of all symbols used in symbolic expressions, with their addresses"""
    return {
        (
            (byte_interval.address + symbolic_expression[0]),
            symbolic_expression[1].symbol
            if isinstance(symbolic_expression[1], gtirb.symbolicexpression.SymAddrConst)
            else symbolic_expression[1].symbol1,
        )
        for byte_interval in ir.modules[0].byte_intervals
        for symbolic_expression in byte_interval.symbolic_expressions.items()
    }


def symbolic_references(
    ir: gtirb, symbols: Union[gtirb.Symbol, List[gtirb.Symbol]]
) -> List[Tuple[int, gtirb.Symbol]]:
    """
    Return a list of all matching symbols and their addresses
    from the set of all symbolic expressions
    """
    if isinstance(symbols, gtirb.Symbol):
        uuid = symbols.uuid
        return filter(
            lambda pair: pair[1] and pair[1].uuid == uuid, all_symbolic_expression_symbols(ir)
        )
    else:
        uuids = list(map(lambda s: s.uuid, symbols))
        return filter(
            lambda pair: pair[1] and pair[1].uuid in uuids, all_symbolic_expression_symbols(ir)
        )


def offsets_at_references(
    ir: gtirb, references: List[Tuple[int, gtirb.Symbol]]
) -> List[Tuple[gtirb.Offset, gtirb.Symbol]]:
    """Return a list of offsets that reference the given symbols"""
    results = []
    for (address, symbol) in references:
        for block in ir.modules[0].byte_blocks_on(address):
            results.append(
                (
                    gtirb.Offset(element_id=block, displacement=((address - block.address) - 1)),
                    symbol,
                )
            )
    return results


def first_line_for_uuid(offset_by_line: Dict[int, gtirb.Offset], uuid: uuid.UUID) -> Optional[int]:
    """Return the first line (lowest numerically) where the offset matches the given UUID"""
    lines = sorted(
        map(
            lambda pair: pair[0],
            filter(lambda pair: pair[1].element_id.uuid == uuid, offset_by_line.items()),
        )
    )
    if len(lines) > 0:
        return lines[0]
    return None


def block_lines(line_by_offset: Dict[gtirb.Offset, int], block: gtirb.ByteBlock) -> List[int]:
    """Return a list of line numbers for all the listing lines associated with the given block"""
    return list(
        filter(
            None,
            map(
                lambda i: line_by_offset.get(gtirb.Offset(element_id=block, displacement=i)),
                range(block.size),
            ),
        )
    )


def block_text(
    line_by_offset: Dict[gtirb.Offset, int], block: gtirb.ByteBlock, asm_lines: List[str]
) -> str:
    """Return the text of all the listing lines associated with the given block"""
    return "\n".join(
        list(
            map(
                lambda line: asm_lines[line].split("#")[0].rstrip(),
                block_lines(line_by_offset, block),
            )
        )
    )


def symbol_for_name(ir: gtirb, name: str) -> Optional[gtirb.Symbol]:
    """Return the GTIRB symbol whose name matches the given string"""
    return next(map(lambda s: s, filter(lambda s: s.name == name, ir.modules[0].symbols)), None)


def function_uuid_for_name(ir: gtirb, name: str) -> Optional[uuid.UUID]:
    """Return the UUID of the function in IR with NAME."""
    aux_data: gtirb.AuxData = ir.modules[0].aux_data
    function_names: Dict = aux_data.get("functionNames", gtirb.AuxData({}, "")).data
    for function_uuid, symbol in function_names.items():
        if symbol.name == name:
            return function_uuid
    return None


#
# chars to strip out so as to leave a line consisting of actual tokens
delims = ["+", "-", "[", "]", ":", "{", "}", "*", ",", "(", ")"]


def replace_delims(line):
    """Return the given line with all delimiters replaced with spaces"""
    for ch in delims:
        line = line.replace(ch, " ")
    return line


def isolate_token(line: str, pos: int) -> str:
    """Return the token found at the given line and character number"""
    if pos < 0 or pos >= len(line):
        return ""
    p = re.compile("[^ \t\n\r\f\v]+")
    for m in p.finditer(replace_delims(line)):
        if pos >= m.start() and pos <= m.start() + len(m.group()):
            return m.group()
    return ""


def preceding_function_line(current_lines: StringList, name: str, line: int) -> Optional[int]:
    """
    Return the line where the named function is declared,
    searching backwards from the given line.
    """
    logger.debug(f"preceding_function_line(asm, '{name}', {line})")
    name_re = re.compile(name + ":")
    addr_re = re.compile("# EA: (0x[0-9a-f]+)$")
    for i in range(1, line):
        if name_re.search(current_lines[line - i]):
            return line - i
        elif addr_re.search(current_lines[line - i]):
            return None
    return None


def get_line_offset(ir: gtirb, current_lines: StringList) -> List[Tuple[int, Tuple[int, int]]]:
    """Process ASM listing string TEXT with respect to GTIRB IR to return a
    list of line numbers and associated offsets."""

    # Process the assembly code file to create a list of (address, line_number).
    addr_re = re.compile("# EA: (0x[0-9a-f]+)$")
    address_lines = list(
        map(
            lambda pair: (int(pair[0], 16), pair[1]),
            filter(
                lambda x: x[0],
                map(
                    lambda line: ((addr_re.search(line[1]) or [None, None])[1], line[0]),
                    enumerate(current_lines),
                ),
            ),
        )
    )
    address_lines.sort(key=lambda x: x[0])

    # Process the gtirb file to create a list of (address, UUID).
    address_to_uuid_displacement = {}
    for block in ir.byte_blocks:
        if block.address:
            for i in range(block.size):
                address_to_uuid_displacement[block.address + i] = (block.uuid, i)
        else:
            logger.warning("Block has no address, gtirb file may be defective.")

    # Walk the lists building up a map of line_number <-> (uuid, offset).
    # Lowest address in file should be in a block.
    line_offsets = []
    for (address, line_number) in address_lines:
        line_offsets += [(line_number, address_to_uuid_displacement[address])]

    return line_offsets


def line_offsets_to_maps(
    ir: gtirb, line_offsets: List[Tuple[int, int]]
) -> Tuple[Dict[int, gtirb.Offset], Dict[gtirb.Offset, int]]:
    """Create maps from line_uuids going both ways."""
    logger.debug("Create maps from line_uuids going both ways.")
    offset_by_line = {}
    line_by_offset = {}
    for (line, offset) in line_offsets:
        # Convert (uuid, displacement) tuples to actual GTIRB offsets.
        offset = gtirb.Offset(ir.get_by_uuid(offset[0]), offset[1])
        offset_by_line[line] = offset
        line_by_offset[offset] = line
    return (offset_by_line, line_by_offset)


# Used to serialize UUIDs to JSON.
# https://stackoverflow.com/questions/36588126/uuid-is-not-json-serializable
class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            # if the obj is uuid, we simply return the value of uuid
            return obj.hex
        return json.JSONEncoder.default(self, obj)


def ensure_index(text_document: TextDocumentItem) -> Tuple[bool, bool]:
    """
    Create (or load from file if possible) an offset/line index for the given listing file.
    Return a tuple of
    [0] True if indexing OK and
    [1] True iff reusing a previously created index
    """
    logger.debug(f"ensure_index({text_document.uri})")
    reused_index = False

    try:
        gtirbfile = gtirbfile_path_map[text_document.uri]
        jsonfile = indexfile_path_map[text_document.uri]
        ir = gtirb.IR.load_protobuf(gtirbfile)
        current_gtirbs[text_document.uri] = ir
    except Exception as inst:
        logger.error(inst)
        logger.error(f"Unable to load gtirb file {gtirbfile}")
        return (False, False)

    line_offsets = None
    if os.path.exists(jsonfile):
        try:
            logger.debug(f"Loading (line-number,offset(UUID,int)) map from JSON file: {jsonfile}")
            # Convert UUIDs back from hex to UUIDs.
            line_offsets = list(
                map(
                    lambda el: (el[0], (uuid.UUID(hex=el[1][0]), el[1][1])),
                    json.load(open(jsonfile, "r")),
                )
            )
            reused_index = True
        except Exception:
            logger.info(f"Failed to load JSON file: {jsonfile}")
            line_offsets = None

    if line_offsets is None:
        logger.debug(f"Populating (line-number,offset(UUID,int)) map to JSON file: {jsonfile}")
        current_lines = text_document.text.splitlines()
        line_offsets = get_line_offset(ir, current_lines)

        # Store the resulting map into a JSON file.
        logger.debug(f"line_offsets => {line_offsets}")
        json.dump(line_offsets, open(jsonfile, "w"), cls=UUIDEncoder)

    # Create maps from line_uuids going both ways.
    current_indexes[text_document.uri] = line_offsets_to_maps(ir, line_offsets)
    return (True, reused_index)


def address_to_line(ir: gtirb, line_by_offset: Dict[int, gtirb.Offset], address: int) -> int:
    """Return the listing line number matching the given address"""
    for block in ir.modules[0].byte_blocks_on(address):
        offset = gtirb.Offset(
            element_id=ir.get_by_uuid(block.uuid), displacement=(address - block.address)
        )
        # Some blocks may not map to a line. Use the first one that does.
        line = line_by_offset.get(offset)
        if line:
            return line


def apply_changes_to_indexes(
    offset_by_line: Dict[int, gtirb.Offset],
    line_by_offset: Dict[gtirb.Offset, int],
    changes: List[Tuple[int, int, str]],
) -> Tuple[Dict[int, gtirb.Offset], Dict[gtirb.Offset, int], Set[gtirb.Offset]]:
    """Update indexes to reflect edits"""

    for start, end, text in changes:
        new_count = len(text.splitlines())
        old_count = (end + 1) - start
        growth = new_count - old_count

        def update_line(line):
            if line < (start + min(new_count, old_count)):
                return line
            if line > end:
                return line + growth
            return None

        new_offset_by_line = {}
        new_line_by_offset = {}

        lines = sorted(offset_by_line.keys())
        for line in range(min(lines), max(lines) + growth + 1):
            new_line = update_line(line)
            new_offset = offset_by_line.get(new_line)
            if new_line and new_offset:
                new_offset_by_line[new_line] = new_offset
                new_line_by_offset[new_offset] = new_line

        offset_by_line = new_offset_by_line
        line_by_offset = new_line_by_offset

    return (new_offset_by_line, line_by_offset)


def parse_listing_uri(listing_uri: str) -> Tuple[str, str]:
    """Return the paths to the listing file and gtirb file for the given document URI"""
    parsed = urlparse(listing_uri)
    if parsed.scheme != "file":
        return None, None
    asmfile = unquote(parsed.path)
    # Remove extra leading slash in windows paths
    if asmfile.startswith("/") and ":" in asmfile:
        asmfile = asmfile[1:]
    cachedir = os.path.dirname(os.path.dirname(asmfile))
    cachedir_base = os.path.basename(cachedir)
    if not cachedir_base.startswith(".vscode."):
        return None, None
    gtirbfile_base = cachedir_base[8:]
    gtirbfile = os.path.join(os.path.dirname(cachedir), gtirbfile_base)
    return asmfile, gtirbfile


async def configure_path_mapping(ls: GtirbLanguageServer, text_document: TextDocumentItem) -> None:
    """
    Set file paths for GTIRB and index files

    Initializes the gtirbfile_path_map and indexfile_path_map global
    indexes for the given text document
    """
    asmfile, gtirbfile = parse_listing_uri(text_document.uri)
    if asmfile is None or gtirbfile is None:
        logger.error(f"error in document path: {text_document.uri}")
        return
    #
    # For local files, gtirb file path is now known, set it and return
    if not ls.is_remote():
        gtirbfile_path_map[text_document.uri] = gtirbfile
        indexfile_path_map[text_document.uri] = asmfile + ".json"
        return
    #
    # For remote mode, we need unique file path to store the GTIRB
    # So hash the client IP and document uri together
    transport = ls.lsp.transport
    if hasattr(transport, "get_extra_info"):
        peername = transport.get_extra_info("peername")
    else:
        peername = ("client",)
    client_path = peername[0] + ":" + text_document.uri
    hashname = hashlib.md5(client_path.encode("utf-8")).hexdigest() + ".gtirb"
    remote_gtirbfile = os.path.join(tempfile.gettempdir(), hashname)

    # File might have been pulled already. But if not, pull it now.
    if not os.path.exists(remote_gtirbfile):
        client_gtirbfile_uri = "file://" + gtirbfile
        result = await ls.get_gtirb_content_async(client_gtirbfile_uri)
        gtirb_bytes = result["text"].encode("utf-8")
        with open(remote_gtirbfile, "wb") as file_to_save:
            gtirb_data = base64.decodebytes(gtirb_bytes)
            file_to_save.write(gtirb_data)

    # Store a map to use for finding the files later
    gtirbfile_path_map[text_document.uri] = remote_gtirbfile
    indexfile_path_map[text_document.uri] = remote_gtirbfile + ".json"
    return


def offset_indexed_aux_data(ir: gtirb) -> List[str]:
    """Return a list of the auxdata types in the current GTIRB that are indexed by Offset"""
    results = []
    for (name, value) in ir.modules[0].aux_data.items():
        if not isinstance(value.data, dict):
            continue
        if not value.data or not isinstance(list(value.data.keys())[0], gtirb.Offset):
            continue
        results += [name]
    return results


def offset_to_auxdata(ir: gtirb, offset: gtirb.Offset) -> Optional[str]:
    """Return all auxdata associated with the given offset"""
    result = ""
    for name in offset_indexed_aux_data(ir):
        data = ir.modules[0].aux_data[name].data.get(offset)
        if data:
            result += f"{name}: {data}\n"

    if result == "":
        return None
    else:
        return result


#
# Used in test module
#
async def get_line_from_address(ls: GtirbLanguageServer, *args) -> Optional[Range]:
    """Get the line number for an address for a document"""
    document_uri = args[0][0]
    address_str = args[0][1]
    logger.debug(f"Command: get_line_from_address, uri: {document_uri}")
    if document_uri not in ls.workspace.documents or document_uri not in current_gtirbs:
        ls.show_message(f" No address mapping for {document_uri}")
        return None
    try:
        address = int(address_str, 16)
    except Exception:
        ls.show_message(f" Invalid address {address_str}")
        return None
    ir = current_gtirbs[document_uri]
    line = address_to_line(ir, current_indexes[document_uri][1], address)
    if line:
        # only the line number is really used, set character to 0
        range = Range(
            start=Position(line=line, character=0),
            end=Position(line=line, character=0),
        )
        return range
    # no line found, send message to UI
    ls.show_message(f" No line for {address_str}")
    return None


def parse_function_name(text: str) -> Optional[str]:
    """Parse a function name from TEXT, if possible."""
    logger.debug(f"parse_function_name({text}")

    GLOBL_RE: re.Pattern = re.compile(r"\.globl ([A-Za-z0-9_]+)")
    TYPE_RE: re.Pattern = re.compile(r"\.type ([A-Za-z0-9_]+), @function")
    FUNCTION_LABEL_RE: re.Pattern = re.compile(r"([A-Za-z0-9_]+):")

    for regex in [GLOBL_RE, TYPE_RE, FUNCTION_LABEL_RE]:
        m = regex.match(text)
        if m:
            return m.group(1)
    return None


def function_decompilations(ir: gtirb, name: str) -> Optional[str]:
    """
    Return the decompilation auxdata associated with the given function NAME in IR
    as a markdown string.
    """
    logger.debug(f"function_name_to_auxdata(IR, {name})")

    result: str = ""
    aux_data: gtirb.AuxData = ir.modules[0].aux_data
    function_uuid: uuid.UUID = function_uuid_for_name(ir, name)
    function_sources: Dict = aux_data.get("functionSources", gtirb.AuxData({}, "")).data
    function_sources = function_sources.get(function_uuid, {})
    for annotation_source, text in function_sources.items():
        if text.strip():
            result += f"## {annotation_source}\n```c\n{text.strip()}\n```\n\n"

    return result.strip() if result else None


def create_gtirb_server_instance():

    server = GtirbLanguageServer(protocol_cls=NonTerminatingLanguageServerProtocol)

    functions_spec = importlib.util.find_spec("gtirb_functions")
    rewriting_spec = importlib.util.find_spec("gtirb_rewriting")
    mcasm_spec = importlib.util.find_spec("mcasm")

    if functions_spec and rewriting_spec and mcasm_spec:
        import gtirb_functions
        import gtirb_rewriting
        import mcasm

        X86Syntax = mcasm.X86Syntax
    else:
        logger.info("Disabling rewriting.")
        server.disable_rewrite()

    # import of gtirb_types may fail if python version < 3.7
    try:
        from gtirb_types import GtirbTypes, c_str

        server.gtirb_types_imported = True
        logger.info("Type import successful.")
    except Exception as inst:
        logger.info(f"Type import failed: {inst}.")
        pass

    @server.command(GtirbLanguageServer.CMD_GET_ADDRESS_OF_SYMBOL)
    async def get_address_of_symbol(ls: GtirbLanguageServer, *args) -> Optional[int]:
        """Get the address of a symbol"""
        document_uri = args[0][0]
        symbol_name = args[0][1]
        logger.debug(f"Command: get_address_of_symbol, uri: {document_uri}")
        if document_uri not in ls.workspace.documents or document_uri not in current_gtirbs:
            ls.show_message(f" No address mapping for {document_uri}")
            return None
        ir = current_gtirbs[document_uri]
        symbol = symbol_for_name(ir, symbol_name)
        if (
            symbol is None
            or symbol.referent is None
            or isinstance(symbol.referent, gtirb.block.ProxyBlock)
        ):
            # no address available, log message to UI
            logger.warning(f" {symbol_name} does not have an address")
            return None

        block = symbol.referent
        return hex(block.address)

    @server.command(GtirbLanguageServer.CMD_GET_MODULE_NAME)
    async def get_module_name(ls: GtirbLanguageServer, *args) -> Optional[str]:
        """Get the address of a symbol"""
        document_uri = args[0][0]
        module_index = args[0][1]
        if document_uri not in ls.workspace.documents or document_uri not in current_gtirbs:
            ls.show_message(f" No module name for {document_uri}")
            return None

        ir = current_gtirbs[document_uri]
        if module_index < 0 or module_index >= len(ir.modules):
            logger.warning(f" module index out of range: {document_uri}:{module_index}")
            return None
        module = ir.modules[module_index]
        if len(module.name) > 0:
            return module.name
        else:
            return "module" + str(module_index)

    @server.command(GtirbLanguageServer.CMD_GET_FUNCTION_LOCATIONS)
    async def get_function_locations(ls: GtirbLanguageServer, *args) -> Optional[LocationList]:
        """Get a list of functions and their locations in the listing file"""
        document_uri = args[0][0]
        if document_uri not in ls.workspace.documents or document_uri not in current_gtirbs:
            ls.show_message(f" No {document_uri} in document index")
            return None

        # Get a list of function entries
        ir = current_gtirbs[document_uri]
        module = ir.modules[0]
        try:
            function_names = module.aux_data["functionNames"]
        except Exception as inst:
            logger.info(f"Gtirb does not contain function information {inst}.")
            return None

        # Retrieve the offsets for the URI
        (offset_by_line, line_by_offset) = current_indexes[document_uri]

        # Generate a list of functions from the function entries auxdata
        gtirb_funclist = []
        function_names_data = function_names.data
        for key in function_names_data:
            symbol = function_names_data[key]
            function_name = symbol.name

            # Use GTIRB to get symbol object from function name
            definition_line = first_line_for_uuid(offset_by_line, symbol.referent.uuid)

            if definition_line:
                tup = (function_name, definition_line, definition_line + 1)
                gtirb_funclist.append(tup)

        # Generate a list of locations from the defintion lines
        current_document: Document = ls.workspace.get_document(document_uri)
        current_lines: StringList = current_document.source.splitlines()
        locations: LocationList = []

        for tup in gtirb_funclist:
            symbol = tup[0]
            line_num = tup[1]

            # Adjust line number because function labels are always
            # before the actual code in the listing
            line_num = preceding_function_line(current_lines, symbol, line_num)
            line_text: str = current_lines[line_num]

            # The name should be in the line text,
            # But if it isn't use the whole line as range.
            start_pos = line_text.find(symbol)
            if start_pos == -1:
                locations.append(
                    Location(
                        uri=current_document.uri,
                        range=Range(
                            start=Position(line=line_num, character=0),
                            end=Position(line=line_num, character=len(line_text)),
                        ),
                    )
                )
            else:
                locations.append(
                    Location(
                        uri=current_document.uri,
                        range=Range(
                            start=Position(line=line_num, character=start_pos),
                            end=Position(line=line_num, character=(start_pos + len(symbol))),
                        ),
                    )
                )

        return locations

    @server.command(GtirbLanguageServer.CMD_GET_LINE_FROM_ADDRESS)
    async def get_line_from_address(ls: GtirbLanguageServer, *args) -> Optional[Range]:
        """Get the line number for an address for a document"""
        document_uri = args[0][0]
        address_str = args[0][1]
        if document_uri not in ls.workspace.documents or document_uri not in current_gtirbs:
            ls.show_message(f" No address mapping for {document_uri}")
            return None

        try:
            address = int(address_str, 16)
        except Exception:
            ls.show_message(f" Invalid address {address_str}")
            return None
        ir = current_gtirbs[document_uri]
        line = address_to_line(ir, current_indexes[document_uri][1], address)
        if line:
            # only the line number is really used, set character to 0
            range = Range(
                start=Position(line=line, character=0),
                end=Position(line=line, character=0),
            )
            return range
        # no line found, send message to UI
        ls.show_message(f" No line for {address_str}")
        return None

    @server.command(GtirbLanguageServer.CMD_GET_LINE_ADDRESS_LIST)
    async def get_line_address_list(ls: GtirbLanguageServer, *args) -> List[List[int]]:
        """Get a list of (line, address) pairs for every line with an instruction"""
        document_uri = args[0][0]
        if document_uri not in ls.workspace.documents:
            ls.show_message(f" No address mapping for {document_uri}")
            return None
        offset_by_line = current_indexes[document_uri][0]
        result_list = []
        for line, offset in offset_by_line.items():
            block_addr = offset.element_id.address
            if block_addr is not None:
                result_list.append([line, block_addr + offset.displacement])
        return result_list

    @server.feature(TEXT_DOCUMENT_DID_CHANGE)
    def did_change(ls: GtirbLanguageServer, params: DidChangeTextDocumentParams) -> None:
        """GTIRB listing did change notification."""
        uri = params.text_document.uri
        logger.debug(f"Document Did Change notification, {params.text_document.uri}")
        ls.show_message_log(f"Document Did Change notification, {params.text_document.uri}")

        #
        # Go ahead with tracking edits only if server has enabled rewriting
        #
        if not ls.can_rewrite():
            ls.show_message("Warning: GTIRB rewriting is disabled")
            return None

        if uri not in modified_blocks:
            modified_blocks[uri] = set()

        if uri not in current_indexes:
            ls.show_message(f"document {uri} not in indexes")
            return None
        (offset_by_line, line_by_offset) = current_indexes[uri]

        # Track the blocks modified by the edit.
        for change in params.content_changes:
            for line in range(change.range.start.line, change.range.end.line + 1):
                offset = offset_by_line.get(line)
                logger.debug(f"offset {offset} for edit line {line}")
                if offset:
                    if offset.element_id not in modified_blocks[uri]:
                        asm = block_text(
                            line_by_offset,
                            offset.element_id,
                            ls.workspace.get_document(uri).lines,
                        )
                        logger.debug(f" modified block {offset.element_id} with:\n{asm}")
                    modified_blocks[uri].add(offset.element_id)

        # Update the indices to reflect the edit.
        (offset_by_line, line_by_offset) = apply_changes_to_indexes(
            offset_by_line,
            line_by_offset,
            map(
                lambda change: (change.range.start.line, change.range.end.line + 1, change.text),
                params.content_changes,
            ),
        )

        current_indexes[uri] = (offset_by_line, line_by_offset)

        logger.debug(f"{len(modified_blocks[uri])} blocks for {len(params.content_changes)} edits")
        ls.show_message_log(f"Storing edit for {params.text_document.uri}")

        # TODO: Update the lines<->offset map as the lines change.
        # - get the affected lines from the range
        # - update all lines in the line<->offset map appropriately

        # Could consider updating the spaces in time to ensure the column
        # offset of the address stays consistent.

    @server.feature(TEXT_DOCUMENT_DID_SAVE)
    async def did_save(ls: GtirbLanguageServer, params: DidSaveTextDocumentParams) -> None:
        """
        Text document did save notification.

        If there are pending edits, and rewriting is enabled,
        process the edits and save the modified GTIRB file.
        """
        uri = params.text_document.uri
        logger.debug(f"Text Document Did Save notification, uri: {uri}")
        ls.show_message_log(f"Text Document Did Save notification, uri: {uri}")

        #
        # Go ahead with rewriting procedure only if server has enabled rewriting
        #
        if ls.can_rewrite():

            workspace = ls.workspace
            document = workspace.get_document(uri)
            logger.debug(f"document {document} with {len(document.lines)} lines")

            if (uri not in modified_blocks) or len(modified_blocks[uri]) == 0:
                ls.show_message(f"no pending modifications to {uri}")
                return None

            if uri not in current_gtirbs:
                ls.show_message(f"no GTIRB found for {uri}")
                return None
            ir = current_gtirbs[uri]

            logger.debug(f"applying {len(modified_blocks[uri])} modifications to {uri}")

            functions = gtirb_functions.Function.build_functions(ir.modules[0])
            blocks_to_functions = {
                block: func for func in functions for block in func.get_all_blocks()
            }
            ctx = gtirb_rewriting.RewritingContext(ir.modules[0], functions)

            def literal_patch(asm: str) -> gtirb_rewriting.Patch:
                """
                Creates a patch from a literal string. The patch will have an empty
                constraints object.
                """

                @gtirb_rewriting.patch_constraints(x86_syntax=X86Syntax.INTEL)
                def patch(ctx):
                    return asm

                return gtirb_rewriting.Patch.from_function(patch)

            blocks: List[gtirb.ByteBlock] = []
            for block in modified_blocks[uri]:
                asm = block_text(current_indexes[uri][1], block, document.lines)

                if asm == "":
                    logger.debug("TODO: implement block deletion in gtirb-rewriting")
                    ls.show_message(f"skipping {block} with empty assembly")
                else:
                    logger.debug(f"rewriting {block} to asm:\n{asm}")
                    blocks += [block]
                    ctx.replace_at(
                        blocks_to_functions[block], block, 0, block.size, literal_patch(asm)
                    )

            try:
                if len(blocks) > 0:
                    ctx.apply()
                    # Save gtirb, overwriting the original file
                    gtirbfile = gtirbfile_path_map[uri]
                    ir.save_protobuf(gtirbfile)
                    # If server is running in remote mode,
                    # push modified file back to client:
                    if ls.is_remote():
                        with open(gtirbfile, "rb") as file_to_send:
                            gtirb_data = file_to_send.read()
                            gtirb_bytes = base64.encodebytes(gtirb_data)
                            asmfile, client_gtirb_path = parse_listing_uri(uri)
                            await ls.push_gtirb_content_async(
                                "file://" + client_gtirb_path, gtirb_bytes
                            )
                    ls.show_message("GTIRB rewritten successfully")

                else:
                    ls.show_message("No blocks to rewrite")
                # Clear modified blocks on a SUCCESSFUL rewrite.  Otherwise retain for another try.
                del modified_blocks[uri]
            except Exception as e:
                ls.show_message(f"assembly error: {e}")
        else:
            ls.show_message("GTIRB rewriting is disabled")

            # TODO:
            # - Update the text with gtirb-pprinter
            #   - Return updated text
            #   - Distinguish between modified comments and modified assembly
            #   - Improved warnings when trying to delete blocks
            #   - Retain comments (in a new AuxData in the GTIRB)

    @server.feature(TEXT_DOCUMENT_DID_OPEN)
    async def did_open(ls: GtirbLanguageServer, params: DidOpenTextDocumentParams) -> None:
        """GTIRB listing did open notification."""
        logger.debug(f"Document Did Open notification, uri: {params.text_document.uri}")
        ls.show_message_log(f"Document Did Open notification, uri: {params.text_document.uri}")
        ext = os.path.splitext(params.text_document.uri)[1]

        # This is where to check the extension
        if ext == ".view":
            await configure_path_mapping(ls, params.text_document)
            index_ok, reused_index = ensure_index(params.text_document)
            if index_ok:
                filename = os.path.split(params.text_document.uri)[1]
                ls.show_message(f"{filename} indexing completed.")
                if reused_index:
                    ls.show_message_log(f"re-using indexes for {filename}")

    @server.feature(TEXT_DOCUMENT_DID_CLOSE)
    def did_close(ls: GtirbLanguageServer, params: DidCloseTextDocumentParams) -> None:
        """GTIRB listing did close notification."""
        logger.debug(f"Document Did Close notification, uri: {params.text_document.uri}")
        ls.show_message_log(f"Document Did Close notification, uri: {params.text_document.uri}")
        if params.text_document.uri in modified_blocks:
            del modified_blocks[params.text_document.uri]
        if params.text_document.uri in current_indexes:
            del current_indexes[params.text_document.uri]
            del current_gtirbs[params.text_document.uri]
            ls.show_message_log(
                f"Removed document from index of open documents: {params.text_document.uri}"
            )

    @server.feature(DEFINITION, DefinitionOptions())
    def get_definition(ls: GtirbLanguageServer, params: DefinitionParams) -> Optional[Location]:
        """GTIRB listing definition request."""
        logger.debug(f"Definition request received uri: {params.text_document.uri}")
        ls.show_message_log(f"Definition request received uri: {params.text_document.uri}")
        current_document: Document = ls.workspace.get_document(params.text_document.uri)

        # Make sure the document indexes and gtirb representation are cached
        if (
            current_document.uri not in current_indexes
            or current_document.uri not in current_gtirbs
        ):
            ls.show_message(f"{current_document.uri} is not currently cached.")
            return None

        current_lines: StringList = current_document.source.splitlines()
        current_token: str = isolate_token(
            current_lines[params.position.line], params.position.character
        )

        # Ensure token was found at the given position.
        if current_token is None or len(current_token) == 0:
            ls.show_message(
                f" no token found for {params.position.line}:{params.position.character}"
            )
            return None

        # Retrieve the gtirb for the URI
        ir = current_gtirbs[current_document.uri]

        symbol = symbol_for_name(ir, current_token)
        if (
            symbol is None
            or symbol.referent is None
            or isinstance(symbol.referent, gtirb.block.ProxyBlock)
        ):
            ls.show_message(f" {current_token} is not defined.")
            return None
        logger.debug(f"symbol found: {symbol}")

        line = first_line_for_uuid(current_indexes[current_document.uri][0], symbol.referent.uuid)
        if line is None:
            ls.show_message(f" no definition found for {symbol.name}.")
            return None
        logger.debug(f"line found: {line}")

        line = preceding_function_line(current_lines, current_token, line)
        definition_line: str = current_lines[line]

        return Location(
            uri=current_document.uri,
            range=Range(
                start=Position(line=line, character=definition_line.find(current_token)),
                end=Position(
                    line=line, character=(definition_line.find(current_token) + len(current_token))
                ),
            ),
        )

    @server.feature(REFERENCES, ReferenceOptions())
    def get_references(
        ls: GtirbLanguageServer, params: ReferenceParams
    ) -> Optional[List[Location]]:
        """GTIRB listing references request."""
        logger.debug(f"References request received uri: {params.text_document.uri}")
        ls.show_message_log(f"References request received uri: {params.text_document.uri}")
        current_document: Document = ls.workspace.get_document(params.text_document.uri)

        # Make sure the document indexes and gtirb representation are cached
        if (
            current_document.uri not in current_indexes
            or current_document.uri not in current_gtirbs
        ):
            ls.show_message(f"{current_document.uri} is not currently cached.")
            return None

        current_lines: StringList = current_document.source.splitlines()
        current_token: str = isolate_token(
            current_lines[params.position.line], params.position.character
        )
        locations: LocationList = []

        # Ensure token was found at the given position.
        if current_token is None or len(current_token) == 0:
            ls.show_message(
                f" no token found for {params.position.line}:{params.position.character}"
            )
            return None

        # Retrieve the gtirb for the URI
        ir = current_gtirbs[current_document.uri]

        # Retrieve the offsets for the URI
        (offset_by_line, line_by_offset) = current_indexes[current_document.uri]

        # If token is a GTIRB symbol, find references to it,
        # otherwise find references to whatever block the cusor is in
        symbol = symbol_for_name(ir, current_token)
        if symbol is None or (
            symbol.referent is not None and isinstance(symbol.referent, gtirb.block.ProxyBlock)
        ):
            reference_line = params.position.line
        else:
            # Cover the case of a symbol that has no referent
            if symbol.referent is None:
                ls.show_message(f" symbol for {current_token} not found.")
                return None
            reference_line = first_line_for_uuid(offset_by_line, symbol.referent.uuid)

        offset = offset_by_line.get(reference_line)
        if offset is None:
            ls.show_message(f" no offset found for line {reference_line}.")
            return None
        logger.debug(f"offset found: {offset}")

        references = list(symbolic_references(ir, offset.element_id.references))
        if len(references) == 0:
            ls.show_message(f" no references found for line {reference_line}.")
            return None
        logger.debug(f"references found: {references}")

        offsets_and_referenced_symbols = offsets_at_references(ir, references)
        if len(offsets_and_referenced_symbols) == 0:
            ls.show_message(f" no offsets found for {references}.")
            return None
        logger.debug(f"offsets found: {offsets_and_referenced_symbols}")

        # This is now lines and symbols
        lines_and_referenced_symbols = list(
            filter(
                lambda it: isinstance(it[0], int),
                map(
                    lambda off_and_se: (
                        offset_to_line(line_by_offset, off_and_se[0]),
                        off_and_se[1],
                    ),
                    offsets_and_referenced_symbols,
                ),
            )
        )
        if len(lines_and_referenced_symbols) == 0:
            ls.show_message(f" no lines for offsets {offsets_and_referenced_symbols}.")
            return None
        logger.debug(f"lines found: {lines_and_referenced_symbols}")

        for (line, symbol) in lines_and_referenced_symbols:
            reference_line: str = current_lines[line]
            token = None
            if reference_line.find(symbol.name) > 0:
                token = symbol.name
            if token:
                locations.append(
                    Location(
                        uri=current_document.uri,
                        range=Range(
                            start=Position(line=line, character=reference_line.find(token)),
                            end=Position(
                                line=line, character=(reference_line.find(token) + len(token))
                            ),
                        ),
                    )
                )
            else:
                locations.append(
                    Location(
                        uri=current_document.uri,
                        range=Range(
                            start=Position(line=line, character=0),
                            end=Position(line=line, character=len(reference_line)),
                        ),
                    )
                )

        return locations

    @server.feature(HOVER, HoverOptions())
    def get_hover(ls: GtirbLanguageServer, params: HoverParams) -> Optional[Hover]:
        """GTIRB listing hover request."""
        logger.debug(f"Hover request received uri: {params.text_document.uri}")
        ls.show_message_log(f"Hover request received uri: {params.text_document.uri}")
        if params.text_document.uri not in current_gtirbs:
            ls.show_message(f" {params.text_document.uri} has not been indexed yet.")
            return None
        ir = current_gtirbs[params.text_document.uri]
        (offset_by_line, line_by_offset) = current_indexes[params.text_document.uri]
        offset = offset_by_line.get(params.position.line)
        current_line = ls.workspace.get_document(params.text_document.uri).source.splitlines()[
            params.position.line
        ]

        auxdata = None
        if offset:  # Get auxdata associated with current offset
            auxdata = offset_to_auxdata(ir, offset)
            markup_kind = MarkupKind.PlainText
        if auxdata is None:
            function_name = parse_function_name(current_line)
            if function_name:
                decomp = function_decompilations(ir, function_name)
                if decomp:
                    auxdata = decomp
                    markup_kind = MarkupKind.Markdown
        if auxdata is None:
            if server.gtirb_types_imported:
                # Types are supported so lets see if the thing being hovered over is
                # a function for which we have a prototype. But preload functionNames, if
                # that is empty no reason to continue.
                token: str = isolate_token(current_line, params.position.character)
                if len(token) > 0:
                    function_name = token[:-4] if token.endswith("@PLT") else token
                    types = GtirbTypes(ir.modules[0])
                    prototype_table = load_prototype_table(ir, types, c_str)
                    if function_name in prototype_table:
                        auxdata = prototype_table[function_name]
                        markup_kind = MarkupKind.PlainText

        if auxdata:
            logger.debug(f"Returning auxdata: {auxdata}")
            return Hover(contents=MarkupContent(kind=markup_kind, value=auxdata))
        else:
            logger.debug("No auxdata found")
            return Hover(
                contents=MarkupContent(kind=MarkupKind.PlainText, value="No auxdata found")
            )

    return server


def run_gtirb_server(mode: str, host: str = None, port: int = None) -> any:
    """Start the language server"""
    while True:
        server = create_gtirb_server_instance()
        if mode == "tcp":
            server.set_remote(host, port)
            server.start_tcp(host, port)
        elif mode == "stdio_remote":
            global force_remote
            force_remote = True
            server.start_io()
        elif mode == "stdio":
            server.start_io()
        else:
            logger.error(f"unrecognized transport: {mode}, should be tcp or stdio")
            sys.exit(0)

        # To reach this part of the loop, the server must have exited,
        # if this was by keyboard interrupt, exit the program,
        # otherwise start a new server.
        if not server.lsp._shutdown:
            logger.debug("keyboard interrupt, exiting...")
            sys.exit(1)
        del server
        logger.debug("server restarting...")
