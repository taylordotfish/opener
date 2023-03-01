# Copyright (C) 2021 taylor.fish <contact@taylor.fish>
#
# This file is part of Opener.
#
# Opener is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Opener is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Opener. If not, see <https://www.gnu.org/licenses/>.

from .defaults import DEFAULT_TEMP_PREFIX

import json
import os
import os.path
import re
import subprocess
import sys

USAGE = """\
Usage:
  {0} [options] <js-file>
  {0} -h | --help

Options:
  -p --prefix=<prefix>  The prefix to use when creating temporary identifiers.
                        There should be no identifiers that consist of this
                        prefix followed by a sequence of digits in the input
                        code. [default: {1}]
              -a --ast  Output a JSON representation of the AST instead of JS.
          -v --verbose  Output additional messages to standard error.
""".format(os.path.basename(sys.argv[0]), DEFAULT_TEMP_PREFIX)


def _import():
    global transform
    from .transformations import transform
    global esprima, pkg_resources
    import esprima
    import pkg_resources


def usage(*, exit: bool, error: bool):
    print(USAGE, end="", file=(sys.stderr if error else sys.stdout))
    if exit:
        sys.exit(int(error))


def main():
    positional_args = []
    temp_prefix = DEFAULT_TEMP_PREFIX
    emit_ast = False
    verbose = False

    args = []
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            if "=" in arg:
                args += arg.split("=", 1)
            else:
                args.append(arg)
        elif arg.startswith("-"):
            iterator = enumerate(arg)
            next(iterator)
            for i, c in iterator:
                args.append(f"-{c}")
                if c in ["p"]:
                    break
            trailing = arg[i+1:]
            if trailing:
                args.append(trailing)
        else:
            args.append(arg)

    iterator = iter(args)
    for arg in iterator:
        if not arg.startswith("-"):
            positional_args.append(arg)
        elif arg in ["-h", "--help"]:
            usage(exit=True, error=False)
        elif arg in ["-p", "--prefix"]:
            try:
                temp_prefix = next(iterator)
            except StopIteration:
                print(f"Expected value after {arg}", file=sys.stderr)
                usage(exit=True, error=True)
        elif arg in ["-a", "--ast"]:
            emit_ast = True
        elif arg in ["-v", "--verbose"]:
            verbose = True
        else:
            print(f"Unrecognized option: {arg}", file=sys.stderr)
            usage(exit=True, error=True)

    if len(positional_args) != 1:
        usage(exit=True, error=True)

    with open(positional_args[0], encoding="utf8") as f:
        source = f.read()

    _import()
    if verbose:
        print("Parsing...", file=sys.stderr)
    ast = esprima.parseScript(source)

    if verbose:
        print("Deobfuscating...", file=sys.stderr)
    transform(ast, temp_prefix=temp_prefix)

    if verbose:
        print("Making AST JSON-serializable...", file=sys.stderr)
    ast_dict = esprima.toDict(ast)

    if emit_ast:
        if verbose:
            print("Printing AST...", file=sys.stderr)
        json.dump(ast_dict, sys.stdout)
    else:
        if verbose:
            print("Formatting code...", file=sys.stderr)

        try:
            import escodegen
        except ImportError:
            from warnings import warn
            warn("jscodegen has some issues and produces incorrect results (at least the version in the upstream repo when this remark was added here), better use https://github.com/0o120/escodegen-python")
            import jscodegen as escodegen

        print(escodegen.generate(ast_dict))


if __name__ == "__main__":
    main()
