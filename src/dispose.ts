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
import * as vscode from 'vscode';

export function disposeAll(disposables: vscode.Disposable[]): void {
    while (disposables.length) {
        const item = disposables.pop();
        if (item) {
            item.dispose();
        }
    }
}

export abstract class Disposable {
    private _isDisposed = false;

    protected _disposables: vscode.Disposable[] = [];

    public dispose(): any {
        if (this._isDisposed) {
            return;
        }
        this._isDisposed = true;
        disposeAll(this._disposables);
    }

    protected _register<T extends vscode.Disposable>(value: T): T {
        if (this._isDisposed) {
            value.dispose();
        } else {
            this._disposables.push(value);
        }
        return value;
    }

    protected get isDisposed(): boolean {
        return this._isDisposed;
    }
}
