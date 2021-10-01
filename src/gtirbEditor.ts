import * as vscode from 'vscode';
import { getNonce } from './util';
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
 * Provider for gtirb editors.
 * 
 */
export class GtirbEditorProvider implements vscode.CustomTextEditorProvider {

	public static register(context: vscode.ExtensionContext): vscode.Disposable {
		const provider = new GtirbEditorProvider(context);
		const providerRegistration = vscode.window.registerCustomEditorProvider(GtirbEditorProvider.viewType, provider);
		return providerRegistration;
	}

	private static readonly viewType = 'gtirb-loader.gtirb';

	constructor(
		private readonly context: vscode.ExtensionContext
	) { }

	/**
	 * Called when our custom editor is opened.
	 * 
	 * 
	 */
	public async resolveCustomTextEditor(
		document: vscode.TextDocument,
		webviewPanel: vscode.WebviewPanel,
		_token: vscode.CancellationToken
	): Promise<void> {
		// Setup initial content for the webview
		console.log("gtirb editor activated.");

		execShell(`echo path = $PWD`).then(result => console.log(result));
		execShell(`echo file = ${document.fileName}`).then(result => console.log(result));

		const path: string = document.fileName;
		execShell(`./indexer.sh ${path}`).then(result => console.log(result));
		const x64AssemblyFile: vscode.Uri = vscode.Uri.file(path.concat('.gtx64'));
		const armAssemblyFile: vscode.Uri = vscode.Uri.file(path.concat('.gtarm'));
		const mipsAssemblyFile: vscode.Uri = vscode.Uri.file(path.concat('.gtmips'));
		if (fs.existsSync(x64AssemblyFile.fsPath)) {
			try {
				await vscode.workspace.fs.stat(x64AssemblyFile);
				vscode.window.showTextDocument(x64AssemblyFile);
			} catch {
				vscode.window.showInformationMessage(`${x64AssemblyFile.toString(true)} does not exist`);
			}
		}
		else if (fs.existsSync(armAssemblyFile.fsPath)) {
			try {
				await vscode.workspace.fs.stat(armAssemblyFile);
				vscode.window.showTextDocument(armAssemblyFile);
			} catch {
				vscode.window.showInformationMessage(`${armAssemblyFile.toString(true)} does not exist`);
			}
		}
		else if (fs.existsSync(mipsAssemblyFile.fsPath)) {
			try {
				await vscode.workspace.fs.stat(mipsAssemblyFile);
				vscode.window.showTextDocument(mipsAssemblyFile);
			} catch {
				vscode.window.showInformationMessage(`${mipsAssemblyFile.toString(true)} does not exist`);
			}
		}

		webviewPanel.webview.options = {
			enableScripts: true,
		};

		webviewPanel.webview.html = this.getHtmlForWebview(webviewPanel.webview);

		function updateWebview() {
			webviewPanel.webview.postMessage({
				type: 'update',
				text: document.getText(),
			});
		}

		// Hook up event handlers so that we can synchronize the webview with the text document.
		//
		// The text document acts as our model, so we have to sync change in the document to our
		// editor and sync changes in the editor back to the document.
		// 
		// Remember that a single text document can also be shared between multiple custom
		// editors (this happens for example when you split a custom editor)

		const changeDocumentSubscription = vscode.workspace.onDidChangeTextDocument(e => {
			if (e.document.uri.toString() === document.uri.toString()) {
				updateWebview();
			}
		});

		// Make sure we get rid of the listener when our editor is closed.
		webviewPanel.onDidDispose(() => {
			changeDocumentSubscription.dispose();
		});
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

				<title>GTIRB</title>
			</head>
			<body>
			</body>
			</html>`;
	}
}
