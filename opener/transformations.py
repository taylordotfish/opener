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

from esprima.visitor import Visitor as BaseVisitor
from esprima.nodes import Node
from esprima.nodes import (
    AssignmentExpression, BinaryExpression, BlockStatement, CallExpression,
    ConditionalExpression, ExpressionStatement, Identifier, IfStatement,
    Literal, Property, StaticMemberExpression, VariableDeclaration,
    VariableDeclarator, UnaryExpression,
)

from functools import wraps
from typing import Optional


class State:
    def __init__(self, temp_prefix=DEFAULT_TEMP_PREFIX):
        self.id_num = 0
        self.temp_prefix = temp_prefix

    def make_id_str(self) -> str:
        self.id_num += 1
        return f"{self.temp_prefix}{self.id_num}"

    def make_id(self) -> Identifier:
        return Identifier(self.make_id_str())


def is_const(node) -> bool:
    class Visitor(BaseVisitor):
        def __init__(self):
            self.all_const = True

        def visit_Object(self, node):
            self.all_const = False

        def visit_Literal(self, node):
            pass

        def visit_LogicalExpression(self, node):
            return super().visit_Object(node)

        def visit_BinaryExpression(self, node):
            return super().visit_Object(node)

        def visit_UnaryExpression(self, node):
            return super().visit_Object(node)

        def visit_ConditionalExpression(self, node):
            return super().visit_Object(node)

        def visit_FunctionExpression(self, node):
            pass

    visitor = Visitor()
    visitor.visit(node)
    return visitor.all_const


def is_no_op(node) -> bool:
    return node.type == "Identifier" or is_const(node)


def uses_function_context(node) -> bool:
    class Visitor(BaseVisitor):
        def __init__(self):
            self.uses_context = False

        def visit_FunctionExpression(self, node):
            pass

        def visit_ThisExpression(self, node):
            self.uses_context = True

        def visit_Identifier(self, node):
            if node.name == "arguments":
                self.uses_context = True

    visitor = Visitor()
    visitor.visit(node)
    return visitor.uses_context


def track_shallow_identity_difference(func):
    """Decorator that sets ``self._changed`` to ``True`` if the node returned
    by the wrapped method is different from the provided node (checked
    shallowly using the ``is`` operator).
    """
    @wraps(func)
    def result(self, node, *args, **kwargs):
        new_node = func(self, node, *args, **kwargs)
        self._changed |= node is not new_node
        return new_node
    return result


def conditional_to_if(
    node: ConditionalExpression,
    dest: str,
) -> IfStatement:
    if node.alternate.type == "ConditionalExpression":
        alternate = conditional_to_if(node.alternate, dest)
    else:
        alternate = ExpressionStatement(AssignmentExpression(
            operator="=",
            left=Identifier(dest),
            right=node.alternate
        ))
    return IfStatement(
        test=node.test,
        consequent=ExpressionStatement(AssignmentExpression(
            operator="=",
            left=Identifier(dest),
            right=node.consequent,
        )),
        alternate=alternate,
    )


