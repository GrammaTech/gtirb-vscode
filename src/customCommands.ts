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
    await commands.executeCommand('getLineFromAddress', mydoc, result).then((range: Range|any) =>
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
