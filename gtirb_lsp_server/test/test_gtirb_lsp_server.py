import unittest
import json
import copy
import gtirb
from pathlib import Path
from typing import Optional, Text
from uuid import UUID

from gtirb_lsp_server.server import get_line_offset, UUIDEncoder

DATA_DIR = Path(__file__).parent / "data"

def slurp(path: Path) -> Text:
    """Return the text in the file at the given path."""
    with open(path, "r") as f:
        return f.read()

class InitialIndexTestDriver(unittest.TestCase):
    def setUp(self):
        self.gtirb_path = (DATA_DIR / "hello.gtirb")
        self.gtirb = gtirb.IR.load_protobuf(self.gtirb_path)
        self.asm_path = (DATA_DIR / "hello.gtasm")
        self.asm = slurp(self.asm_path)

    def test_get_line_offsets(self):
        line_offsets = get_line_offset(self.gtirb, self.asm)
        # Has type (int, (UUID, int))
        self.assertTrue(all(map(lambda el: isinstance(el[0], int), line_offsets)))
        self.assertTrue(all(map(lambda el: isinstance(el[1][1], int), line_offsets)))
        self.assertTrue(all(map(lambda el: isinstance(el[1][0], UUID), line_offsets)))
        # Is not empty.
        self.assertTrue(len(line_offsets) > 0)
        # Is able to dump
        json.dump(line_offsets, open(DATA_DIR / "hello.json", "w"), cls=UUIDEncoder)
        self.assertEqual(line_offsets,
                         list(map(lambda el: (el[0],(UUID(hex=el[1][0]),el[1][1])),
                                json.load(open(DATA_DIR / "hello.json", "r")))))
