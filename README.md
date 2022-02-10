# GTIRB GUI

A VSCode extension for viewing and navigating GTIRB, Grammatech's IR for Binaries. This extension is currently for internal use only and not licensed for distribution outside of GrammaTech.

## Prerequisites

This extension uses an LSP (language server protocol) server to add features to the VSCode UI. The LSP server is included with the extension.
- GTIRB UI (client) dependencies:
    - vscode (https://code.visualstudio.com/download).
    - gtirb-pprinter version 1.8.2 or higher, which supports UI listing mode.
- LSP Server (python) dependencies:
    - python 3.6+.
    - The gtirb python package.
    - Also the pygls python packages is required (can be installed with 'pip install pygls').
 - To support rewriting of GTIRB files (optional) the LSP server requires the following additional python packages
    - gtirb-rewriting
    - gtirb-functions
    - mcasm

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
% code --install-extension gtirb-vsix-0.0.1.vsix
```
And start or restart vscode. The extension will start up automatically whenever you open a file with the ".gtirb" extension. You can uninstall the extension from within the GUI, or with the following command:
```
% code --uninstall-extension gtirb-vsix-0.0.1.vsix
```

## Configuration options

The extension adds two configuration settings to configure the connection between client and LSP server. You can find these in the extension settings under "GTIRB Server Configuration"
- **Host**: (IP address of server): Set this to "localhost" (default) for an LSP server running on the same host as the client, or host IP address if remote. To configure the extension to create a dedicated LSP server running as a subprocess to the GTIRB extension (client), use "stdio" for host.
- **Port** (Port to connect to): This defaults to 3036, but can be changed to any convenient port number. If you are using something other than the default, be sure to use the same port when starting the LSP server. When the LSP server is a dedicated subprocess (host = "stdio") the port number is ignored.

## Building and installing the LSP server as a separate python package

The file setup.py provides build information to build the LSP server with. To build a wheel that can be installed with pip:
```
% python3 setup.py build
% python3 -m build --wheel
```

The LSP server optionally supports some limited binary rewriting capability. Some additional python packages are needed, to install these with pip go to the gtirb_lsp_server directory and run:
```
% pip3 install -r requirements-rewriting.txt
```
Or, to install the GTIRB LSP server and dependencies, including packages needed for rewriting capability:
```
% pip3 install -e .[rewriting]
```

## Running the LSP server

If you are running in the repository and using the "Launch Client+Server" launch configuration, or if you have installed the extensino and the host is "stdio" in the GTIRB Server Configration settings, a server is started for you when the client starts up, and stopped when the client exits. If you are not running in one of these configurations you will need to manually start the LSP server. Generally this should be done before the extension (client) is activated, otherwise it will generate an error when it tries to connect to the server.

To start the LSP server:
```
% python3 -m gtirb_lsp_server --tcp [ --host HOST ] [ --port PORT ] [ --verbose | --very-verbose ]
```
Where:
- HOST is the server IP address, the default is 127.0.0.1
- PORT is the TCP port, the default is 3036
- Default logging is to report errors, use verbose or very-verbose for additional levels of logging.
