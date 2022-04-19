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
Test the get_references LSP feature
"""

# NOTE:
# - line numbering starts at zero in the listing file
# - cursor location is specified as [ line, character ]
# - reference locations are specified as [ line, startchar, endchar ]

import pytest
from unittest.mock import Mock

from pygls.lsp.types import (
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    ReferenceParams,
    ReferenceContext,
    TextDocumentItem,
    Position,
)
from gtirb_lsp_server.server import did_open, did_close, get_references
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
async def test_get_references_success():
    """
    Open the document and get references
    """
    server.reset_mocks()

    # Testing for particular references in this file:
    # the symbol ".L_163c"
    # - Identified by cursor location: line 862, character 1
    # - Should return two reference locations:
    #   - line 372, characters 35 to 42
    #   - line 369, characters 35 to 42
    cursor = [862, 1]
    reference1 = [369, 35, 42]
    reference2 = [372, 35, 42]

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=text_document_item)
    await did_open(server, openParams)

    # Call server.get_references()
    refParams = ReferenceParams(
        text_document=text_document_item,
        position=Position(line=cursor[0], character=cursor[1]),
        context=ReferenceContext(include_declaration=False),
    )

    references = get_references(server, refParams)

    # Verify the result
    # - Have to iterate through returned references, because they do not have deterministic ordering
    ref1found = False
    ref2found = False
    for ref in references:
        if [ref.range.start.line, ref.range.start.character, ref.range.end.character] == reference1:
            ref1found = True
        elif [
            ref.range.start.line,
            ref.range.start.character,
            ref.range.end.character,
        ] == reference2:
            ref2found = True

    assert ref1found is True
    assert ref2found is True

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(text_document=text_document_item)
    did_close(server, closeParams)


@pytest.mark.asyncio
async def test_get_references_fail_no_document():
    """
    Test trying to get references when document isn't open
    """
    server.reset_mocks()
    cursor = [862, 1]

    # Call server.get_references()
    refParams = ReferenceParams(
        text_document=text_document_item,
        position=Position(line=cursor[0], character=cursor[1]),
        context=ReferenceContext(include_declaration=False),
    )

    response = get_references(server, refParams)
    assert response is None


@pytest.mark.asyncio
async def test_get_references_fail_no_token():
    """
    Test trying to get references when the cursor is not in a token
    """
    server.reset_mocks()

    # Testing cursor not in a token
    # - Identified by cursor location: line 300, character 5
    # - Should return None
    cursor = [300, 5]

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=text_document_item)
    await did_open(server, openParams)

    # Call server.get_references()
    refParams = ReferenceParams(
        text_document=text_document_item,
        position=Position(line=cursor[0], character=cursor[1]),
        context=ReferenceContext(include_declaration=False),
    )

    response = get_references(server, refParams)
    assert response is None

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(text_document=text_document_item)
    did_close(server, closeParams)


@pytest.mark.asyncio
async def test_get_references_fail_no_symbol():
    """
    Test trying to get references when the token is not a GTIRB symbol
    Result is a location that references the block the cursor is in
    """
    server.reset_mocks()

    # Testing cursor in a token that is not a GTIRB symbol
    # - Identified by cursor location: line 300, character 20
    # - Should return None
    cursor = [300, 20]
    reference = [339, 16, 22]

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=text_document_item)
    await did_open(server, openParams)

    # Call server.get_references()
    refParams = ReferenceParams(
        text_document=text_document_item,
        position=Position(line=cursor[0], character=cursor[1]),
        context=ReferenceContext(include_declaration=False),
    )
    references = get_references(server, refParams)

    # Verify the result
    assert len(references) == 1
    ref = next(iter(references))
    assert [ref.range.start.line, ref.range.start.character, ref.range.end.character] == reference

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(text_document=text_document_item)
    did_close(server, closeParams)


@pytest.mark.asyncio
async def test_get_references_fail_no_definition():
    """
    Test getting references for a symbol not defined in the listing
    """
    server.reset_mocks()

    # The symbol "__init_array_start":
    # - Identified by cursor location: line 1306, character 5
    # - Should return None
    cursor = [1306, 5]

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=text_document_item)
    await did_open(server, openParams)

    # Call server.get_references()
    refParams = ReferenceParams(
        text_document=text_document_item,
        position=Position(line=cursor[0], character=cursor[1]),
        context=ReferenceContext(include_declaration=False),
    )

    response = get_references(server, refParams)
    assert response is None

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(text_document=text_document_item)
    did_close(server, closeParams)
