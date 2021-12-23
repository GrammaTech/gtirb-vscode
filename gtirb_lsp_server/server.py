# -*- coding: utf-8 -*-

import json
import logging
import os
import re
import uuid
from typing import Dict, List, Optional, Set, Tuple, Union

import gtirb
import gtirb_functions
import gtirb_rewriting
import mcasm

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


X86Syntax = mcasm.X86Syntax

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
# The text in the documents.
current_documents = {}

#
# Offsets with pending edits.
modified_blocks = {}


# Local class allows addition  of a configuration section
# See pygls example: json language server
class GtirbLanguageServer(LanguageServer):
    CONFIGURATION_SECTION = "gtirbServer"
    CMD_GET_LINE_FROM_ADDRESS = "getLineFromAddress"

    def __init__(self):
        super().__init__()


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


def offset_to_auxdata(ir: gtirb, offset: gtirb.Offset) -> Optional[str]:
    result = ""
    for name in offset_indexed_aux_data(ir):
        data = ir.modules[0].aux_data[name].data.get(offset)
        if data:
            result += f"{name}: {data}\n"

    if result == "":
        return None
    else:
        return result


def offset_to_predecessors(ir: gtirb, offset: gtirb.Offset) -> Optional[List[gtirb.Offset]]:
    return map(lambda edge: gtirb.Offset(edge.source, 0), ir.cfg.in_edges(offset.element_id))


def offset_to_successors(ir: gtirb, offset: gtirb.Offset) -> Optional[List[gtirb.Offset]]:
    return map(lambda edge: gtirb.Offset(edge.target, 0), ir.cfg.out_edges(offset.element_id))


def all_symbolic_expressions(ir: gtirb) -> Set[Tuple[int, gtirb.SymbolicExpression]]:
    return {
        ((byte_interval.address + symbolic_expression[0]), symbolic_expression[1])
        for byte_interval in ir.modules[0].byte_intervals
        for symbolic_expression in byte_interval.symbolic_expressions.items()
    }


def symbolic_references(
    ir: gtirb, symbols: Union[gtirb.Symbol, List[gtirb.Symbol]]
) -> List[Tuple[int, gtirb.SymbolicExpression]]:
    if isinstance(symbols, gtirb.Symbol):
        uuid = symbols.uuid
        return filter(lambda pair: pair[1].symbol.uuid == uuid, all_symbolic_expressions(ir))
    else:
        uuids = list(map(lambda s: s.uuid, symbols))
        return filter(lambda pair: pair[1].symbol.uuid in uuids, all_symbolic_expressions(ir))


def offsets_at_references(
    ir: gtirb, references: List[Tuple[int, gtirb.SymbolicExpression]]
) -> List[Tuple[gtirb.Offset, gtirb.SymbolicExpression]]:
    results = []
    for (address, symbolic_expression) in references:
        for block in ir.modules[0].byte_blocks_on(address):
            results.append(
                (
                    gtirb.Offset(element_id=block, displacement=((address - block.address) - 1)),
                    symbolic_expression,
                )
            )
    return results


def block_byte_interval(module, thisblock):
    for section in module.sections:
        for byte_interval in section.byte_intervals:
            for block in byte_interval.blocks:
                if block == thisblock:
                    return byte_interval
    return None


def first_line_for_uuid(offset_by_line: Dict[int, gtirb.Offset], uuid: uuid.UUID) -> Optional[int]:
    return sorted(
        map(
            lambda pair: pair[0],
            filter(lambda pair: pair[1].element_id.uuid == uuid, offset_by_line.items()),
        )
    )[0]


def blocks_for_function_name(ir: gtirb, name: str) -> Optional[Set[gtirb.ByteBlock]]:
    for block_uuid, symbol in ir.modules[0].aux_data["functionNames"].data.items():
        if symbol.name == name:
            return ir.modules[0].aux_data["functionBlocks"].data.get(block_uuid)
    return None


def first_line_for_blocks(
    offset_by_line: Dict[int, gtirb.Offset], blocks: Set[gtirb.ByteBlock]
) -> List[int]:
    return sorted(map(lambda b: first_line_for_uuid(offset_by_line, b.uuid), blocks))[0]


