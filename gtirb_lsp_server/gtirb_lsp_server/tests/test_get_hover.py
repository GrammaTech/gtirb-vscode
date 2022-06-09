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
    await server.did_open(openParams)

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

    response = server.get_hover(hoverParams)
    assert response.contents.value == expected_hover

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=fake_document.document_uri)
    )
    server.did_close(closeParams)
