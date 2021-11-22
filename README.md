# GTIRB GUI

A VSCode extension for viewing and navigating GTIRB, Grammatech's IR for Binaries.

## Prerequisites

- vscode (https://code.visualstudio.com/download).
- python 3.6+.
- You must have gtirb available as a python package and gtirb-pprinter version 1.8.2, which supports UI listing mode.
- The pygls python packages is required (can be installed with 'pip install pygls').

## Functionality

This extension will load a GTIRB file and display an assembly file listing of the file contents. Hovering will bring up any AuxData associated with the current line, and you can navigate to definitions by putting the cursor on a symbol and hitting F12 (or right click and select "Go To Definition").  You can also get referents to a function (or label) by going to the definition, right-clicking in the first block of instructions, and selecting "Find All References" (Alt+Shift+F12)

## Running in the repository

- Run `npm install` in this folder. This installs all necessary npm modules in both the client and server folder.
- Open VS Code on this folder.
- Open settings.json in the .vscode directory and check that "python.pythonPath" is correct for your system.
- Press Ctrl+Shift+B (Apple+Shift+B on a Mac) to compile the extension.
- Switch to the Debug viewlet.
- Select `Launch Client+Server` from the drop down.
- Run the launch config.
- In the [Extension Development Host] instance of vscode, open a folder with a ".gtirb" file in it and click the file to open it.

## Installing the pre-built extension

You can install the extension as a .vsix file, and it will appear in vscode with all your other installed extensions. To install, run the following command in this folder:
- code --install-extension gtirb-vsix-0.0.1.vsix

And start vscode. You should now see GTIRB in your list of extensions. The extension will start up automatically whenever you open a file with the ".gtirb" extension. You can uninstall the extension from within the GUI, or with the following command:
- code --uninstall-extension gtirb-vsix-0.0.1.vsix


## Building the LSP server as a separate python package

The file setup.py provides build information to build the LSP server with. To build a wheel that can be installed with pip:
- python3 setup.py build
- python3 -m build --wheel
