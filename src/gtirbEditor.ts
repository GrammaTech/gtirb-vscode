import * as vscode from 'vscode';
import { getNonce } from './util';
import { Disposable } from './dispose';
import * as path from 'path';

import * as cp from 'child_process';
import * as fs from 'fs';

const execShell = (cmd: string) =>
    new Promise<string>((resolve, reject) => {
        cp.exec(cmd, (err, out) => {
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
	static create(
        uri: vscode.Uri
	): GtirbDocument {
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

	private readonly _onDidDispose = this._register(
        new vscode.EventEmitter<void>()
	);

	public readonly onDidDispose = this._onDidDispose.event;

	dispose(): void {
		const parsedPath = path.parse(this._uri.fsPath);
		const cachePath = path.join(parsedPath.dir, '.vscode.'.concat(parsedPath.base));

		const x64CachePath = path.join(cachePath, 'x64');
		const x64AsmPath = path.join(x64CachePath, parsedPath.name.concat('.gtasm'));

		const mipsCachePath = path.join(cachePath, 'mips');
		const mipsAsmPath = path.join(mipsCachePath, parsedPath.name.concat('.gtasm'));

		const armCachePath = path.join(cachePath, 'arm');
		const armAsmPath = path.join(armCachePath, parsedPath.name.concat('.gtasm'));

		// Wait for text document
		if (fs.existsSync(x64AsmPath)) {
			try {
				vscode.window.showTextDocument(vscode.Uri.file(x64AsmPath));
			} catch {
				vscode.window.showInformationMessage(`${x64AsmPath} does not exist`);
			}
		} else	if (fs.existsSync(mipsAsmPath)) {
			vscode.window.showTextDocument(vscode.Uri.file(mipsAsmPath));
		} else	if (fs.existsSync(armAsmPath)) {
			vscode.window.showTextDocument(vscode.Uri.file(armAsmPath));
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

	public static register(context: vscode.ExtensionContext): vscode.Disposable {
		return vscode.window.registerCustomEditorProvider(
				GtirbEditorProvider.viewType,
				new GtirbEditorProvider(context),
			{
				webviewOptions: {
					retainContextWhenHidden: true,
				},
				supportsMultipleEditorsPerDocument: false,
			}
		);
	}

	private static readonly viewType = 'gtirb-loader.gtirb';
	private myPath : string;

	constructor(
		private readonly context: vscode.ExtensionContext
	) { 		this.myPath = context.extensionPath;
	}

	async openCustomDocument(
			uri: vscode.Uri,
			openContext: vscode.CustomDocumentOpenContext,
			token: vscode.CancellationToken
	): Promise<GtirbDocument> {
		const document: GtirbDocument = GtirbDocument.create(uri);
		console.log("gtirb resolve custom editor called.");

		console.log (`extension path: ${this.myPath}`);
		const path: string = uri.fsPath;
		const x64AssemblyFile: vscode.Uri = vscode.Uri.file(path.concat('.gtx64'));
		const x64JsonFile: vscode.Uri = vscode.Uri.file(x64AssemblyFile.fsPath.concat('.json'));

		const armAssemblyFile: vscode.Uri = vscode.Uri.file(path.concat('.gtarm'));
		const armJsonFile: vscode.Uri = vscode.Uri.file(armAssemblyFile.fsPath.concat('.json'));

		const mipsAssemblyFile: vscode.Uri = vscode.Uri.file(path.concat('.gtmips'));
		const mipsJsonFile: vscode.Uri = vscode.Uri.file(mipsAssemblyFile.fsPath.concat('.json'));

		// This is where I have been calling indexer, maybe with wait, maybe not
		if ((fs.existsSync(x64JsonFile.fsPath) && fs.existsSync(x64JsonFile.fsPath))
			|| (fs.existsSync(mipsJsonFile.fsPath) && fs.existsSync(mipsJsonFile.fsPath))
			|| (fs.existsSync(armJsonFile.fsPath) && fs.existsSync(armJsonFile.fsPath))) {
				console.log("reusing existing assembly and index files.");
		} else {
			await execShell(`${this.myPath}/indexer.sh ${path}`);
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
			//enableScripts: true,
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
