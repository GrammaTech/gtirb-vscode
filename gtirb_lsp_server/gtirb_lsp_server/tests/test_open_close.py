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
    await server.did_open(openParams)

    # Verify open:
    # - Always sends message when indexing is complete
    # - Check that thre file was created
    server.gtirb_server.show_message.assert_called_once()
    assert index_path.exists()

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(text_document=text_document_item)
    server.did_close(closeParams)

    # If everything went right, show_message_log should
    # have been called exactly 3 times
    assert server.gtirb_server.show_message_log.call_count == 3

    # Opening the same document again should resuse the index
    server.reset_mocks()
    filename = os.path.split(fake_document.document.uri)[1]
    await server.did_open(openParams)
    server.gtirb_server.show_message_log.assert_called_with(f"re-using indexes for {filename}")
    server.did_close(closeParams)


@pytest.mark.asyncio
async def test_open_fail_bad_uri():
    """
    Test calling open with a bad uri
    """
    server.reset_mocks()

    bad_document_item = TextDocumentItem(
        uri="bad.view",
        language_id="gtgas",
        version=1,
        text=str(fake_document.asmtext),
    )

    # Call server.did_open()
    openParams = DidOpenTextDocumentParams(text_document=bad_document_item)
    with pytest.raises(Exception):
        await server.did_open(openParams)