def block_lines(line_by_offset: Dict[gtirb.Offset, int], block: gtirb.ByteBlock) -> List[int]:
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
    return "\n".join(
        list(
            map(lambda l: asm_lines[l].split("#")[0].rstrip(), block_lines(line_by_offset, block),)
        )
    )


def symbol_for_name(ir: gtirb, name: str) -> Optional[gtirb.Symbol]:
    return next(map(lambda s: s, filter(lambda s: s.name == name, ir.modules[0].symbols)))


#
# chars to strip out so as to leave a line consisting of actual tokens
delims = ["+", "-", "[", "]", ":", "{", "}", "*", ","]


def replace_delims(line):
    for ch in delims:
        line = line.replace(ch, " ")
    return line


def isolate_token(line: str, pos: int) -> str:
    if pos < 0 or pos >= len(line):
        return ""
    p = re.compile("[^ \t\n\r\f\v]+")
    for m in p.finditer(replace_delims(line)):
        if pos >= m.start() and pos <= m.start() + len(m.group()):
            return m.group()
    return ""


def preceding_function_line(current_lines: StringList, name: str, line: int) -> Optional[int]:
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
        for i in range(block.size):
            address_to_uuid_displacement[block.address + i] = (block.uuid, i)

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


def ensure_index(text_document):
    logger.debug(f"ensure_index({text_document.uri})")
    path_list = text_document.uri.split("//")

    if len(path_list) > 1 and path_list[0] == "file:":
        asmfile = path_list[1]
        cachedir = os.path.dirname(os.path.dirname(asmfile))
        cachedir_base = os.path.basename(cachedir)
        if cachedir_base.startswith(".vscode."):
            gtirbfile_base = cachedir_base[8:]
            gtirbfile = os.path.join(os.path.dirname(cachedir), gtirbfile_base)
            logger.info(f"gtirbfile: {gtirbfile}")
            jsonfile = asmfile + ".json"
    else:
        logger.error(f"error in text document path: {text_document.uri}")
        return

    try:
        ir = gtirb.IR.load_protobuf(gtirbfile)
        current_gtirbs[text_document.uri] = ir
    except Exception as inst:
        logger.error(inst)
        logger.error("Unable to load gtirb file %s." % gtirbfile)
        return

    line_offsets = None
    if os.path.exists(jsonfile):
        try:
            logger.info(f"Loading (line-number,offset(UUID,int)) map from JSON file: {jsonfile}")
            # Convert UUIDs back from hex to UUIDs.
            line_offsets = list(
                map(
                    lambda el: (el[0], (uuid.UUID(hex=el[1][0]), el[1][1])),
                    json.load(open(jsonfile, "r")),
                )
            )
        except Exception:
            logger.info(f"Failed to load JSON file: {jsonfile}")
            line_offsets = None

    if line_offsets is None:
        logger.info(f"Populating (line-number,offset(UUID,int)) map to JSON file: {jsonfile}")
        # this document should already be in current_documents, use it if possible
        if text_document.uri in current_documents:
            current_lines = current_documents[text_document.uri]
        else:
            current_lines = text_document.text.splitlines()
        line_offsets = get_line_offset(ir, current_lines)

        # Store the resulting map into a JSON file.
        logger.debug(f"line_offsets => {line_offsets}")
        json.dump(line_offsets, open(jsonfile, "w"), cls=UUIDEncoder)

    # Create maps from line_uuids going both ways.
    current_indexes[text_document.uri] = line_offsets_to_maps(ir, line_offsets)


server = GtirbLanguageServer()


