#!/usr/bin/env python3 
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

DEFAULT_PORT = 3036
DEFAULT_TCP_FLAG = True
DEFAULT_STDIO_FLAG = False

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

#
# Don't think I want this
class NonTerminatingLanguageServerProtocol(LanguageServerProtocol):
    """
    language server protocol implementation which ignores
    exit/shutdown/connection_lost messages from the client
    """

    def bf_exit(self, *args):
        pass

    def bf_shutdown(self, *args):
        pass

    def connection_lost(self, *args):
        pass

class Index:

    def __init__ (self, gtirbfile, asm, xref, defs):
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
            with open(json_filename, "w") as out:
                json.dump(x, out, indent=4)
        except Exception as inst:
            print(inst)
            print("Unable to write cross-reference file %s." % json_filename)
            quit()
        print("\nWrote cross reference file: %s.\n" % json_filename)

#
# chars to strip out so as to leave a line consisting of actual tokens
delims = ['+', '-', '[', ']', ':', '{', '}', '*', ',']
def replace_delims(line):
    for ch in delims:
        line = line.replace(ch, ' ')
    return line

def isolate_token(line, pos):
    if pos < 0 or pos > len(line):
        return None
    # Get the token at the position in the line indicated by pos
    # 1. replace all delimiters with spaces
    space_line = replace_delims(line)
    # 2. find beginning of token
    i = pos
    while space_line[i] != ' ' and i > 0:
        i = i - 1
    # (adjust: i is probably pointing to a space now)
    # (unless it went down to 0)
    if space_line[i] == ' ':
        i = i+1
    # 3. find end of token
    j = pos
    while space_line[j] != ' ' and j < len(space_line)-1:
        j = j + 1
    # (adjust: j could be pointing at the end of the string now)
    # (could be there is no space there)
    if j == len(space_line)-1 and space_line[len(space_line)-1] != ' ':
        j = j + 1
    # return the substring
    return line[i:j]


def do_indexing(text_document):
    path = text_document.uri.split('//')
    lines = text_document.text.splitlines()

    if len(path) > 1 and path[0] == 'file:':
        asmfile = path[1]
        gtirbfile = os.path.splitext(asmfile)[0];
        jsonfile = asmfile+'.json'
    else:
        print(f"error in text document path: {text_document.uri}")
        return

    #
    # Get list of symbols from GTIRB file
    try:
        ir = gtirb.IR.load_protobuf(gtirbfile)
    except Exception as inst:
        print(inst)
        print("Unable to load gtirb file %s." % gtirbfile)
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
            print("looking for %s..." % defined_symbol)
            if defined_symbol in symlist:
                defs[defined_symbol] = i
                print("found def of %s at %d" % (defined_symbol, i))
    
        # parse the tokens to see if any are a symbol
        for word in replace_delims(line).split():
            if word in symlist:
                #print("found reference to %s at line %d" % (word, i))
                xref[word].append(i)

    index = Index(gtirbfile, asmfile, xref, defs)
    index.dump_to_file(jsonfile) 

    #
    # Add to current indexes
    current_indexes[text_document.uri] = index
        

