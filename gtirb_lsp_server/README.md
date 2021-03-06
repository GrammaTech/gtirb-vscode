# GTIRB LSP Server

This tool provides an API and a command line utility for creating a GTIRB file from a raw binary file. A raw binary file is a file that contains executable code, but not in the typical ELF or PE formats. Any file can be converted to GTIRB, as long as information is about the program contained there is provided.

## Installation

To install this module on your system, first clone this repository. Then install using pip:
```shell
 % pip3 install .
```

To support GTIRB rewriting in the server, install the extra rewriting packages:
```shell
 % pip3 install .[rewriting]
```

To build a wheel for installing elsewhere:
```shell
 % python3 setup.py build
 % python3 setup.py bdist_wheel --dist-dir=$PWD
```

## As a command line tool

Starting STDIO server

```shell
% gtirb_lsp_server
```

Starting a TCP based server

```
% gtirb_lsp_server --tcp [ --host HOST ] [ --port PORT ] [-v [v]]
```

To run unit tests, install the server requirements (including dev requirements) and run pytest:

```shell
% pip3 install -r requirements.txt
% pip3 install -r requirements-dev.txt
% pytest
```