@server.command(GtirbLanguageServer.CMD_GET_LINE_FROM_ADDRESS)
async def get_line_from_address(ls, *args):
    """Get the line number for an address for a document"""
    document_uri = args[0][0][2]
    address_str = args[0][1]
    logger.info(f"Command: get_line_from_address, uri: {document_uri}")
    if document_uri not in current_documents:
        ls.show_message(f" No address mapping for {document_uri}")
        return None
    try:
        address = int(address_str, 16)
    except Exception:
        logger.info(f"get_line_from_address: invalid address {address_str}")
        return None
    ir = current_gtirbs[document_uri]
    for block in ir.modules[0].byte_blocks_on(address):
        offset = gtirb.Offset(
            element_id=ir.get_by_uuid(block.uuid), displacement=(address - block.address)
        )
        line = current_indexes[document_uri][1].get(offset)
        text_line = current_documents[document_uri][line]
        if line:
            range = Range(
                start=Position(line=line, character=0),
                end=Position(line=line, character=(len(text_line))),
            )
            return range
    # If no line found, send message to UI
    ls.show_message(f" no line found for {address_str}")
    return None


def apply_changes_to_indexes(
    offset_by_line: Dict[int, gtirb.Offset],
    line_by_offset: Dict[gtirb.Offset, int],
    changes: List[Tuple[int, int, str]],
) -> Tuple[Dict[int, gtirb.Offset], Dict[gtirb.Offset, int], Set[gtirb.Offset]]:

    for start, end, text in changes:
        new_count = len(text.splitlines())
        old_count = (end + 1) - start
        growth = new_count - old_count

        def update_line(line):
            if line < start:
                return line
            if line > end:
                return line + growth
            if line < (start + min(new_count, old_count)):
                return line
            return None

        new_offset_by_line = {}
        new_line_by_offset = {}

        lines = sorted(offset_by_line.keys())
        for line in range(min(lines), max(lines) + growth):
            new_line = update_line(line)
            new_offset = offset_by_line.get(new_line)
            if new_line and new_offset:
                new_offset_by_line[new_line] = new_offset
                new_line_by_offset[new_offset] = new_line

        offset_by_line = new_offset_by_line
        line_by_offset = new_line_by_offset

    return (new_offset_by_line, line_by_offset)


@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(server: GtirbLanguageServer, params: DidChangeTextDocumentParams):
    """Text document did change notification."""
    uri = params.text_document.uri
    logger.info(f"Text Document Did Change notification, {params.text_document.uri}")
    if uri not in modified_blocks:
        modified_blocks[uri] = set()

    if uri not in current_indexes:
        server.show_message(f"document {uri} not in indexes")
        return None
    (offset_by_line, line_by_offset) = current_indexes[uri]

    # Track the blocks modified by the edit.
    for change in params.content_changes:
        for line in range(change.range.start.line, change.range.end.line + 1):
            offset = offset_by_line.get(line)
            logger.info(f"offset {offset} for edit line {line}")
            if offset:
                if offset.element_id not in modified_blocks[uri]:
                    asm = block_text(
                        line_by_offset, offset.element_id, server.workspace.get_document(uri).lines,
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

    logger.info(f"{len(modified_blocks[uri])} blocks for {len(params.content_changes)} edits")

    # TODO: Update the lines<->offset map as the lines change.
    # - get the affected lines from the range
    # - update all lines in the line<->offset map appropriately

    # Could consider updating the spaces in time to ensure the column
    # offset of the address stays consistent.


@server.feature(TEXT_DOCUMENT_DID_SAVE)
async def did_save(server: GtirbLanguageServer, params: DidSaveTextDocumentParams):
    """Text document did save notification."""
    uri = params.text_document.uri
    logger.info(f"Text Document Did Save notification, uri: {uri}")
    workspace = server.workspace
    document = workspace.get_document(uri)
    logger.debug(f"document {document} with {len(document.lines)} lines")

    if (uri not in modified_blocks) or len(modified_blocks[uri]) == 0:
        server.show_message(f"no pending modifications to {uri}")
        return None

    if uri not in current_gtirbs:
        server.show_message(f"no GTIRB found for {uri}")
        return None
    ir = current_gtirbs[uri]

    logger.info(f"applying {len(modified_blocks[uri])} modifications to {uri}")

    functions = gtirb_functions.Function.build_functions(ir.modules[0])
    blocks_to_functions = {block: func for func in functions for block in func.get_all_blocks()}
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
            logger.info("TODO: implement block deletion in gtirb-rewriting")
            server.show_message(f"skipping {block} with empty assembly")
        else:
            logger.debug(f"rewriting {block} to asm:\n{asm}")
            blocks += [block]
            ctx.replace_at(blocks_to_functions[block], block, 0, block.size, literal_patch(asm))

    try:
        if len(blocks) > 0:
            ctx.apply()
            ir.save_protobuf(uri.split("//")[1] + ".gtirb")
            server.show_message("GTIRB rewritten successfully")
        else:
            server.show_message("No blocks to rewrite")
    except Exception as e:
        server.show_message(f"assembly error: {e}")

    # TODO:
    # - Update the text with gtirb-pprinter
    #   - Return updated text
    #   - Distinguish between modified comments and modified assembly
    #   - Improved warnings when trying to delete blocks
    #   - Retain comments (in a new AuxData in the GTIRB)


@server.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls: GtirbLanguageServer, params: DidOpenTextDocumentParams):
    """Text document did open notification."""
    logger.info(f"Text Document Did Open notification, uri: {params.text_document.uri}")
    splitpath = os.path.splitext(params.text_document.uri)
    ext = splitpath[1]

    # This is where to check the extension
    if ext == ".gtasm":
        current_documents[params.text_document.uri] = params.text_document.text.splitlines()
        logger.info("Added to document list")
        ensure_index(params.text_document)
        logger.info("finished indexing")


