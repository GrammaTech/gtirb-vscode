import json
import unittest
from pathlib import Path
from typing import Text
from uuid import UUID

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
    apply_changes_to_indexes,
    block_text,
    offset_to_line,
    block_byte_interval,
    function_uuid_for_name,
    function_decompilations,
    parse_function_name,
    address_to_line,
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

    def get_current_indexes(self):
        return line_offsets_to_maps(self.gtirb, get_line_offset(self.gtirb, self.asm))

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

    def test_line_offsets_to_maps(self):
        (offset_by_line, line_by_offset) = line_offsets_to_maps(
            self.gtirb, get_line_offset(self.gtirb, self.asm)
        )
        self.assertTrue(isinstance(offset_to_auxdata(self.gtirb, offset_by_line.get(300)), str))

    def test_offsets_to_line_maps(self):
        (offset_by_line, line_by_offset) = line_offsets_to_maps(
            self.gtirb, get_line_offset(self.gtirb, self.asm)
        )
        self.assertTrue(
            isinstance(offset_to_line(line_by_offset, list(offset_by_line.values())[0]), int)
        )

    def test_offset_indexed_aux_data(self):
        offset_indexed_names = offset_indexed_aux_data(self.gtirb)
        self.assertTrue(len(offset_indexed_names) > 0)
        self.assertTrue(all(map(lambda it: isinstance(it, str), offset_indexed_names)))

    def test_blocks_for_function_name(self):
        blocks = blocks_for_function_name(self.gtirb, "generateMessageID")
        self.assertTrue(len(blocks) > 0)

    def test_block_byte_interval(self):
        blocks = blocks_for_function_name(self.gtirb, "generateMessageID")
        self.assertTrue(
            isinstance(block_byte_interval(self.gtirb, next(iter(blocks))), gtirb.ByteInterval)
        )

    def test_first_line_for_uuid(self):
        (offset_by_line, line_by_offset) = line_offsets_to_maps(
            self.gtirb, get_line_offset(self.gtirb, self.asm)
        )
        uuid_w_line = list(offset_by_line.values())[0].element_id.uuid
        first_line = first_line_for_uuid(offset_by_line, uuid_w_line)
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
        self.assertTrue(isinstance(offsets[0][1], gtirb.Symbol))

    def test_get_line_from_address(self):
        address = int("0x41acaa", 16)
        expected_line = 27070
        (offset_by_line, line_by_offset) = line_offsets_to_maps(
            self.gtirb, get_line_offset(self.gtirb, self.asm)
        )
        line = address_to_line(self.gtirb, line_by_offset, address)
        self.assertTrue(line == expected_line)

    def test_get_references_for_symbol(self):
        symbol_name = ".L_4049d9"
        expected_definition_line = 1321
        expected_references = [1318, 1367]
        sym = symbol_for_name(self.gtirb, symbol_name)
        self.assertTrue(sym is not None)
        (offset_by_line, line_by_offset) = line_offsets_to_maps(
            self.gtirb, get_line_offset(self.gtirb, self.asm)
        )
        referent_line = first_line_for_uuid(offset_by_line, sym.referent.uuid)
        self.assertTrue(referent_line == expected_definition_line)
        offset = offset_by_line[referent_line]
        self.assertTrue(offset is not None)
        references = list(symbolic_references(self.gtirb, offset.element_id.references))
        offsets_and_referenced_symbols = offsets_at_references(self.gtirb, references)
        reference_lines = list(
            filter(
                lambda it: isinstance(it, int),
                map(
                    lambda off: line_by_offset.get(off),
                    map(lambda off_and_se: off_and_se[0], offsets_and_referenced_symbols,),
                ),
            )
        )
        reference_lines.sort()
        self.assertTrue(reference_lines == expected_references)

    def test_apply_changes_to_indexes_same_size(self):
        (offset_by_line, line_by_offset) = line_offsets_to_maps(
            self.gtirb, get_line_offset(self.gtirb, self.asm)
        )
        target_start_pair = list(offset_by_line.items())[
            100
        ]  # Randomly chosen range in the program.
        target_end_pair = list(offset_by_line.items())[104]  # Randomly chosen range in the program.
        new_text = "\n".join(
            ["Line of new text"] * ((target_end_pair[0] + 1) - target_start_pair[0])
        )
        (new_offset_by_line, new_line_by_offset) = apply_changes_to_indexes(
            offset_by_line, line_by_offset, [(target_start_pair[0], target_end_pair[0], new_text)]
        )
        # When the size doesn't change, the same sets of lines should have offsets.
        print(f"OLD LINES: {sorted(offset_by_line.keys())}")
        print(f"NEW LINES: {sorted(new_offset_by_line.keys())}")
        self.assertTrue(set(offset_by_line.keys()) == set(new_offset_by_line.keys()))

    def test_apply_changes_to_indexes_smaller_replacement(self):
        (offset_by_line, line_by_offset) = line_offsets_to_maps(
            self.gtirb, get_line_offset(self.gtirb, self.asm)
        )
        target_start_pair = list(offset_by_line.items())[
            100
        ]  # Randomly chosen range in the program.
        target_end_pair = list(offset_by_line.items())[104]  # Randomly chosen range in the program.
        new_text = "\n".join(
            ["Line of new text"] * (((target_end_pair[0] + 1) - target_start_pair[0]) - 1)
        )
        (new_offset_by_line, new_line_by_offset) = apply_changes_to_indexes(
            offset_by_line, line_by_offset, [(target_start_pair[0], target_end_pair[0], new_text)]
        )
        # When the size decreases, then fewer lines should have offsets.
        print(f"OLD LINES: {sorted(offset_by_line.keys())}")
        print(f"NEW LINES: {sorted(new_offset_by_line.keys())}")
        self.assertTrue(len(offset_by_line.keys()) > len(new_offset_by_line.keys()))

    def test_apply_changes_to_indexes_larger_replacement(self):
        (offset_by_line, line_by_offset) = line_offsets_to_maps(
            self.gtirb, get_line_offset(self.gtirb, self.asm)
        )
        target_start_pair = list(offset_by_line.items())[
            100
        ]  # Randomly chosen range in the program.
        target_end_pair = list(offset_by_line.items())[104]  # Randomly chosen range in the program.
        new_text = "\n".join(
            ["Line of new text"] * (((target_end_pair[0] + 1) - target_start_pair[0]) + 10)
        )
        (new_offset_by_line, new_line_by_offset) = apply_changes_to_indexes(
            offset_by_line, line_by_offset, [(target_start_pair[0], target_end_pair[0], new_text)]
        )
        print(f"OLD LINES: {sorted(offset_by_line.keys())}")
        print(f"NEW LINES: {sorted(new_offset_by_line.keys())}")
        # When the size increases, then there should be lines between start and end w/o offsets.
        self.assertTrue(
            len(
                list(
                    filter(
                        lambda l: (l > target_start_pair[0]) and (l < target_start_pair[0] + 10),
                        set(offset_by_line.keys()).difference(set(new_offset_by_line.keys())),
                    )
                )
            )
            > 0
        )
        # When the size increases, then there should be the same number of lines w/offsets.
        self.assertTrue(len(offset_by_line.keys()) > len(new_offset_by_line.keys()))

    def test_block_text(self):
        (offset_by_line, line_by_offset) = line_offsets_to_maps(
            self.gtirb, get_line_offset(self.gtirb, self.asm)
        )
        cb = list(offset_by_line.items())[100][1].element_id
        text = block_text(line_by_offset, cb, self.asm)
        self.assertTrue(isinstance(text, str))
        self.assertTrue(len(text.splitlines()) > 1)

    def test_function_uuid_for_name(self):
        function_uuid = function_uuid_for_name(self.gtirb, "undefined")
        self.assertIsNone(function_uuid)

        function_uuid = function_uuid_for_name(self.gtirb, "main")
        self.assertEqual(function_uuid, UUID("6263d7b2-da85-49bd-8f8e-5585417a5500"))


class HelloTestDriver(unittest.TestCase):
    def setUp(self):
        self.gtirb = gtirb.IR.load_protobuf(DATA_DIR / "hello.gtirb")

    def test_function_decompilations(self):
        decompilations = function_decompilations(self.gtirb, "undefined")
        self.assertIsNone(decompilations)

        decompilations = function_decompilations(self.gtirb, "main")
        text = 'int main() {\n    // 0x401130\n    puts("Hello World\\n");\n    return 0;\n}'
        expected = f"## Retdec\n```c\n{text}\n```"
        self.assertEqual(decompilations, expected)


class ParseFunctionNameTestDriver(unittest.TestCase):
    def test_parse_function_name(self):
        name = parse_function_name('.section .interp ,"a",@progbits')
        self.assertIsNone(name)

        name = parse_function_name("#===================================")
        self.assertIsNone(name)

        name = parse_function_name("push RBP              # EA: 0x401690")
        self.assertIsNone(name)

        name = parse_function_name(".L_402ea0:")
        self.assertIsNone(name)

        name = parse_function_name(".globl main")
        self.assertEqual(name, "main")

        name = parse_function_name(".type main, @function")
        self.assertEqual(name, "main")

        name = parse_function_name("main:")
        self.assertEqual(name, "main")