class Unsequence:
    def __init__(self, state: State):
        self.state = state
        self._changed = False

    def process_node(self, node: Node):
        if node.type in ["Program", "BlockStatement"]:
            self.process_block(node)
        elif node.type == "SwitchCase":
            self.process_block(node, body_attr="consequent")

    def process_block(self, node: Node, *, body_attr="body"):
        while True:
            self._changed = False
            self.process_block_once(node, body_attr=body_attr)
            if not self._changed:
                break

    def process_block_once(self, node: Node, *, body_attr="body"):
        children = []
        for i, child in enumerate(getattr(node, body_attr)):
            new_child = self.handle_statement(child, children)
            if new_child is not None:
                children.append(new_child)

        # It's possible for the two lengths to be equal, even when there
        # are new additions, if there were an equal number of additions and
        # deletions, but deletions imply that `self._changed` has already been
        # set to `True`, as they involve `handle_statement()` returning a
        # different node type (`None` rather than whatever statement type was
        # passed in).
        self._changed |= len(children) != len(getattr(node, body_attr))
        setattr(node, body_attr, children)

    @track_shallow_identity_difference
    def handle_statement(
        self,
        node: Node,
        additions: list[Node],
    ) -> Optional[Node]:
        if node.type == "ExpressionStatement":
            return self.handle_expression_statement(node, additions)

        if node.type in ["ReturnStatement", "ThrowStatement"]:
            if node.argument is not None:
                node.argument = self.handle_expression(
                    node.argument,
                    additions,
                )
            return node

        if node.type == "VariableDeclaration":
            if not node.declarations:
                return node

            if len(node.declarations) > 1:
                additions += (
                    VariableDeclaration(declarations=[decl], kind=node.kind)
                    for decl in node.declarations[:-1]
                )
                node.declarations = [node.declarations[-1]]
                return node

            decl = node.declarations[0]
            if decl.init is not None:
                decl.init = self.handle_expression(decl.init, additions)
            return node

        if node.type == "IfStatement":
            node.test = self.handle_expression(node.test, additions)
            cons_additions = []
            new_cons = self.handle_statement(node.consequent, cons_additions)
            if cons_additions:
                if new_cons is not None:
                    cons_additions.append(new_cons)
                new_cons = BlockStatement(cons_additions)

            new_alt = node.alternate
            if new_alt is not None:
                alt_additions = []
                new_alt = self.handle_statement(new_alt, alt_additions)
                if alt_additions:
                    if new_alt is not None:
                        alt_additions.append(new_alt)
                    new_alt = BlockStatement(alt_additions)

            if new_cons is not None:
                if new_cons.type == "IfStatement":
                    # Avoid dangling else ambiguity.
                    new_cons = BlockStatement([new_cons])
                node.consequent = new_cons
                node.alternate = new_alt
                return node

            if new_alt is not None:
                node.test = UnaryExpression(operator="!", argument=node.test)
                node.consequent = new_alt
                node.alternate = None
                return node
            return ExpressionStatement(node.test)

        if node.type in [
            "WhileStatement",
            "DoWhileStatement",
            "ForStatement",
            "ForOfStatement",
            "ForInStatement",
        ]:
            body_additions = []
            node.body = self.handle_statement(node.body, body_additions)
            if body_additions:
                body_additions.append(node.body)
                node.body = BlockStatement(body_additions)
            # Note: We don't return here, as there may be more specific
            # processing later.

        if node.type == "ForStatement":
            if node.init is None:
                pass
            elif node.init.type == "VariableDeclaration":
                node.init = self.handle_statement(node.init, additions)
            else:
                node.init = self.handle_expression(node.init, additions)

            if node.update is not None:
                update_additions = []
                node.update = self.handle_expression(
                    node.update,
                    update_additions,
                )
                if node.body.type != "BlockStatement":
                    node.body = BlockStatement([node.body])
                node.body.body += update_additions
            return node

        if node.type in ["ForOfStatement", "ForInStatement"]:
            node.right = self.handle_expression(node.right, additions)
            return node

        if node.type == "SwitchStatement":
            node.discriminant = self.handle_expression(
                node.discriminant,
                additions,
            )
            return node
        return node

    @track_shallow_identity_difference
    def handle_expression_statement(
        self,
        node: Node,
        additions: list[Node],
    ) -> Optional[Node]:
        expr = node.expression
        if is_no_op(expr):
            return None

        def handle_expression():
            node.expression = self.handle_expression(expr, additions)
            return node

        if expr.type == "LogicalExpression":
            if expr.operator not in ["&&", "||"]:
                return handle_expression()
            test = expr.left
            if expr.operator == "||":
                test = UnaryExpression(operator="!", argument=test)
            return self.handle_statement(IfStatement(
                test=test,
                consequent=ExpressionStatement(expr.right),
                alternate=None,
            ), additions)

        if expr.type == "ConditionalExpression":
            return self.handle_statement(IfStatement(
                test=expr.test,
                consequent=ExpressionStatement(expr.consequent),
                alternate=ExpressionStatement(expr.alternate),
            ), additions)
        return handle_expression()

    @track_shallow_identity_difference
    def handle_expression(
        self,
        node: Optional[Node],
        additions: list[Node],
    ) -> Optional[Node]:
        if node is None:
            return None

        if node.type == "SequenceExpression":
            additions += map(ExpressionStatement, node.expressions[:-1])
            return node.expressions[-1]

        if node.type == "AssignmentExpression":
            rhs_additions = []
            node.right = self.handle_expression(node.right, rhs_additions)
            if rhs_additions:
                node.left = self.pre_eval_assignment_lhs(node.left, additions)
                additions += rhs_additions
            else:
                # Note: We can use `handle_expression()` here because when
                # passed a `MemberExpression` or `Identifier`, it won't change
                # change the top-level type. But if `handle_expression()`, e.g,
                # replaced the whole `MemberExpression` with a temporary
                # variable, this would be incorrect.
                new_left = self.handle_expression(node.left, additions)
                if new_left is not node.left:
                    raise RuntimeError("Unexpected top-level change")
            return node

        if node.type == "UnaryExpression":
            node.argument = self.handle_expression(node.argument, additions)
            return node

        if node.type == "BinaryExpression":
            rhs_additions = []
            node.right = self.handle_expression(node.right, rhs_additions)
            if rhs_additions:
                node.left = self.pre_eval_expression(node.left, additions)
                additions += rhs_additions
            else:
                node.left = self.handle_expression(node.left, additions)
            return node

        if node.type == "MemberExpression":
            if node.computed:
                prop_additions = []
                node.property = self.handle_expression(
                    node.property,
                    prop_additions,
                )
                if prop_additions:
                    node.object = self.pre_eval_expression(
                        node.object,
                        additions,
                    )
                    additions += prop_additions
                    return node
            node.object = self.handle_expression(node.object, additions)
            return node

        if node.type in ["CallExpression", "NewExpression"]:
            arg_additions = []
            for i in reversed(range(len(node.arguments))):
                node.arguments[i] = self.handle_expression(
                    node.arguments[i],
                    arg_additions,
                )
                if arg_additions:
                    break
            else:
                # Note: We can use `handle_expression()` here because if
                # `node.callee` is a `MemberExpression`, its type won't be
                # changed by `handle_expression()` (e.g., it won't be stored
                # entirely in a temporary variable). This ensures that the
                # value of `this` in the called function will be the same.
                node.callee = self.handle_expression(node.callee, additions)
                return node
            modified_index = i

            if (
                node.type == "CallExpression" and
                node.callee.type == "MemberExpression"
            ):
                if node.callee.object.type != "Identifier":
                    node.callee.object = self.store_in_temporary(
                        node.callee.object,
                        additions,
                    )
                obj = Identifier(node.callee.object.name)
                node.callee = StaticMemberExpression(
                    object=self.pre_eval_expression(node.callee, additions),
                    property=Identifier("call"),
                )
                node.arguments.insert(0, obj)
            else:
                node.callee = self.pre_eval_expression(node.callee, additions)

            for i in range(modified_index):
                node.arguments[i] = self.pre_eval_expression(
                    node.arguments[i],
                    additions,
                )
            additions += arg_additions
            return node

        if node.type == "LogicalExpression":
            if node.operator not in ["&&", "||"]:
                return node
            rhs_additions = []
            rhs = self.handle_expression(node.right, rhs_additions)
            if rhs_additions:
                lhs = self.store_in_temporary(
                    node.left,
                    additions,
                    const=False,
                )
                rhs_additions.append(ExpressionStatement(AssignmentExpression(
                    operator="=",
                    left=lhs,
                    right=rhs,
                )))
                test = lhs
                if node.operator == "||":
                    test = UnaryExpression(operator="!", argument=test)
                additions.append(IfStatement(
                    test=test,
                    consequent=BlockStatement(rhs_additions),
                    alternate=None,
                ))
                return lhs
            node.left = self.handle_expression(node.left, additions)
            return node

        if node.type == "ConditionalExpression":
            if node.alternate.type == "ConditionalExpression":
                result = self.store_in_temporary(None, additions, const=False)
                additions.append(conditional_to_if(node, dest=result.name))
                return result

            cons_additions = []
            cons = self.handle_expression(node.consequent, cons_additions)
            alt_additions = []
            alt = self.handle_expression(node.alternate, alt_additions)
            if cons_additions or alt_additions:
                result = self.store_in_temporary(None, additions, const=False)
                cons_additions.append(ExpressionStatement(AssignmentExpression(
                    operator="=",
                    left=result,
                    right=cons,
                )))
                alt_additions.append(ExpressionStatement(AssignmentExpression(
                    operator="=",
                    left=result,
                    right=alt,
                )))
                additions.append(IfStatement(
                    node.test,
                    consequent=BlockStatement(cons_additions),
                    alternate=BlockStatement(alt_additions),
                ))
                return result
            node.test = self.handle_expression(node.test, additions)
            return node

        if node.type == "ArrayExpression":
            elem_additions = []
            for i in reversed(range(len(node.elements))):
                node.elements[i] = self.handle_expression(
                    node.elements[i],
                    elem_additions,
                )
                if elem_additions:
                    break
            else:
                return node

            modified_index = i
            for i in range(modified_index):
                node.elements[i] = self.pre_eval_expression(
                    node.elements[i],
                    additions,
                )
            additions += elem_additions
            return node

        if node.type == "ObjectExpression":
            prop_additions = []
            for i in reversed(range(len(node.properties))):
                node.properties[i] = self.handle_property(
                    node.properties[i],
                    prop_additions
                )
                if prop_additions:
                    break
            else:
                return node

            modified_index = i
            for i in range(modified_index):
                node.properties[i] = self.pre_eval_property(
                    node.properties[i],
                    additions,
                )
            additions += prop_additions
            return node
        return node

    @track_shallow_identity_difference
    def handle_property(
        self,
        node: Property,
        additions: list[Node],
    ) -> Property:
        if node.shorthand and not node.method:
            if node.computed:
                raise ValueError("Property should not be computed")
            return node

        if node.method:
            if node.value.type != "FunctionExpression":
                raise ValueError("Expected FunctionExpression")
        else:
            value_additions = []
            node.value = self.handle_expression(node.value, value_additions)
            if value_additions:
                if node.computed:
                    node.key = self.pre_eval_property_key(node.key, additions)
                additions += value_additions
                return node

        if node.computed:
            node.key = self.handle_expression(node.key, additions)
        return node

    def store_in_temporary(
        self,
        expr: Optional[Node],
        additions: list[Node], *,
        const=False,
    ) -> Identifier:
        ident = self.state.make_id()
        declarator = VariableDeclarator(id=ident, init=expr)
        additions.append(VariableDeclaration(
            declarations=[declarator],
            kind=("const" if const else "let"),
        ))
        return ident

    @track_shallow_identity_difference
    def pre_eval_expression(
        self,
        expr: Optional[Node],
        additions: list[Node],
    ) -> Optional[Node]:
        expr = self.handle_expression(expr, additions)
        if is_no_op(expr):
            return expr
        return self.store_in_temporary(expr, additions)

    @track_shallow_identity_difference
    def pre_eval_assignment_lhs(
        self,
        lhs: Node,
        additions: list[Node],
    ) -> Node:
        if lhs.type == "Identifier":
            return lhs
        if lhs.type != "MemberExpression":
            raise ValueError(f"Unexpected assignment LHS type: {lhs.type}")
        lhs.object = self.pre_eval_expression(lhs.object, additions)
        if lhs.computed:
            lhs.property = self.pre_eval_expression(lhs.property, additions)
        return lhs

    @track_shallow_identity_difference
    def pre_eval_property(
        self,
        node: Property,
        additions: list[Node],
    ) -> Property:
        if node.shorthand and not node.method:
            if node.computed:
                raise ValueError("Property should not be computed")
            return node
        if node.computed:
            node.key = self.pre_eval_property_key(node.key, additions)
        if node.method:
            if node.value.type != "FunctionExpression":
                raise ValueError("Expected FunctionExpression")
        else:
            node.value = self.pre_eval_expression(node.value, additions)
        return node

    @track_shallow_identity_difference
    def pre_eval_property_key(self, node: Node, additions: list[Node]) -> Node:
        if is_const(node):
            return node
        return self.store_in_temporary(BinaryExpression(
            operator="+",
            left=Literal(value="", raw='""'),
            right=node,
        ), additions)


