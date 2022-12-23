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
    await server.did_open(openParams)

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
    server.did_change(changeParams)
    if server.can_rewrite():
        # If rewriting there should be 2 log messages and no user messages
        assert server.gtirb_server.show_message_log.call_count == 2
        assert server.gtirb_server.show_message.call_count == 0
    else:
        # If not rewriting there should be 1 log message and 1 user mesage
        assert server.gtirb_server.show_message_log.call_count == 1
        assert server.gtirb_server.show_message.call_count == 1

    # Call server.did_save() to process edit and rewrite file
    saveParams = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=fake_document.document_uri)
    )
    await server.did_save(saveParams)
    if server.can_rewrite():
        server.gtirb_server.show_message.assert_called_once_with("GTIRB rewritten successfully")
    else:
        assert server.gtirb_server.show_message.call_count == 2

    # Call server.did_close()
    closeParams = DidCloseTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=fake_document.document_uri)
    )
    server.did_close(closeParams)
