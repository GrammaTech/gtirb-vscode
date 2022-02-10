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

import { getAddressAndJump, getPathForListing } from './customCommands';

import {promises as fs} from 'fs';
import * as url from 'url';

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


const FALLBACK_PYTHON = 'python';

/**
 * Derive python path from Python extension API
 * https://github.com/microsoft/vscode-python/wiki/AB-Experiments#pythondeprecatepythonpath
 * https://github.com/vscode-restructuredtext/vscode-restructuredtext/pull/224/files
 */
async function getPythonPath(): Promise<string> {
    let pythonPath;
    try {
        const extension = vscode.extensions.getExtension("ms-python.python");
        if (extension) {
            const usingNewInterpreterStorage = extension.packageJSON?.featureFlags?.usingNewInterpreterStorage;
            if (usingNewInterpreterStorage) {
                if (!extension.isActive) {
                    await extension.activate();
                }
                pythonPath = extension.exports.settings.getExecutionDetails().execCommand[0];
            }
        }
    } catch (error) {
        console.error('Error obtaining Python extension python path', error);
    }
    if (!pythonPath) {
        pythonPath = vscode.workspace.getConfiguration("python").get<string>("defaultInterpreterPath");
    }
    if (!pythonPath) {
        pythonPath = vscode.workspace.getConfiguration("python").get<string>("pythonPath");
    }
    if (!pythonPath) {
        pythonPath = FALLBACK_PYTHON;
    }
    return pythonPath;
}

export async function activate(context: vscode.ExtensionContext) {
    const port = vscode.workspace.getConfiguration().get<number>('gtirb.server.port');
    const hostAddr = vscode.workspace.getConfiguration().get<string>('gtirb.server.host');

    const cwd = path.join(__dirname, "..");
    const pythonPath = await getPythonPath();

    if (!pythonPath) {
        throw new Error("`python.pythonPath` is not set");
    }

    if (hostAddr === 'stdio') {
        client = startLangServer(pythonPath, ["-m", "gtirb_lsp_server"], cwd);
    } else {
        client = startLangServerTCP(port!, hostAddr!);
    }

    // Register request handlers for custom requests
    client.onReady().then(function (x: any) {
        // Response to a Get GTIRB File request from the server
        client.onRequest("gtirbGetGtirbFile", async (params: string) => {
            const p = url.fileURLToPath(new url.URL(params));
            const buf = await fs.readFile(p);
            const text = buf.toString('base64');
            return{params, languageId: '', version: 0, text: text};
        });
    });

    // Register our custom editor providers
    context.subscriptions.push(client.start());
    context.subscriptions.push(GtirbEditorProvider.register(context, pythonPath));

    context.subscriptions.push(
        vscode.commands.registerCommand('gtirb-vscode.goToAddress', () => {
            getAddressAndJump();
        }),
        vscode.commands.registerCommand('gtirb-vscode.getPathForListing', (gtirbFile, isa) =>
            getPathForListing(gtirbFile, isa)
        )
    );
}


export function deactivate(): Thenable<void> {
    //client.sendRequest("exit"); (needed?)
    return client ? client.stop() : Promise.resolve();
}
