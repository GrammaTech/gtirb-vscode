# GTIRB LSP Server

This tool provides an API and a command line utility for creating a GTIRB file from a raw binary file. A raw binary file is a file that contains executable code, but not in the typical ELF or PE formats. Any file can be converted to GTIRB, as long as information is about the program contained there is provided.

## Installation

To install this module on your system, first clone this repository. Then, build a wheel and install it, for example:
```
 % python3 setup.py build
 % python3 setup.py bdist_wheel --dist-dir=$PWD
 % pip3 install $PWD/cwgtirb_lsp_server-VERSION-py2.py3-none-any.whl
```

## As a command line tool

Starting STDIO server

```
% gtirb_lsp_server
```

Starting a TCP based server

```
% gtirb_lsp_server --tcp [ --host HOST ] [ --port PORT ]
```
