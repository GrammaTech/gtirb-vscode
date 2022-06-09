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
Test the get_definition LSP feature
"""

# NOTE:
# - line numbering starts at zero in the listing file
# - cursor location is specified as [ line, character ]
# - definition location is specified as [ line, startchar, endchar ]

import pytest
from unittest.mock import Mock

from pygls.lsp.types import (
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    DefinitionParams,
    TextDocumentItem,
    Position,
)

from gtirb_lsp_server.tests.fake_server import FakeServer, FakeDocument

# Create a fake server
server = FakeServer()
fake_document = FakeDocument()
server.workspace.get_document = Mock(return_value=fake_document.document)
text_document_item = TextDocumentItem(
    uri=fake_document.document_uri,
    language_id="gtgas",
    version=1,
    text=str(fake_document.asmtext),
)


@pytest.mark.asyncio
async def test_get_definition_success():
    """
    Open the document and get definition
    """
    server.reset_mocks()

    # Testing a particular definition in this file:
    # The symbol "printBody":
    # - Identified by cursor location: line 778, character 21
    # - Should return this defintion location:
    #   - line 372, characters 35 to 42
    cursor = [778, 21]
    definition = [351, 0, 9]

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=text_document_item)
    await server.did_open(openParams)

    # Call server.get_definition()
    defParams = DefinitionParams(
        text_document=text_document_item,
        position=Position(line=cursor[0], character=cursor[1]),
    )
    response = server.get_definition(defParams)

    # Verify result
    definition_found = False
    if [
        response.range.start.line,
        response.range.start.character,
        response.range.end.character,
    ] == definition:
        definition_found = True
    assert definition_found is True

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(text_document=text_document_item)
    server.did_close(closeParams)


@pytest.mark.asyncio
async def test_get_definition_fail_no_document():
    """
    Test trying to get definition when document isn't open
    """
    server.reset_mocks()
    cursor = [778, 21]

    # Call server.get_definition()
    defParams = DefinitionParams(
        text_document=text_document_item,
        position=Position(line=cursor[0], character=cursor[1]),
    )
    response = server.get_definition(defParams)
    assert response is None


@pytest.mark.asyncio
async def test_get_definition_fail_no_token():
    """
    Test trying to get a definition when the cursor is not in a token
    """
    server.reset_mocks()

    # Testing cursor not in a token
    # - Identified by cursor location: line 300, character 5
    # - Should return None
    cursor = [300, 5]

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=text_document_item)
    await server.did_open(openParams)

    # Call server.get_definition()
    defParams = DefinitionParams(
        text_document=text_document_item,
        position=Position(line=cursor[0], character=cursor[1]),
    )
    response = server.get_definition(defParams)
    assert response is None

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(text_document=text_document_item)
    server.did_close(closeParams)


@pytest.mark.asyncio
async def test_get_definition_fail_no_symbol():
    """
    Test trying to get a definition when the token is not a GTIRB symbol
    """
    server.reset_mocks()

    # Testing cursor in a token that is not a GTIRB symbol
    # - Identified by cursor location: line 300, character 20
    # - Should return None
    cursor = [300, 20]

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=text_document_item)
    await server.did_open(openParams)

    # Call server.get_definition()
    defParams = DefinitionParams(
        text_document=text_document_item,
        position=Position(line=cursor[0], character=cursor[1]),
    )
    response = server.get_definition(defParams)
    assert response is None

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(text_document=text_document_item)
    server.did_close(closeParams)


@pytest.mark.asyncio
async def test_get_definition_fail_no_definition():
    """
    Test trying to get a definition when the token is a GTIRB symbol
    that is not defined in the listing
    """
    server.reset_mocks()

    # Testing a particular definition in this file:
    # The symbol "__init_array_start":
    # - Identified by cursor location: line 1306, character 5
    # - Should return None
    cursor = [1306, 5]

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=text_document_item)
    await server.did_open(openParams)

    # Call server.get_definition()
    defParams = DefinitionParams(
        text_document=text_document_item,
        position=Position(line=cursor[0], character=cursor[1]),
    )
    response = server.get_definition(defParams)
    assert response is None

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(text_document=text_document_item)
    server.did_close(closeParams)
