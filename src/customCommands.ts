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
        }
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
    });
}