@server.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(ls: GtirbLanguageServer, params: DidCloseTextDocumentParams):
    """Text document did close notification."""
    logger.info(f"Text Document Did Close notification, uri: {params.text_document.uri}")
    if params.text_document.uri in current_documents:
        del current_documents[params.text_document.uri]
        del current_indexes[params.text_document.uri]
        del current_gtirbs[params.text_document.uri]
        logger.info("removed document from list of current documents")


@server.feature(DEFINITION, DefinitionOptions())
def get_definition(ls: GtirbLanguageServer, params: DefinitionParams) -> Optional[Location]:
    """Text document definition request."""
    logger.info(f"Definition request received uri: {params.text_document.uri}")
    current_lines: StringList = []
    current_token: str
    #
    # Make sure the document is current
    if (
        params.text_document.uri in current_documents
        and params.text_document.uri in current_indexes
        and params.text_document.uri in current_gtirbs
    ):
        current_lines = current_documents[params.text_document.uri]
        current_token = isolate_token(
            current_lines[params.position.line], params.position.character
        )
        if current_token is None or len(current_token) == 0:
            ls.show_message(
                f" no token found for {params.position.line}:{params.position.character}"
            )
            return None
    else:
        ls.show_message(
            f" document {params.text_document.uri} is not in the current document store."
        )
        return None

    ir = current_gtirbs[params.text_document.uri]
    if ir is None:
        ls.show_message(" document {params.text_document.uri} has no GTIRB.")
        return None
    logger.debug("ir found")

    symbol = symbol_for_name(ir, current_token)
    if symbol is None:
        ls.show_message(f" symbol for {current_token} not found.")
        return None
    logger.debug(f"symbol found: {symbol}")

    line = first_line_for_uuid(current_indexes[params.text_document.uri][0], symbol.referent.uuid)
    if line is None:
        ls.show_message(f" no line for uuid {symbol.referent}.")
        return None
    logger.debug(f"line found: {line}")

    line = preceding_function_line(current_lines, current_token, line)
    definition_line: str = current_lines[line]

    return Location(
        uri=params.text_document.uri,
        range=Range(
            start=Position(line=line, character=definition_line.find(current_token)),
            end=Position(
                line=line, character=(definition_line.find(current_token) + len(current_token))
            ),
        ),
    )


