# GTIRB GUI

A VSCode extension for viewing and navigation GTIRB, Grammatech's IR for Binaries.

## Functionality

This extension will load a GTIRB file and display an assembly file listing of the file contents.

## Running the Sample

- Run `npm install` in this folder. This installs all necessary npm modules in both the client and server folder
- Open VS Code on this folder.
- Open settings.json in the .vscode directory and check that "python.pythonPath" is correct for your system.
- Press Ctrl+Shift+B to compile the extension
- Switch to the Debug viewlet.
- Select `Launch Client+Server` from the drop down.
- Run the launch config.
- In the [Extension Development Host] instance of VSCode, open a folder with a ".gtirb" file in it and click the file to open it.

## Building the LSP server as a separate python package

The file setup.py provides build information to build the LSP server with. To build a wheel that can be installed with pip:
- python3 setup.py build
- python3 -m build --wheel 
