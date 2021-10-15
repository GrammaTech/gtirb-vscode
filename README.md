# GTIRB Loader

Heavily documented sample code for https://code.visualstudio.com/api/language-extensions/language-server-extension-guide

## Functionality

This extension will load a GTIRB (Grammatech IR for Binaries) file and display an assembly file listing of the file contents.

## Running the Sample

- Run `npm install` in this folder. This installs all necessary npm modules in both the client and server folder
- Open VS Code on this folder.
- Press Ctrl+Shift+B to compile the loader
- Switch to the Debug viewlet.
- Select `Launch Extension` from the drop down.
- Run the launch config.
- In the [Extension Development Host] instance of VSCode, open a folder with a ".gtirb" file in it and lick the file in file explorer.
  - If GT X86/64 or MIPS  extensions are installed you should see proper syntax highlighting and be able to find all references and definitions for a selected token.