def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tcp",
        action="store_true",
        default=DEFAULT_TCP_FLAG,
        help="Run server in TCP mode.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Port to listen for requests on.",
    )
    parser.add_argument(
        "--stdio",
        action="store_true",
        default=DEFAULT_STDIO_FLAG,
        help="Run server in STDIO mode.",
    )

    args = parser.parse_args()
    logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

    #if args.stdio:
    #    server = LanguageServer()
    #else:
    #   server = LanguageServer(protocol_cls=NonTerminatingLanguageServerProtocol)
    # Use local class inheriting from LanguageServer, and drop the NonTerm
    server = GtirbLanguageServer()

    @server.feature(TEXT_DOCUMENT_DID_CHANGE)
    def did_change(ls, params: DidChangeTextDocumentParams):
        """Text document did change notification."""
        print(f"Text Document Did Change notification, uri: {params.text_document.uri}")
        # extraneous # return None


    @server.feature(TEXT_DOCUMENT_DID_OPEN)
    async def did_open(ls, params: DidOpenTextDocumentParams):
        """Text document did open notification."""
        print(f"Text Document Did Open notification, uri: {params.text_document.uri}")
        #print(params)
        #ext = os.path.splitext(params.text_document.uri)[1];
        splitpath = os.path.splitext(params.text_document.uri)
        ext = splitpath[1]
        print(f"scheme: {splitpath[0]}")
        print(f"ext: {ext}")
        print(splitpath)

        # This is where to check the extension
        if ext == '.gtx86' or ext == '.gtx64' or ext == '.gtmips' or ext == '.gtarm':
            current_documents[params.text_document.uri] = params.text_document
            print('Added to document list')
            do_indexing(params.text_document)
            print('finished indexing')


    @server.feature(TEXT_DOCUMENT_DID_CLOSE)
    def did_close(ls, params: DidCloseTextDocumentParams):
        """Text document did close notification."""
        print(f"Text Document Did Close notification, uri: {params.text_document.uri}")
        if params.text_document.uri in current_documents:
            #del current_documents[params.text_document.uri]
            ls.show_message("document is in current list, you should have removed it just now?")

    @server.feature(DEFINITION, DefinitionOptions())
    def get_definition(ls, params: DefinitionParams) -> Optional[Union[Location, List[Location], List[LocationLink]]]:
        """Text document definition request."""
        print(f"Definition request received uri: {params.text_document.uri}")
        print(f"position (line,char): {params.position.line},{params.position.character}")
        current_line: str = ""
        current_text: str = ""
        current_token: str = ""
        current_lines: StringList = []
        if params.text_document.uri in current_documents:
            text_document = current_documents[params.text_document.uri]
            current_text = text_document.text
            current_lines = current_text.splitlines()
            current_line = current_lines[params.position.line]
            print(f"seeing this line there: {current_line}")
            current_token = isolate_token(current_line, params.position.character)
            if current_token == None or len(current_token) == 0:
                print("Unable to isolate a token.")
                return None
            else:
                print(f"current token: {current_token}")
        else:
            print("document not in current documents store.")
            print("Should load it?")
            return None

        if params.text_document.uri in current_indexes:
            index = current_indexes[params.text_document.uri]
            if current_token in index.defs:
                adef = index.defs[current_token]
            else:
                print(f"don't see any defs for {current_token}")
                return None
            #Expecting only one def
            print(f"a def: {adef}")
            definition_line: str = current_lines[adef]
            print(f"this reference line: {definition_line}")
            location = Location(
                uri = params.text_document.uri,
                range = Range(
                    start = Position(line = adef,
                        character = definition_line.find(current_token)),
                    end = Position(line = adef,
                        character = definition_line.find(current_token) + len(current_token))))
        else:
            print("document not in current index store.")
            print("Could load and index it.")
            return None

        #print(params)
        return location 

# remove async ? test code does not have.
#    async def get_references(ls, params: ReferenceParams):
    # returns Optional[List[Location]]
    @server.feature(REFERENCES, ReferenceOptions())
    def get_references(ls, params: ReferenceParams) -> Optional[List[Location]]:
        """Text document references request."""
        print(f"References request received uri: {params.text_document.uri}")
        print(f"position (line,char): {params.position.line},{params.position.character}")
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
            print(f"seeing this line there: {current_line}")
            current_token = isolate_token(current_line, params.position.character)
            if current_token == None or len(current_token) == 0:
                print("Unable to isolate a token.")
                return None
            else:
                print(f"current token: {current_token}")
        else:
            print("document not in current documents store.")
            print("Should load it?")
            return None

        if params.text_document.uri in current_indexes:
            index = current_indexes[params.text_document.uri]
            refs = index.xref[current_token]
            if refs == None or len(refs) == 0:
                print(f"don't see any refs for {current_token}")
                return None
            for ref in refs:
                print(f"ref: {ref}")
                reference_line: str = current_lines[ref]
                print(f"this reference line: {reference_line}")
                locations.append(Location(
                    uri = params.text_document.uri,
                    range = Range(
                        start = Position(line = ref,
                            character = reference_line.find(current_token)),
                        end = Position(line = ref,
                            character = reference_line.find(current_token) + len(current_token)))))
        else:
            print("document not in current index store.")
            print("Could load and index it.")
            return None

        #print(params)
        return locations 

    # Spawn the server.
    if args.stdio:
        server.start_io()
    else:
        server.start_tcp("0.0.0.0", args.port)


if __name__ == "__main__":
    main()
