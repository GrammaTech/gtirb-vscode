"""
Test opening and closing documents of the LSP server using a mocked server instance
"""

import os
import pytest
from pathlib import Path
from unittest.mock import Mock

from pygls.lsp.types import (
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    TextDocumentItem,
)
from gtirb_lsp_server.server import did_open, did_close
from gtirb_lsp_server.tests.fake_server import FakeServer, FakeDocument

# Create a fake server
server = FakeServer()
fake_document = FakeDocument()
server.workspace.get_document = Mock(return_value=fake_document.document)
text_document_item = TextDocumentItem(
    uri=fake_document.document_uri, language_id="gtgas", version=1, text=str(fake_document.asmtext),
)

index_path = Path(str(fake_document.asm_path) + ".json")


@pytest.mark.asyncio
async def test_did_open_did_close():
    """
    Open the document, generate indexes for it, then close it.
    """
    server.reset_mocks()

    # We want to test the index is generated,
    # so if there is one already there, delete it.
    if index_path.exists():
        index_path.unlink()

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=text_document_item)
    await did_open(server, openParams)

    # Verify open:
    # - Always sends message when indexing is complete
    # - Check that thre file was created
    server.show_message.assert_called_once()
    assert index_path.exists()

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(text_document=text_document_item)
    did_close(server, closeParams)

    # If everything went right, show_message_log should
    # have been called exactly 3 times
    assert server.show_message_log.call_count == 3

    # Opening the same document again should resuse the index
    server.reset_mocks()
    filename = os.path.split(fake_document.document.uri)[1]
    await did_open(server, openParams)
    server.show_message_log.assert_called_with(f"re-using indexes for {filename}")
    did_close(server, closeParams)


@pytest.mark.asyncio
async def test_open_fail_bad_uri():
    """
    Test calling open with a bad uri
    """
    server.reset_mocks()

    bad_document_item = TextDocumentItem(
        uri="bad.view", language_id="gtgas", version=1, text=str(fake_document.asmtext),
    )

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=bad_document_item)
    with pytest.raises(Exception):
        await did_open(server, openParams)
