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
Test LSP features using a mocked server instance running in remote mode
"""

import os
import shutil
import hashlib
import tempfile

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

# Make this one remote
server.is_remote = Mock(return_value=True)

# Additional setup and configuration for remote mode
#
# Copy the gtirb into the place where a server pull would put it,
# because pytest (in python3.6) does not support mocking async operations
# which the server uses to pull the gtirb.
#
# => TODO: Revisit this when async is supported so that servver pull will get
# tested Pre-placing the gtirb as I am doing here means the server won't call
# the servcer pull method.
#
# This following code duplicates the code used in the server to
# generate a remote file name:
peername = "mytestpeer"
client_path = peername + ":" + "file://" + str(fake_document.asm_path)
hashname = hashlib.md5(client_path.encode("utf-8")).hexdigest() + ".gtirb"
remote_gtirbfile = os.path.join(tempfile.gettempdir(), hashname)
index_path = Path(remote_gtirbfile + ".json")
shutil.copyfile(fake_document.gtirb_path, remote_gtirbfile)
server.lsp.transport.get_extra_info = Mock(return_value=[peername])


@pytest.mark.asyncio
async def test_open_close_remote():
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
