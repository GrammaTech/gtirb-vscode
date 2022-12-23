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
import * as vscode from 'vscode';
import { getNonce } from './util';
import { Disposable } from './dispose';
import * as path from 'path';
import { ISA } from './customCommands';
import { client, customIndexer } from './extension';

import * as cp from 'child_process';
import * as fs from 'fs';

const execFile = (cmd: string, ...args: string[]) =>
    new Promise<string>((resolve, reject) => {
        cp.execFile(cmd, args, (err, out) => {
            if (err) {
                return reject(err);
            }
            return resolve(out);
        });
    });

/**
 * If you are not extending some kind of Text Editor, you have to define a Custom Document
 * This is the custom document definition for the GTIRB editor.
 */
class GtirbDocument extends Disposable implements vscode.CustomDocument {
    static create(uri: vscode.Uri): GtirbDocument {
        return new GtirbDocument(uri);
    }

    private readonly _uri: vscode.Uri;

    private constructor(uri: vscode.Uri) {
        super();
        this._uri = uri;
    }

    public get uri() {
        return this._uri;
    }

    private readonly _onDidDispose = this._register(new vscode.EventEmitter<void>());

    public readonly onDidDispose = this._onDidDispose.event;

    dispose(): void {
        const parsedPath = path.parse(this._uri.fsPath);
        const cachePath = path.join(parsedPath.dir, '.vscode.'.concat(parsedPath.base));

        const isas = Object.values(ISA);
        const asms = isas.map(isa =>
            path.join(cachePath, isa, parsedPath.name.concat('.view'))
        );

        // Wait for text document
        const asmPath = asms.find(path => {
            return fs.existsSync(path);
        });

        if (asmPath) {
            // Set as file permission according to config setting
            const readOnly = vscode.workspace.getConfiguration().get<boolean>('gtirb.listings.viewMode');
            if (readOnly) {
                fs.chmod(asmPath, 0o444, () => {
                    console.log(`setting ${asmPath} to read only`);
                });
            }
            vscode.window.showTextDocument(vscode.Uri.file(asmPath));
        } else {
            vscode.window.showErrorMessage(`Could not find gtirb disassembly in: ${asms.join(', ')}`);
        }

        this._onDidDispose.fire();
        super.dispose();
    }
}

/**
 * Provider for gtirb editors.
 *
 */
export class GtirbEditorProvider implements vscode.CustomReadonlyEditorProvider<GtirbDocument> {

    public static register(context: vscode.ExtensionContext, pythonPath: string): vscode.Disposable {
        return vscode.window.registerCustomEditorProvider(
            GtirbEditorProvider.viewType,
            new GtirbEditorProvider(context, pythonPath),
            {
                webviewOptions: {
                    retainContextWhenHidden: true,
                },
                supportsMultipleEditorsPerDocument: false,
            }
        );
    }

    private static readonly viewType = 'gtirb-loader.gtirb';
    private extensionPath : string;

    constructor(private readonly context: vscode.ExtensionContext, private readonly pythonPath: string) {
        this.extensionPath = context.extensionPath;
    }

    async openCustomDocument(
        uri: vscode.Uri,
        openContext: vscode.CustomDocumentOpenContext,
        token: vscode.CancellationToken
    ): Promise<GtirbDocument> {
        const document: GtirbDocument = GtirbDocument.create(uri);
        const gtirbPath: string = uri.fsPath;
        const indexer = path.join(this.extensionPath, "indexer.py");
        if (customIndexer) {
            const asmGenerationMessage: string = await customIndexer(uri.fsPath, indexer);
            client?.outputChannel.appendLine(asmGenerationMessage);
        } else {
            const asmGenerationMessage: string = await execFile(this.pythonPath, indexer, uri.fsPath);
            client?.outputChannel.appendLine(asmGenerationMessage);
        }
        return document;
    }

    /**
     * Called when our custom editor is opened.
     *
     *
     */
    async resolveCustomEditor(
        document: GtirbDocument,
        webviewPanel: vscode.WebviewPanel,
        _token: vscode.CancellationToken
    ): Promise<void> {
        // Setup initial content for the webview
        webviewPanel.webview.options = {
            enableScripts: false
        };

        // (If you move the indexing to here, the webview will show while indexing)
        webviewPanel.webview.html = this.getHtmlForWebview(webviewPanel.webview);

        // As soon as the document is open, start the shutdown sequence
        vscode.commands.executeCommand('workbench.action.closeActiveEditor');
    }

    /**
     * Get the static html used for the editor webviews.
     */
    private getHtmlForWebview(webview: vscode.Webview): string {
        const nonce = getNonce();

        return /* html */`
            <!DOCTYPE html>
            <html lang="en">
            <head>
            <meta charset="UTF-8">

            <!--
            Use a content security policy to only allow loading images from https or from our extension directory,
            and only allow scripts that have a specific nonce.
            -->
            <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${webview.cspSource}; style-src ${webview.cspSource}; script-src 'nonce-${nonce}';">

            <meta name="viewport" content="width=device-width, initial-scale=1.0">

            <title>GTIRB Editor</title>
            </head>
            <body>
            <i>Loading...</i>
            </body>
            </html>`;
    }
}