class Respelling:
    def process_node(self, node: Node):
        for key, value in node.items():
            if isinstance(value, list):
                for i, elem in enumerate(value):
                    if isinstance(elem, Node):
                        value[i] = self.handle_child(elem)
            elif isinstance(value, Node):
                setattr(node, key, self.handle_child(value))

    def handle_child(self, node: Node) -> Node:
        if (
            node.type == "UnaryExpression" and
            node.operator == "void" and
            node.argument.type == "Literal"
        ):
            return Identifier("undefined")

        if (
            node.type == "UnaryExpression" and
            node.operator == "!" and
            node.argument.type == "Literal" and
            type(node.argument.value) is int
        ):
            value = not node.argument.value
            return Literal(value=value, raw="true" if value else "false")
        return node


class IfBraces:
    def process_node(self, node: Node):
        if node.type == "IfStatement":
            node.consequent = self.handle_body(node.consequent)
            if node.alternate is not None:
                node.alternate = self.handle_alternate(node.alternate)
            return

        if node.type in [
            "WhileStatement",
            "DoWhileStatement",
            "ForStatement",
            "ForInStatement",
            "ForOfStatement",
        ]:
            node.body = self.handle_body(node.body)
            return

    def handle_body(self, node: Node):
        if node.type not in ["BlockStatement", "EmptyStatement"]:
            return BlockStatement([node])
        return node

    def handle_alternate(self, node: Node):
        if node.type == "IfStatement":
            return node
        return self.handle_body(node)


