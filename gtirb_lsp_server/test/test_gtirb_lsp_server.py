import json
import unittest
from pathlib import Path
from typing import Text
from uuid import UUID
from itertools import chain

import gtirb
from gtirb_lsp_server.server import (
    UUIDEncoder,
    blocks_for_function_name,
    first_line_for_blocks,
    first_line_for_uuid,
    get_line_offset,
    line_offsets_to_maps,
    offset_indexed_aux_data,
    offset_to_auxdata,
    offset_to_predecessors,
    offset_to_successors,
    offsets_at_references,
    preceding_function_line,
    symbol_for_name,
    symbolic_references,
)

DATA_DIR = Path(__file__).parent / "data"


def slurp(path: Path) -> Text:
    """Return the text in the file at the given path."""
    with open(path, "r") as f:
        return f.read()


class InitialIndexTestDriver(unittest.TestCase):
    def setUp(self):
        self.gtirb_path = DATA_DIR / "leafnode.gtirb"
        self.gtirb = gtirb.IR.load_protobuf(self.gtirb_path)
        self.asm_path = DATA_DIR / "leafnode.gtasm"
        self.asmtext = slurp(self.asm_path)
        self.asm = self.asmtext.splitlines()

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
        self.assertEqual(
            line_offsets,
            list(
                map(
                    lambda el: (el[0], (UUID(hex=el[1][0]), el[1][1])),
                    json.load(open(DATA_DIR / "temp.json", "r")),
                )
            ),
        )

    # def test_line_offsets_to_maps(self):
    #    (offsets_by_line, lines_by_offset) = line_offsets_to_maps(
    #        self.gtirb, get_line_offset(self.gtirb, self.asm)
    #    )
    #    counter = 0
    #    found = False
    #    for i in range(len(self.asm)):
    #        for off in offsets_by_line.get(i) or []:
    #            counter += 1
    #            auxdata = offset_to_auxdata(self.gtirb, off)
    #            if auxdata:
    #                found = True
    #                print(f"{i} {off.element_id.uuid.hex} {off.displacement} {auxdata}")
    #                break
    #        if found:
    #            break
    #    print(f"{counter} line to UUID maps processed")
    #    self.assertTrue(counter > 0)
    #    self.assertTrue(found)

    def test_offset_indexed_aux_data(self):
        offset_indexed_names = offset_indexed_aux_data(self.gtirb)
        self.assertTrue(len(offset_indexed_names) > 0)
        self.assertTrue(all(map(lambda it: isinstance(it, str), offset_indexed_names)))

    def test_blocks_for_function_name(self):
        blocks = blocks_for_function_name(self.gtirb, "generateMessageID")
        self.assertTrue(len(blocks) > 0)

    def test_first_line_for_uuid(self):
        (offsets_by_line, lines_by_offset) = line_offsets_to_maps(
            self.gtirb, get_line_offset(self.gtirb, self.asm)
        )
        uuid_w_line = list(offsets_by_line.items())[0][1][0].element_id.uuid
        first_line = first_line_for_uuid(offsets_by_line, uuid_w_line)
        self.assertTrue(isinstance(first_line, int))

    def test_function_blocks_to_lines(self):
        (offsets_by_line, lines_by_offset) = line_offsets_to_maps(
            self.gtirb, get_line_offset(self.gtirb, self.asm)
        )
        blocks = blocks_for_function_name(self.gtirb, "freeservers")
        self.assertTrue(len(blocks) > 0)
        line = first_line_for_blocks(offsets_by_line, blocks)
        self.assertTrue(isinstance(line, int))

    def test_preceding_function_line(self):
        func_name = "freeservers"
        func_line = 9878
        preceding_line = preceding_function_line(self.asm, func_name, func_line)
        self.assertEqual(preceding_line, 9876)

    def test_offset_to_predecessors(self):
        it = self.gtirb.get_by_uuid(UUID("7a888589-9c8e-4952-95c9-a096e5d9b479"))
        predecessors = list(
            offset_to_predecessors(self.gtirb, gtirb.Offset(element_id=it, displacement=0))
        )
        self.assertTrue(len(predecessors) > 0)

    def test_offset_to_successors(self):
        it = self.gtirb.get_by_uuid(UUID("7a888589-9c8e-4952-95c9-a096e5d9b479"))
        successors = list(
            offset_to_successors(self.gtirb, gtirb.Offset(element_id=it, displacement=0))
        )
        self.assertTrue(len(successors) > 0)

    def test_offsets_at_references(self):
        it = gtirb.Symbol(
            uuid=UUID("f73cd30c-c24e-4ad3-913a-c1be4545c7e4"),
            name=".L_410757",
            payload=gtirb.CodeBlock(
                uuid=UUID("32737754-db68-4bbe-a9df-18f8032208ca"),
                size=5,
                offset=52919,
                decode_mode=1,
            ),
            at_end=False,
        )
        references = list(symbolic_references(self.gtirb, it))
        self.assertTrue(len(references) > 0)
        print(f"First reference is {references[0]}")
        offsets = list(offsets_at_references(self.gtirb, references))
        self.assertTrue(len(offsets) > 0)
        self.assertTrue(isinstance(offsets[0][0], gtirb.Offset))
        self.assertTrue(isinstance(offsets[0][1], gtirb.SymbolicExpression))

    def test_get_references_for_symbol(self):
        symbol_name = ".L_4049d9"
        expected_definition_line = 1321
        expected_references = [1318, 1367]
        sym = symbol_for_name(self.gtirb, symbol_name)
        self.assertTrue(sym is not None)
        (offsets_by_line, lines_by_offset) = line_offsets_to_maps(
            self.gtirb, get_line_offset(self.gtirb, self.asm)
        )
        referent_line = first_line_for_uuid(offsets_by_line, sym.referent.uuid)
        self.assertTrue(referent_line == expected_definition_line)
        offset = offsets_by_line[referent_line][0]
        self.assertTrue(offset is not None)
        references = list(symbolic_references(self.gtirb, offset.element_id.references))
        offsets_and_symbolic_expressions = offsets_at_references(self.gtirb, references)
        reference_lines = list(
            filter(
                lambda it: isinstance(it, int),
                chain(
                    *map(
                        lambda off_and_se: lines_by_offset[off_and_se[0]],
                        offsets_and_symbolic_expressions,
                    )
                ),
            )
        )
        reference_lines.sort()
        self.assertTrue(reference_lines == expected_references)
