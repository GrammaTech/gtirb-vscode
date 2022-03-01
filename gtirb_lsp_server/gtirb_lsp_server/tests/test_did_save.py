"""
Test the did_change and did_save LSP features
"""

# NOTE:
# - line numbering starts at zero in the listing file
# - edit location is specified as [ line, startchar, endchar ]

import pytest
from unittest.mock import Mock

from pygls.lsp.types import (
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    DidChangeTextDocumentParams,
    DidSaveTextDocumentParams,
    TextDocumentContentChangeEvent,
    TextDocumentIdentifier,
    TextDocumentItem,
    Range,
    Position,
)
from gtirb_lsp_server.server import did_open, did_close, did_change, did_save
from gtirb_lsp_server.tests.fake_server import FakeServer, FakeDocument

# Create a fake server
server = FakeServer()
fake_document = FakeDocument()
server.workspace.get_document = Mock(return_value=fake_document.document)

try:
    import gtirb_functions
    import gtirb_rewriting
    import mcasm
except Exception as inst:
    server.can_rewrite = Mock(return_value=False)
    print(inst)
    print("Disabling rewriting.")
else:
    print("Enabling rewriting.")
    server.can_rewrite = Mock(return_value=True)


@pytest.mark.asyncio
async def test_did_save_success():
    """
    Open the document, do changes, and try to save.
    """
    server.reset_mocks()

    #
    # These are here to please flake8, otherwise
    # it complains of unsused imports.
    if server.can_rewrite():
        print(gtirb_functions.version)
        print(gtirb_rewriting.version)
        print(mcasm.version)

    # Testing for particular change in the test document:
    # - Cursor location: line 372, character 17
    edit_location = [525, 12, 23]
    edit_content = "mov EAX,0  "

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(
        text_document=TextDocumentItem(
            uri=fake_document.document_uri,
            language_id="gtgas",
            version=1,
            text=str(fake_document.asmtext),
        )
    )
    await did_open(server, openParams)

    # Call server.did_change()
    change = TextDocumentContentChangeEvent(
        range=Range(
            start=Position(line=edit_location[0], character=edit_location[1]),
            end=Position(line=edit_location[0], character=edit_location[2]),
        ),
        range_length=len(edit_content),
        text=edit_content,
    )
    changeParams = DidChangeTextDocumentParams(
        text_document=TextDocumentItem(
            uri=fake_document.document_uri,
            language_id="gtgas",
            version=1,
            text=str(fake_document.asmtext),
        ),
        content_changes=[change],
    )

    server.reset_mocks()
    did_change(server, changeParams)
    # If success there should be 2 log messages and no user messages
    assert server.show_message_log.call_count == 2
    assert server.show_message.call_count == 0

    # Call server.did_save() to process edit and rewrite file
    saveParams = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=fake_document.document_uri)
    )
    await did_save(server, saveParams)
    if server.can_rewrite():
        server.show_message.assert_called_once_with("GTIRB rewritten successfully")
    else:
        server.show_message.assert_called_once_with("GTIRB rewriting is disabled")

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=fake_document.document_uri)
    )
    did_close(server, closeParams)
