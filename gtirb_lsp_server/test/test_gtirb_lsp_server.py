import unittest
import json
import copy
import gtirb
from pathlib import Path
from typing import Optional, Text
from uuid import UUID

from gtirb_lsp_server.server import get_line_offset, UUIDEncoder, line_offsets_to_maps, offset_to_auxdata, offset_indexed_aux_data, blocks_for_function_name, first_line_for_blocks, first_line_for_uuid

DATA_DIR = Path(__file__).parent / "data"

def slurp(path: Path) -> Text:
    """Return the text in the file at the given path."""
    with open(path, "r") as f:
        return f.read()

class InitialIndexTestDriver(unittest.TestCase):
    def setUp(self):
        self.gtirb_path = (DATA_DIR / "leafnode.gtirb")
        self.gtirb = gtirb.IR.load_protobuf(self.gtirb_path)
        self.asm_path = (DATA_DIR / "leafnode.gtasm")
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
        json.dump(line_offsets, open(DATA_DIR / "temp.json", "w"), cls=UUIDEncoder)
        self.assertEqual(line_offsets,
                         list(map(lambda el: (el[0],(UUID(hex=el[1][0]),el[1][1])),
                                json.load(open(DATA_DIR / "temp.json", "r")))))

    def test_line_offsets_to_maps(self):
        (offset_by_line, line_by_offset) = line_offsets_to_maps(
            self.gtirb,
            get_line_offset(self.gtirb, self.asm)
        )
        counter = 0
        found = False
        for i in range(len(self.asm.splitlines())):
            try:
                off = offset_by_line[i]
            except:
                continue
            counter += 1
            auxdata = offset_to_auxdata(self.gtirb, off)
            if auxdata:
                found = True
                print(f"{i} {off.element_id.uuid.hex} {off.displacement} {auxdata}")
                break
        print(f"{counter} line to UUID maps processed")
        self.assertTrue(counter > 0)
        self.assertTrue(found)

    def test_offset_indexed_aux_data(self):
        offset_indexed_names = offset_indexed_aux_data(self.gtirb)
        self.assertTrue(len(offset_indexed_names) > 0)
        self.assertTrue(all(map(lambda it: isinstance(it, str), offset_indexed_names)))

    def test_blocks_for_function_name(self):
        blocks = blocks_for_function_name(self.gtirb, 'generateMessageID')
        self.assertTrue(len(blocks) > 0)

    def test_first_line_for_uuid(self):
        (offset_by_line, line_by_offset) = line_offsets_to_maps(
            self.gtirb,
            get_line_offset(self.gtirb, self.asm)
        )
        uuid_w_line = list(offset_by_line.items())[0][1].element_id.uuid
        first_line = first_line_for_uuid(offset_by_line, uuid_w_line)
        self.assertTrue(isinstance(first_line, int))

    def test_function_blocks_to_lines(self):
        (offset_by_line, line_by_offset) = line_offsets_to_maps(
            self.gtirb,
            get_line_offset(self.gtirb, self.asm)
        )
        blocks = blocks_for_function_name(self.gtirb, 'generateMessageID')
        self.assertTrue(len(blocks) > 0)
        line = first_line_for_blocks(offset_by_line, blocks)
        self.assertTrue(isinstance(line, int))
