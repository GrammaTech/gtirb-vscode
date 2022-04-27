# GTIRB GUI

A VSCode extension for viewing, navigating, and rewriting [GTIRB][], Grammatech's IR for Binaries.

[GTIRB]: https://github.com/GrammaTech/gtirb

## Prerequisites

This extension uses an LSP (language server protocol) server to add features to the VSCode UI. The LSP server is included with the extension.
- GTIRB UI (client) dependencies:
    - vscode (https://code.visualstudio.com/download).
    - [gtirb-pprinter][] version 1.8.2 or higher, which supports UI listing mode.
- LSP Server (python) dependencies:
    - python 3.6+.
    - The [gtirb][] python package.
    - Also the [pygls][] python package is required (can be installed with pip).
 - To support rewriting of GTIRB files (optional) the LSP server requires the following additional python packages
    - [gtirb-rewriting][]
    - [gtirb-functions][]
    - [mcasm][]

[gtirb]: https://github.com/GrammaTech/gtirb
[mcasm]: https://github.com/GrammaTech/mc-asm
[pygls]: https://github.com/openlawlibrary/pygls
[gtirb-pprinter]: https://github.com/GrammaTech/gtirb-pprinter
[gtirb-rewriting]: https://github.com/GrammaTech/gtirb-rewriting
[gtirb-functions]: https://github.com/GrammaTech/gtirb-functions

## Functionality

Some examples of what you can do with this extension: Load a GTIRB file and display an assembly file listing of the file contents. Hover to bring up any AuxData associated with the current line. Navigate to definitions by putting the cursor on a symbol and hitting F12 (or right click and select "Go To Definition").  You can also get referents to a function (or label) by going to the definition, right-clicking in the first block of instructions, and selecting "Find All References" (Alt+Shift+F12). More functionality will be added over time.

## Running in the repository

- Run `npm install` in this folder. This installs all necessary npm modules in both the client and server folder.
- Open VS Code on this folder.
- Open settings.json in the .vscode directory and check that "python.pythonPath" is correct for your system.
- Press Ctrl+Shift+B (Apple+Shift+B on a Mac) to compile the extension.
- Switch to the Debug viewlet.
- Select `Launch Client+Server` from the drop down.
- Run the launch config. This will start a TCP-based LSP server and add the client code to VSCode.
- In the [Extension Development Host] instance of vscode, open a folder with a ".gtirb" file in it and click the file to open it.

## Installing the pre-built extension

To install the extension as prebuilt VSIX file, go to the package registry and click on the latest version of gtirb-vscode. You will see a list of builds for this version, click on the most recent build to download it. To install into VSCode, run the following command in the folder you downloaded to:
```
% code --install-extension gtirb-vsix-VERSION.vsix
```
And start or restart vscode. The extension will start up automatically whenever you open a file with the ".gtirb" extension. You can uninstall the extension from within the GUI, or with the following command:
```
% code --uninstall-extension gtirb-vsix-VERSION.vsix
```

## Configuration options

The extension adds two configuration settings to configure the connection between client and LSP server. You can find these in the extension settings under "GTIRB Server Configuration"
- **Host**: (IP address of server): Set this to "localhost" (default) for an LSP server running on the same host as the client, or host IP address if remote. To configure the extension to create a dedicated LSP server running as a subprocess to the GTIRB extension (client), use "stdio" for host. The subprocess will exit when the client disconnects.
- **Port** (Port to connect to): This defaults to 3036, but can be changed to any convenient port number. If you are using something other than the default, be sure to use the same port when starting the LSP server. When the LSP server is a dedicated subprocess (host = "stdio") the port number is ignored.

## Installing the LSP server as a separate python package

To install with pip, got to the gtirb_lsp_server directory and run:
```
% pip3 install .
```

The LSP server optionally supports some limited binary rewriting capability. Some additional python packages are needed, to install these with pip go to the gtirb_lsp_server directory and run:
```
% pip3 install -r requirements-rewriting.txt
```
Or, to install the GTIRB LSP server and dependencies, including packages needed for rewriting capability:
```
% pip3 install .[rewriting]
```

## Running the LSP server

Server start-up and connection may be automatic or manual depending on the way you are running:
- If you have installed the extension and the host (in GTIRB Server Configration settings) is "stdio", a server is started for you when the client starts up, and stopped when the client exits.
- If you are running in the repository, use the "Launch Server (TCP)" configuration to start an LSP server before starting a client, or use "Launch Client+Server" to start both. The server will not exit when the client disconnects, you can use Ctrl-C in the terminal window to close it.
- You can also start the LSP Server manually using the command line below.

To start the LSP server:
```
% gtirb_lsp_server --tcp [ --host HOST ] [ --port PORT ] [ --verbose | --very-verbose ]
```
Where:
- HOST is the server IP address, the default is 127.0.0.1
- PORT is the TCP port, the default is 3036
- Default logging is to report errors, use verbose or very-verbose for additional levels of logging.

*NOTE* VSCode records user configuration settings in a file that persists, even when extensions are uninstalled. You may need to edit this file to reset the GTIRB Server host configuration. The path to this file depends on your host OS and version, some possibilities are:
- Linux: $HOME/.config/Code/User/settings/json
- Windows: C:\Users\%USERNAME%\AppData\Roaming\Code\User\Settings.json

## Copyright and Acknowledgments

Copyright (C) 2022 GrammaTech, Inc.

This code is licensed under the GPLv3 license. See the LICENSE file in the project root for license terms.

This project is sponsored by the Office of Naval Research, One Liberty Center, 875 N. Randolph Street, Arlington, VA 22203 under contract #N68335-17-C-0700. The content of the information does not necessarily reflect the position or policy of the Government and no official endorsement should be inferred.
