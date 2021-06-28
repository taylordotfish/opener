# This file contains code originally from esprima-python
# (https://github.com/Kronuz/esprima-python), which is covered
# by the following copyright and license notice:
#
#   Copyright JS Foundation and other contributors, https://js.foundation/
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#   AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#   IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
#   ARE DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
#   DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#   (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#   SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#   CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
#   LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
#   OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
#   DAMAGE.
#
# All modifications in this file are released under the same license
# as the original.

from esprima.visitor import Visited, Visitor


def to_dict(node):
    return ToDictVisitor().visit(node)


class ToDictVisitor(Visitor):
    map = {
        "isAsync": "async",
        "allowAwait": "await",
    }

    def visit_RecursionError(self, obj):
        yield Visited({
            "error": "Infinite recursion detected...",
        })

    def visit_Object(self, obj):
        obj = yield obj.__dict__
        yield Visited(obj)

    def visit_list(self, obj):
        items = []
        for item in obj:
            v = yield item
            items.append(v)
        yield Visited(items)

    visit_Array = visit_list

    def visit_dict(self, obj):
        items = []
        for k, item in obj.items():
            if not k.startswith("_"):
                v = yield item
                k = str(k)
                items.append((self.map.get(k, k), v))
        yield Visited(dict(items))

    def visit_SRE_Pattern(self, obj):
        yield Visited({})
