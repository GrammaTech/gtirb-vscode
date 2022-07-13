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

export let client: LanguageClient;
export let customIndexer: (gtirbPath: string, pyScript: string) => Promise<string>;

function getClientOptions(): LanguageClientOptions {
    return {
        // Register the server for GT assembly documents
        documentSelector: [
            { scheme: "file", language: "gtgas" },
            { scheme: "file", language: "gtmips" },
        ],
        outputChannelName: "Gtirb Language Server",
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

interface GtirbPushParams {
    uri: string;
    content: string;
}


function registerLspHandlers(client: LanguageClient) {
    // Register request handlers for custom requests
    client.onReady().then(function (x: any) {
        // Response to a "Get GTIRB File" request from the server
        client.onRequest("gtirbGetGtirbFile", async (params: string) => {
            const p = url.fileURLToPath(new url.URL(params));
            const buf = await fs.readFile(p);
            const text = buf.toString('base64');
            return{params, languageId: '', version: 0, text: text};
        });
        // Response to a "Push GTIRB File" request from the server
        client.onRequest("gtirbPushGtirbFile", async (params: GtirbPushParams) => {
            const gtirb_uri = params.uri;
            const content = params.content;
            const buf = Buffer.from(content, 'base64');
            const p = url.fileURLToPath(new url.URL(gtirb_uri));
            fs.writeFile(p, buf).then(
                val => { client.outputChannel.appendLine(`GTIRB from server: ${params.uri} transfer complete.`); },
                err => { throw new Error(`failed to write gtirb file ${params.uri}: ${err}`); }
            );
            return{languageId: '', version: 0, text: "OK"};
        });
    });
}

export async function activate(context: vscode.ExtensionContext) {
    const port = vscode.workspace.getConfiguration().get<number>('gtirb.server.port');
    const hostAddr = vscode.workspace.getConfiguration().get<string>('gtirb.server.host');

    const pythonPath = await getPythonPath();

    if (!pythonPath) {
        throw new Error("`python.pythonPath` is not set");
    }

    if (hostAddr === 'stdio') {
        client = startLangServer(pythonPath, ["-m", "gtirb_lsp_server"],
            path.join(context.extensionPath, "gtirb_lsp_server"));
    } else {
        client = startLangServerTCP(port!, hostAddr!);
    }
    registerLspHandlers(client);

    // Register our custom editor providers
    context.subscriptions.push(client.start());
    context.subscriptions.push(GtirbEditorProvider.register(context, pythonPath));

    context.subscriptions.push(
        vscode.commands.registerCommand('gtirb-vscode.goToAddress', () => {
            getAddressAndJump();
        }),
        vscode.commands.registerCommand('gtirb-vscode.getPathForListing', (gtirbFile, isa) =>
            getPathForListing(gtirbFile, isa)
        ),
        vscode.commands.registerCommand('gtirb-vscode.startCustomLspServer',
            (command: string, args: string[], cwd = context.extensionPath) => {
                // Don't do anything if the LSP client is already working
                if (client.initializeResult !== undefined) {
                    return;
                }
                client = startLangServer(command, args, cwd);
                registerLspHandlers(client);
                context.subscriptions.push(client.start());
            }
        ),
        vscode.commands.registerCommand('gtirb-vscode.retryLspConnection', () => {
            // Don't do anything if the LSP client is already working
            if (client.initializeResult !== undefined) {
                return;
            }
            client = startLangServerTCP(port!, hostAddr!);
            registerLspHandlers(client);
            context.subscriptions.push(client.start());
        }),
        vscode.commands.registerCommand('gtirb-vscode.registerCustomIndexer',
            (indexer: (gtirbPath: string, pyScript: string) => Promise<string>) => {
                customIndexer = indexer;
            }
        ),
    );
}


export function deactivate(): Thenable<void> {
    //client.sendRequest("exit"); (needed?)
    return client ? client.stop() : Promise.resolve();
}
