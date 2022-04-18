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
Test custom cammands for this server
"""

# NOTE:
# - line numbering starts at zero in the listing file

import pytest
from unittest.mock import Mock

from pygls.lsp.types import (
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    TextDocumentIdentifier,
    TextDocumentItem,
)
from gtirb_lsp_server.server import (
    did_open,
    did_close,
    get_line_from_address,
    get_address_of_symbol,
)
from gtirb_lsp_server.tests.fake_server import FakeServer, FakeDocument

# Create a fake server
server = FakeServer()
fake_document = FakeDocument()
server.workspace.get_document = Mock(return_value=fake_document.document)
text_document_item = TextDocumentItem(
    uri=fake_document.document_uri, language_id="gtgas", version=1, text=str(fake_document.asmtext),
)

# Unlike other features, the custom commands
# check the list of documents in the workspace
server.workspace.put_document(text_document_item)


@pytest.mark.asyncio
async def test_line_from_address_success():
    """
    Open the document, run the handler for the
    CMD_GET_LINE_FROM_ADDRESS custom command,
    then close.
    """
    server.reset_mocks()

    # Get line number of an address in the test document:
    # - Address is 0x15a5
    # - Corresponding line number is 829
    input_address = "0x15a5"
    output_line = 829

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=text_document_item)
    await did_open(server, openParams)

    # Call server command handler
    args = [fake_document.document_uri, input_address]
    response = await get_line_from_address(server, args)
    assert response.start.line == output_line

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=fake_document.document_uri)
    )
    did_close(server, closeParams)


@pytest.mark.asyncio
async def test_line_from_address_fail_no_document():
    """
    Test sending a URI that does not match any workspace document
    """
    server.reset_mocks()
    input_address = "0x15a5"
    bad_uri = "bad.view"

    # Call server command handler
    args = [bad_uri, input_address]
    response = await get_line_from_address(server, args)
    assert response is None
    server.show_message.assert_called_once_with(f" No address mapping for {bad_uri}")


@pytest.mark.asyncio
async def test_line_from_address_fail_invalid_addr():
    """
    Test sending a string that is not an address
    """
    server.reset_mocks()
    input_address = "line something or other"

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=text_document_item)
    await did_open(server, openParams)

    # Call server command handler
    server.reset_mocks()
    args = [fake_document.document_uri, input_address]
    response = await get_line_from_address(server, args)
    assert response is None
    server.show_message.assert_called_once_with(f" Invalid address {input_address}")

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=fake_document.document_uri)
    )
    did_close(server, closeParams)


@pytest.mark.asyncio
async def test_line_from_address_fail_no_line():
    """
    Test sending an address out of range
    """
    server.reset_mocks()
    input_address = "0x300000"

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=text_document_item)
    await did_open(server, openParams)

    # Call server command handler
    server.reset_mocks()
    args = [fake_document.document_uri, input_address]
    response = await get_line_from_address(server, args)
    assert response is None
    server.show_message.assert_called_once_with(f" No line for {input_address}")

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=fake_document.document_uri)
    )
    did_close(server, closeParams)


#
# ----------------------------------------------------------------------------------------
#
# THE OTHER COMMAND
#
# ----------------------------------------------------------------------------------------
#


@pytest.mark.asyncio
async def test_address_of_symbol_success():
    """
    Open the document, run the handler for the
    CMD_GET_ADDRESS_OF_SYMBOL custom command,
    then close.
    """
    server.reset_mocks()

    # Get the address of a symbol in the test document:
    # - Symbol is ".L_1820"
    # - Address is 0x1820
    input_symbol = ".L_1820"
    output_address = "0x1820"

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=text_document_item)
    await did_open(server, openParams)

    # Call server command handler
    args = [fake_document.document_uri, input_symbol]
    response = await get_address_of_symbol(server, args)
    assert response == output_address

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=fake_document.document_uri)
    )
    did_close(server, closeParams)


@pytest.mark.asyncio
async def test_address_of_symbol_fail_no_document():
    """
    Test sending a URI that does not match any workspace document
    """
    server.reset_mocks()
    input_symbol = ".L_1820"
    bad_uri = "bad.view"

    # Call server command handler
    args = [bad_uri, input_symbol]
    response = await get_address_of_symbol(server, args)
    assert response is None
    server.show_message.assert_called_once_with(f" No address mapping for {bad_uri}")


@pytest.mark.asyncio
async def test_address_of_symbol_fail_no_definition():
    """
    Test trying to get the address of a symbol that is not in the listing
    """
    server.reset_mocks()
    input_symbol = "notAnyActualSymbol"

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=text_document_item)
    await did_open(server, openParams)

    # Call server command handler
    args = [fake_document.document_uri, input_symbol]
    response = await get_address_of_symbol(server, args)
    assert response is None
    server.show_message(f" {input_symbol} does not have an address")

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=fake_document.document_uri)
    )
    did_close(server, closeParams)
