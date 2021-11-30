//"use strict";

import * as net from "net";
import * as path from "path";
import * as vscode from 'vscode';
import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions
} from 'vscode-languageclient/node';

import { GtirbEditorProvider } from './gtirbEditor';

let client: LanguageClient;

function getClientOptions(): LanguageClientOptions {
    return {
        // Register the server for GT assembly documents
        documentSelector: [
            { scheme: "file", language: "gtgas" },
            { scheme: "file", language: "gtmips" },
        ],
        outputChannelName: "[pygls] GTIRB LanguageServer",
        synchronize: {
            // Notify the server about file changes to '.clientrc files contain in the workspace
            fileEvents: vscode.workspace.createFileSystemWatcher("**/.clientrc"),
        },
    };
}


function isStartedInDebugMode(): boolean {
    return process.env.VSCODE_DEBUG_MODE === "true";
}

function startLangServerTCP(port: number, hostAddr: string): LanguageClient {
    const serverOptions: ServerOptions = () => {
        return new Promise((resolve /*, reject */) => {
            const clientSocket = new net.Socket();
            clientSocket.connect(port, hostAddr, () => {
                resolve({
                    reader: clientSocket,
                    writer: clientSocket,
                });
            });
        });
    };

    return new LanguageClient(
        'gtirbServer',
        `tcp lang server (port ${port})`,
        serverOptions,
        getClientOptions()
    );
}

function startLangServer(
    command: string,
    args: string[],
    cwd: string
): LanguageClient {
    const serverOptions: ServerOptions = {
        args,
        command,
        options: { cwd },
    };

    return new LanguageClient(command, serverOptions, getClientOptions());
}


export function activate(context: vscode.ExtensionContext) {
    const port = vscode.workspace.getConfiguration().get<number>('gtirb.server.port');
    const hostAddr = vscode.workspace.getConfiguration().get<string>('gtirb.server.host');

    const cwd = path.join(__dirname, "..");
    const pythonPath = vscode.workspace
        .getConfiguration("python")
        .get<string>("pythonPath");

    if (!pythonPath) {
        throw new Error("`python.pythonPath` is not set");
    }

    if (hostAddr === 'stdio') {
        client = startLangServer(pythonPath, ["-m", "gtirb_lsp_server"], cwd);
    } else {
        client = startLangServerTCP(port!, hostAddr!);
    }

    // Register our custom editor providers
    context.subscriptions.push(client.start());
    context.subscriptions.push(GtirbEditorProvider.register(context, pythonPath));
}


export function deactivate(): Thenable<void> {
    //client.sendRequest("exit"); (needed?)
    return client ? client.stop() : Promise.resolve();
}
