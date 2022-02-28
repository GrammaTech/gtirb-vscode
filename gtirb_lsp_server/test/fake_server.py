"""
Provide a fake pygls infrastructure to test server LSP features.
"""

from typing import Text
from pathlib import Path
from unittest.mock import Mock
from pygls.workspace import Document, Workspace

DATA_DIR = Path(__file__).parent / "data"


def read_text_file(path: Path) -> Text:
    """Return the text in the file at the given path."""
    with open(path, "r") as f:
        return f.read()


class FakeTransport:
    get_extra_info = None


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


class FakeServer:
    """Use mocks for the methods provided by pygls."""

    show_message = None
    show_message_log = None
    is_remote = None
    can_rewrite = None

    def __init__(self):
        self.workspace = Workspace("", None)
        self.show_message = Mock()
        self.show_message_log = Mock()
        self.is_remote = Mock(return_value=False)
        self.lsp = FakeProtocol()

    def reset_mocks(self):
        self.show_message.reset_mock()
        self.show_message_log.reset_mock()
