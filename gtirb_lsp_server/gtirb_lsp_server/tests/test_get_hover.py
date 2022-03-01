"""
Test the hover LSP feature
"""

# NOTE:
# - line numbering starts at zero in the listing file
# - cursor location is specified as [ line, character ]

import pytest
from unittest.mock import Mock

from pygls.lsp.types import (
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    HoverParams,
    TextDocumentIdentifier,
    TextDocumentItem,
    Position,
)
from gtirb_lsp_server.server import did_open, did_close, get_hover
from gtirb_lsp_server.tests.fake_server import FakeServer, FakeDocument

# Create a fake server
server = FakeServer()
fake_document = FakeDocument()
server.workspace.get_document = Mock(return_value=fake_document.document)


@pytest.mark.asyncio
async def test_get_hover_success():
    """
    Open the document and get hover
    """
    server.reset_mocks()

    # Testing for particular hover response in the test document:
    # - Cursor location: line 372, character 17
    # - Expected response is a string:
    #   "comments: RAX=X*0+163c type(complete), RAX=(NONE,0xf63)*0+163c\n"
    cursor = [372, 17]
    expected_hover = "comments: RAX=X*0+163c type(complete), RAX=(NONE,0xf63)*0+163c\n"

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

    # Call server.get_hover()
    hoverParams = HoverParams(
        text_document=TextDocumentItem(
            uri=fake_document.document_uri,
            language_id="gtgas",
            version=1,
            text=str(fake_document.asmtext),
        ),
        position=Position(line=cursor[0], character=cursor[1]),
    )

    response = get_hover(server, hoverParams)
    assert response.contents.value == expected_hover

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=fake_document.document_uri)
    )
    did_close(server, closeParams)
