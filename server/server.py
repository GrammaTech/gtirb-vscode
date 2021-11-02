# -*- coding: utf-8 -*- 

import os
import json
import logging
import argparse
import gtirb
import re
from collections import defaultdict
from typing import List, Optional, Union
from pygls.server import LanguageServer
from pygls.protocol import LanguageServerProtocol
from pygls.lsp.methods import (
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_CLOSE,
    TEXT_DOCUMENT_DID_SAVE,
    TEXT_DOCUMENT_DID_CHANGE,
    DEFINITION,
    REFERENCES
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
    ReferenceContext
)

logger = logging.getLogger(__name__)

DEFAULT_PORT = 3036
DEFAULT_TCP_FLAG = False
DEFAULT_STDIO_FLAG = True

StringList = List[str]
LocationList = List[Location]

current_indexes = {} # not sure defaultdict would support factory of TextDocument?
current_documents = {} # not sure defaultdict would support factory of TextDocument?

#
# Local class allows addition  of a configuration section
# See pygls example: json language server
class GtirbLanguageServer(LanguageServer):
    CONFIGURATION_SECTION = 'gtirbServer'

    def __init__(self):
        super().__init__()


class Index:

    def __init__ (self, gtirbfile=None, asm=None, xref=None, defs=None):
        self.gtirbfile = gtirbfile
        self.asm = asm
        self.xref = xref
        self.defs = defs

    def dump_to_file (self, json_filename):
        x = {
            "gtirb": self.gtirbfile,
            "asm": self.asm,
            "xref": self.xref,
            "defs": self.defs
        }
        try:
            with open(json_filename, "w") as outfile:
                json.dump(x, outfile, indent=4)
        except Exception as inst:
            logger.error(f"unable to write to JSON file: {json_filename}")

    def load_from_file (self, json_filename):
        try:
            with open(json_filename) as infile:
                x = json.load(infile)
        except Exception as inst:
            logger.error(f"unable to read from JSON file: {json_filename}")
        else:
            self.gtirbfile = x["gtirb"]
            self.asm = x["asm"]
            self.xref = x["xref"]
            self.defs = x["defs"]


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
    p = re.compile('\S+')
    for m in p.finditer(replace_delims(line)):
        if pos >= m.start() and pos < m.start()+len(m.group()):
            return m.group()
    return ""


def do_indexing(text_document):
    path_list = text_document.uri.split('//')

    lines = text_document.text.splitlines()

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

    if os.path.exists(jsonfile):
        logger.info(f"Reusing indexing from JSON file: {jsonfile}")
        index = Index()
        index.load_from_file(jsonfile)

    else:

        # 
        # Get list of symbols from GTIRB file
        try:
            ir = gtirb.IR.load_protobuf(gtirbfile)
        except Exception as inst:
            logger.error(inst)
            logger.error("Unable to load gtirb file %s." % gtirbfile)
            return
    
        modules = ir.modules
        module = next(iter(modules))
        symbols = module.symbols
        symlist = []
        for symbol in symbols:
            symlist.append(symbol.name)

        # if this is a definition, a symbol followed by a colon is the whole line
        def_search = re.compile('^.*:$')

        #
        # Process the assembly code line by line
        defs = {}
        xref = defaultdict(list)
        for i, line in enumerate(lines):
            if def_search.match(line) != None:
                defined_symbol = line[:-1]
                if defined_symbol in symlist:
                    defs[defined_symbol] = i
    
            # parse the tokens to see if any are a symbol
            for word in replace_delims(line).split():
                if word in symlist:
                    xref[word].append(i)

        index = Index(gtirbfile, asmfile, xref, defs)
        index.dump_to_file(jsonfile) 

    #
    # Add to current indexes
    current_indexes[text_document.uri] = index
        

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
    #if ext == '.gtx86' or ext == '.gtx64' or ext == '.gtmips' or ext == '.gtarm':
    if ext == '.gtasm':
        current_documents[params.text_document.uri] = params.text_document
        logger.info('Added to document list')
        do_indexing(params.text_document)
        logger.info('finished indexing')


@server.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(ls, params: DidCloseTextDocumentParams):
    """Text document did close notification."""
    logger.info(f"Text Document Did Close notification, uri: {params.text_document.uri}")
    if params.text_document.uri in current_documents:
        #del current_documents[params.text_document.uri]
        logger.info("document is in current list, you should have removed it just now?")

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
        #Load the cached index here if it exists?
        ls.show_message(f" document {params.text_document.uri} is not in the currrent document store.")
        return None

    if params.text_document.uri in current_indexes:
        index = current_indexes[params.text_document.uri]
        if current_token in index.defs:
            adef = index.defs[current_token]
        else:
            return None
        #Expecting only one def
        definition_line: str = current_lines[adef]
        location = Location(
            uri = params.text_document.uri,
            range = Range(
                start = Position(line = adef,
                    character = definition_line.find(current_token)),
                end = Position(line = adef,
                    character = definition_line.find(current_token) + len(current_token))))
    else:
        ls.show_message(f" document {params.text_document.uri} is not in the currrent index store.")
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
        #Check if cache exists ono file system?
        ls.show_message(f" document {params.text_document.uri} is not in the currrent document store.")
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
        ls.show_message(f" document {params.text_document.uri} is not in the currrent index store.")
        return None

    return locations 


def gtirb_tcp_server(host: str, port: int) -> None:
    server.start_tcp(host, port)


def gtirb_stdio_server() -> None:
    server.start_io()