class FlattenInvoked:
    def process_node(self, node: Node):
        for key, value in node.items():
            if isinstance(value, list):
                for i, elem in enumerate(value):
                    if isinstance(elem, Node):
                        value[i] = self.flatten(elem)
            elif isinstance(value, Node):
                setattr(node, key, self.flatten(value))

    def flatten(self, node: Node) -> Node:
        while True:
            new_node = self.flatten_once(node)
            if new_node is node:
                return new_node
            node = new_node

    def flatten_once(self, node: Node) -> Node:
        if not (
            node.type == "CallExpression" and
            not node.arguments and
            node.callee.type == "FunctionExpression" and
            not node.callee.params and
            node.callee.body.type == "BlockStatement" and
            len(node.callee.body.body) == 1 and
            node.callee.body.body[0].type == "ReturnStatement" and
            not uses_function_context(node.callee.body)
        ):
            return node
        return node.callee.body.body[0].argument


class LabelFunctionArray:
    def process_node(self, node: Node):
        if node.type == "VariableDeclarator":
            self.process_declarator(node)

    def process_declarator(self, node: VariableDeclarator):
        if not (node.init is not None and node.init.type == "ArrayExpression"):
            return
        for i, child in enumerate(node.init.elements):
            if child.type != "FunctionExpression":
                continue
            if child.id is not None:
                continue
            child.id = Identifier(f"{node.id.name}{i}")


# For debugging JS code: wraps a bunch of expressions in calls to `__wrap()`,
# which can perform arbitrary processing.
class AddWrapCalls:
    def process_node(self, node: Node):
        if node.type == "ReturnStatement":
            node.argument = self.wrap(node.argument)
        elif node.type == "VariableDeclarator":
            node.init = self.wrap(node.init)
        elif node.type == "AssignmentExpression":
            node.right = self.wrap(node.right)

    def wrap(self, expr: Optional[Node]) -> Optional[Node]:
        if expr is None:
            return expr
        return CallExpression(callee=Identifier("__wrap"), args=[expr])


def transform(ast: Node, temp_prefix=DEFAULT_TEMP_PREFIX):
    state = State(temp_prefix=temp_prefix)
    passes = [
        Unsequence(state),
        Respelling(),
        IfBraces(),
        FlattenInvoked(),
        LabelFunctionArray(),
    ]

    def process_node(node: Node):
        for tf_pass in passes:
            tf_pass.process_node(node)

    class Visitor(BaseVisitor):
        def visit_Object(self, node):
            if isinstance(node, Node):
                process_node(node)
            return super().visit_Object(node)
    Visitor().visit(ast)
