// Copyright (C) 2022 GrammaTech, Inc.
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.
//
// This project is sponsored by the Office of Naval Research, One
// Liberty Center, 875 N. Randolph Street, Arlington, VA 22203 under
// contract #N68335-17-C-0700.  The content of the information does
// not necessarily reflect the position or policy of the Government
// and no official endorsement should be inferred.
import { basename, join } from 'path';
import { window, commands, Range, TextEditorRevealType, Selection } from 'vscode';
import { integer } from 'vscode-languageclient';

function isHex(h:string) {
    const a = parseInt(h,16);
    return (a.toString(16) === h);
}

/**
 * Gets an address using window.showInputBox(),
 * then uses LSP custom command getLineFromAddress.
 */
export async function getAddressAndJump() {
    const result = await window.showInputBox({
        value: '0xabcdef',
        valueSelection: [2, 8],
        placeHolder: 'Enter a valid hex address',
        validateInput: text => {
            return isHex(text) ? 'invalid number!' : null;
        }
    });
    const editor = window.activeTextEditor;
    const mydoc = editor?.document.uri;
    if (editor == null || mydoc == null) {
        window.showInformationMessage(`no active document.`);
        return;
    }
    const position = editor?.selection.active;
    if (position == null) {
        window.showInformationMessage(`unable to find postion.`);
        return;
    }
    let line: integer = -1;
    await commands.executeCommand('gtirbGetLineFromAddress', mydoc.toString(), result).then((range: Range|any) =>
    {
        if (range) {
            editor?.revealRange(range, TextEditorRevealType.InCenter);
            line = range.start.line;

            const position = editor.selection.active;
            if (line > position.line) {
                const moveDown: integer = line - position.line;
                commands.executeCommand("cursorMove",
                {
                    to: "down", by:'line', value:moveDown
                });
            } else {
                const moveUp: integer = position.line - line;
                commands.executeCommand("cursorMove",
                {
                    to: "up", by:'line', value:moveUp
                });
            }
        }
    });
}

/* Instruction set architecture of a target binary. */
export enum ISA {
    X64 = 'x64',
    IA32 = 'ia32',
    ARM = 'arm',  // 32-bit, little endian
    MIPS32 = 'mips32' // 32-bit, big endian
}

/* gtirb-vscode cache dir relative to gtirb file */
const cacheDir = (gtirbFile: string) => `.vscode.${basename(gtirbFile)}`;

/**
 * Returns the path relative to the gtirb file where the vscode extension
 * will preferentially look for an existing listing file.
 */
export const getPathForListing = (gtirbFile: string, isa: ISA) =>
    join(cacheDir(gtirbFile), isa, `${basename(gtirbFile, '.gtirb')}.view`);