@server.feature(REFERENCES, ReferenceOptions())
def get_references(ls: GtirbLanguageServer, params: ReferenceParams) -> Optional[List[Location]]:
    """Text document references request."""
    logger.info(f"References request received uri: {params.text_document.uri}")
    current_lines: StringList = []
    current_token: str
    locations: LocationList = []
    #
    # Make sure the document is current
    if (
        params.text_document.uri in current_documents
        and params.text_document.uri in current_indexes
        and params.text_document.uri in current_gtirbs
    ):
        (offset_by_line, line_by_offset) = current_indexes[params.text_document.uri]
        current_lines = current_documents[params.text_document.uri]
        current_token = isolate_token(
            current_lines[params.position.line], params.position.character
        )
        if current_token is None or len(current_token) == 0:
            ls.show_message(
                f" no token found for {params.position.line}:{params.position.character}"
            )
            return None
    else:
        ls.show_message(
            f" document {params.text_document.uri} is not in the store of current documents."
        )
        return None

    ir = current_gtirbs[params.text_document.uri]
    if ir is None:
        ls.show_message(f" document {params.text_document.uri} has no GTIRB.")
        return None
    logger.debug("ir found")

    # If token is a GTIRB symbol, find references to it,
    # otherwise find references to whatever block the cusor is in
    symbol = symbol_for_name(ir, current_token)
    if symbol is None:
        reference_line = params.position.line
    else:
        reference_line = first_line_for_uuid(offset_by_line, symbol.referent.uuid)

    offset = offset_by_line.get(reference_line)
    if offset is None:
        ls.show_message(f" no offset found for line {reference_line}.")
        return None
    logger.debug(f"offset found: {offset}")

    references = list(symbolic_references(ir, offset.element_id.references))
    if len(references) == 0:
        ls.show_message(f" no references found for {offset}.")
        return None
    logger.debug(f"references found: {references}")

    offsets_and_symbolic_expressions = offsets_at_references(ir, references)
    if len(offsets_and_symbolic_expressions) == 0:
        ls.show_message(f" no offsets found for {references}.")
        return None
    logger.debug(f"offsets found: {offsets_and_symbolic_expressions}")

    lines_and_symbolic_expressions = list(
        filter(
            lambda it: isinstance(it[0], int),
            map(
                lambda off_and_se: (offset_to_line(line_by_offset, off_and_se[0]), off_and_se[1],),
                offsets_and_symbolic_expressions,
            ),
        )
    )
    if len(lines_and_symbolic_expressions) == 0:
        ls.show_message(f" no lines for offsets {offsets_and_symbolic_expressions}.")
        return None
    logger.debug(f"lines found: {lines_and_symbolic_expressions}")

    for (line, symbolic_expression) in lines_and_symbolic_expressions:
        reference_line: str = current_lines[line]
        token = None
        for sym in symbolic_expression.symbols:
            if reference_line.find(sym.name):
                token = sym.name
        if token:
            locations.append(
                Location(
                    uri=params.text_document.uri,
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
                    uri=params.text_document.uri,
                    range=Range(
                        start=Position(line=line, character=0),
                        end=Position(line=line, character=len(reference_line)),
                    ),
                )
            )

    return locations


@server.feature(HOVER, HoverOptions())
def get_hover(ls: GtirbLanguageServer, params: HoverParams) -> Optional[Hover]:
    logger.info(f"Hover request received uri: {params.text_document.uri}")
    (offset_by_line, line_by_offset) = current_indexes[params.text_document.uri]
    offset = offset_by_line.get(params.position.line)
    if offset:
        auxdata = offset_to_auxdata(current_gtirbs[params.text_document.uri], offset)
    else:
        auxdata = None

    if auxdata is None:
        logger.debug("No auxdata found")
        return Hover(contents=MarkupContent(kind=MarkupKind.PlainText, value="No auxdata found"))
    else:
        logger.debug(f"Returning auxdata: {auxdata}")
        return Hover(contents=MarkupContent(kind=MarkupKind.PlainText, value=auxdata))


def offset_indexed_aux_data(ir: gtirb) -> List[str]:
    results = []
    for (name, value) in ir.modules[0].aux_data.items():
        if not isinstance(value.data, dict):
            continue
        if not value.data or not isinstance(list(value.data.keys())[0], gtirb.Offset):
            continue
        results += [name]
    return results


def gtirb_tcp_server(host: str, port: int) -> None:
    server.start_tcp(host, port)


def gtirb_stdio_server() -> None:
    server.start_io()
