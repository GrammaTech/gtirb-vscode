"""
Provide a fake pygls infrastructure to test server LSP features.
"""

from typing import Text
from pathlib import Path
from unittest.mock import Mock
from pygls.workspace import Document, Workspace
from gtirb_lsp_server.server import GtirbLanguageServer, create_gtirb_server_instance

DATA_DIR = Path(__file__).parent / "data"


def read_text_file(path: Path) -> Text:
    """Return the text in the file at the given path."""
    with open(path, "r") as f:
        return f.read()


class FakeTransport:
    get_extra_info = None

    def __init__(self):
        self.write = Mock()


class FakeProtocol:
    transport = FakeTransport()


class FakeDocument:
    """Define a document to run tests with."""

    def __init__(self):
        # Set up paths for a test document
        self.gtirb_path = DATA_DIR.joinpath("hangman.gtirb")
        self.asm_path = (
            DATA_DIR.joinpath(".vscode.hangman.gtirb").joinpath("x64").joinpath("hangman.view")
        )
        self.index_path = Path(str(self.asm_path) + ".json")
        self.asmtext = read_text_file(self.asm_path)
        self.document_uri = "file://" + str(self.asm_path)
        self.document_content = self.asmtext
        self.document = Document(self.document_uri, self.document_content)


class FakeServer(GtirbLanguageServer):
    """Use mocks for the methods provided by pygls."""

    show_message = None
    show_message_log = None
    is_remote = None
    can_rewrite = None
    workspace = Workspace("", None)

    def __init__(self):
        GtirbLanguageServer.__init__(self)
        self.gtirb_server = create_gtirb_server_instance()
        self.did_open = self.gtirb_server.lsp.fm.features["textDocument/didOpen"]
        self.did_save = self.gtirb_server.lsp.fm.features["textDocument/didSave"]
        self.did_close = self.gtirb_server.lsp.fm.features["textDocument/didClose"]
        self.did_change = self.gtirb_server.lsp.fm.features["textDocument/didChange"]
        self.get_hover = self.gtirb_server.lsp.fm.features["textDocument/hover"]
        self.get_definition = self.gtirb_server.lsp.fm.features["textDocument/definition"]
        self.get_references = self.gtirb_server.lsp.fm.features["textDocument/references"]
        self.get_symbol_address = self.gtirb_server.lsp.fm.commands["gtirbGetAddressOfSymbol"]
        self.gtirb_server.lsp.workspace = Workspace("", None)
        self.gtirb_server.lsp.transport = FakeTransport()
        self.gtirb_server.show_message = Mock()
        self.gtirb_server.show_message_log = Mock()
        self.lsp = FakeProtocol()

    def reset_mocks(self):
        self.gtirb_server.show_message.reset_mock()
        self.gtirb_server.show_message_log.reset_mock()
