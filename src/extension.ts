import * as vscode from 'vscode';
import { GtirbEditorProvider } from './gtirbEditor';

export function activate(context: vscode.ExtensionContext) {
	// Register our custom editor providers
	context.subscriptions.push(GtirbEditorProvider.register(context));
}
