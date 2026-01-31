"""Custom Formula Expression Parser.

Parses and evaluates user-defined screening expressions.
"""

import re
import operator
import math
from typing import Any, Callable, Optional
import logging

logger = logging.getLogger(__name__)


class ExpressionError(Exception):
    """Expression parsing or evaluation error."""
    pass


class ExpressionParser:
    """Parses and evaluates custom formula expressions.
    
    Supports:
    - Arithmetic: +, -, *, /, %, ^
    - Comparison: >, <, >=, <=, ==, !=
    - Logical: and, or, not
    - Functions: abs, min, max, avg, sqrt, log, if
    
    Example:
        parser = ExpressionParser()
        result = parser.evaluate(
            "pe_ratio < 20 and revenue_growth > 0.10",
            {"pe_ratio": 15, "revenue_growth": 0.15}
        )
    """
    
    # Token patterns
    TOKEN_PATTERNS = [
        (r'\d+\.?\d*', 'NUMBER'),
        (r'[a-zA-Z_][a-zA-Z0-9_]*', 'IDENTIFIER'),
        (r'>=', 'GTE'),
        (r'<=', 'LTE'),
        (r'==', 'EQ'),
        (r'!=', 'NEQ'),
        (r'>', 'GT'),
        (r'<', 'LT'),
        (r'\+', 'PLUS'),
        (r'-', 'MINUS'),
        (r'\*', 'MULTIPLY'),
        (r'/', 'DIVIDE'),
        (r'%', 'MOD'),
        (r'\^', 'POWER'),
        (r'\(', 'LPAREN'),
        (r'\)', 'RPAREN'),
        (r',', 'COMMA'),
        (r'\s+', 'WHITESPACE'),
    ]
    
    # Built-in functions
    FUNCTIONS: dict[str, Callable] = {
        'abs': abs,
        'min': min,
        'max': max,
        'sqrt': math.sqrt,
        'log': math.log,
        'log10': math.log10,
        'exp': math.exp,
        'pow': pow,
        'round': round,
        'floor': math.floor,
        'ceil': math.ceil,
    }
    
    # Operators
    OPERATORS: dict[str, Callable] = {
        '+': operator.add,
        '-': operator.sub,
        '*': operator.mul,
        '/': operator.truediv,
        '%': operator.mod,
        '^': operator.pow,
        '>': operator.gt,
        '<': operator.lt,
        '>=': operator.ge,
        '<=': operator.le,
        '==': operator.eq,
        '!=': operator.ne,
    }
    
    # Keywords
    KEYWORDS = {'and', 'or', 'not', 'if', 'true', 'false'}
    
    def __init__(self):
        self._token_regex = re.compile(
            '|'.join(f'(?P<{name}>{pattern})' for pattern, name in self.TOKEN_PATTERNS)
        )
    
    def tokenize(self, expression: str) -> list[tuple[str, Any]]:
        """Tokenize an expression string.
        
        Args:
            expression: Expression string.
            
        Returns:
            List of (token_type, value) tuples.
        """
        tokens = []
        pos = 0
        
        while pos < len(expression):
            match = self._token_regex.match(expression, pos)
            if not match:
                raise ExpressionError(f"Invalid character at position {pos}: {expression[pos]}")
            
            token_type = match.lastgroup
            value = match.group()
            
            if token_type != 'WHITESPACE':
                if token_type == 'NUMBER':
                    value = float(value) if '.' in value else int(value)
                elif token_type == 'IDENTIFIER':
                    # Check for keywords
                    if value.lower() in self.KEYWORDS:
                        token_type = value.upper()
                        value = value.lower()
                tokens.append((token_type, value))
            
            pos = match.end()
        
        return tokens
    
    def parse(self, expression: str) -> 'ASTNode':
        """Parse an expression into an AST.
        
        Args:
            expression: Expression string.
            
        Returns:
            Root AST node.
        """
        tokens = self.tokenize(expression)
        parser = _Parser(tokens, self.FUNCTIONS)
        return parser.parse()
    
    def evaluate(
        self,
        expression: str,
        variables: dict[str, Any],
    ) -> Any:
        """Evaluate an expression with given variables.
        
        Args:
            expression: Expression string.
            variables: Variable values dict.
            
        Returns:
            Evaluation result.
        """
        try:
            ast = self.parse(expression)
            return ast.evaluate(variables, self.FUNCTIONS, self.OPERATORS)
        except Exception as e:
            logger.error(f"Expression error: {e}")
            raise ExpressionError(f"Failed to evaluate '{expression}': {e}")
    
    def validate(self, expression: str) -> tuple[bool, Optional[str]]:
        """Validate an expression.
        
        Args:
            expression: Expression string.
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        try:
            self.parse(expression)
            return True, None
        except Exception as e:
            return False, str(e)
    
    def get_variables(self, expression: str) -> set[str]:
        """Get variable names used in an expression.
        
        Args:
            expression: Expression string.
            
        Returns:
            Set of variable names.
        """
        tokens = self.tokenize(expression)
        variables = set()
        
        for i, (token_type, value) in enumerate(tokens):
            if token_type == 'IDENTIFIER':
                # Check if it's not a function call
                if value not in self.FUNCTIONS:
                    # Check if next token is LPAREN (function call)
                    if i + 1 < len(tokens) and tokens[i + 1][0] == 'LPAREN':
                        continue
                    variables.add(value)
        
        return variables


# =============================================================================
# AST Nodes
# =============================================================================

class ASTNode:
    """Base AST node."""
    
    def evaluate(
        self,
        variables: dict[str, Any],
        functions: dict[str, Callable],
        operators: dict[str, Callable],
    ) -> Any:
        raise NotImplementedError


class NumberNode(ASTNode):
    """Number literal node."""
    
    def __init__(self, value: float):
        self.value = value
    
    def evaluate(self, variables, functions, operators) -> float:
        return self.value


class BooleanNode(ASTNode):
    """Boolean literal node."""
    
    def __init__(self, value: bool):
        self.value = value
    
    def evaluate(self, variables, functions, operators) -> bool:
        return self.value


class VariableNode(ASTNode):
    """Variable reference node."""
    
    def __init__(self, name: str):
        self.name = name
    
    def evaluate(self, variables, functions, operators) -> Any:
        if self.name not in variables:
            raise ExpressionError(f"Unknown variable: {self.name}")
        return variables[self.name]


class BinaryOpNode(ASTNode):
    """Binary operation node."""
    
    def __init__(self, op: str, left: ASTNode, right: ASTNode):
        self.op = op
        self.left = left
        self.right = right
    
    def evaluate(self, variables, functions, operators) -> Any:
        left_val = self.left.evaluate(variables, functions, operators)
        right_val = self.right.evaluate(variables, functions, operators)
        
        if self.op == 'and':
            return bool(left_val) and bool(right_val)
        elif self.op == 'or':
            return bool(left_val) or bool(right_val)
        elif self.op in operators:
            return operators[self.op](left_val, right_val)
        else:
            raise ExpressionError(f"Unknown operator: {self.op}")


class UnaryOpNode(ASTNode):
    """Unary operation node."""
    
    def __init__(self, op: str, operand: ASTNode):
        self.op = op
        self.operand = operand
    
    def evaluate(self, variables, functions, operators) -> Any:
        val = self.operand.evaluate(variables, functions, operators)
        
        if self.op == '-':
            return -val
        elif self.op == 'not':
            return not bool(val)
        else:
            raise ExpressionError(f"Unknown unary operator: {self.op}")


class FunctionNode(ASTNode):
    """Function call node."""
    
    def __init__(self, name: str, args: list[ASTNode]):
        self.name = name
        self.args = args
    
    def evaluate(self, variables, functions, operators) -> Any:
        if self.name not in functions:
            raise ExpressionError(f"Unknown function: {self.name}")
        
        arg_values = [arg.evaluate(variables, functions, operators) for arg in self.args]
        return functions[self.name](*arg_values)


class IfNode(ASTNode):
    """Conditional if node."""
    
    def __init__(self, condition: ASTNode, true_val: ASTNode, false_val: ASTNode):
        self.condition = condition
        self.true_val = true_val
        self.false_val = false_val
    
    def evaluate(self, variables, functions, operators) -> Any:
        if self.condition.evaluate(variables, functions, operators):
            return self.true_val.evaluate(variables, functions, operators)
        return self.false_val.evaluate(variables, functions, operators)


# =============================================================================
# Parser
# =============================================================================

class _Parser:
    """Recursive descent parser for expressions."""
    
    def __init__(self, tokens: list[tuple[str, Any]], functions: dict[str, Callable]):
        self.tokens = tokens
        self.functions = functions
        self.pos = 0
    
    def parse(self) -> ASTNode:
        """Parse the token stream into an AST."""
        result = self._parse_or()
        if self.pos < len(self.tokens):
            raise ExpressionError(f"Unexpected token: {self.tokens[self.pos]}")
        return result
    
    def _current(self) -> Optional[tuple[str, Any]]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None
    
    def _consume(self, expected_type: Optional[str] = None) -> tuple[str, Any]:
        token = self._current()
        if token is None:
            raise ExpressionError("Unexpected end of expression")
        if expected_type and token[0] != expected_type:
            raise ExpressionError(f"Expected {expected_type}, got {token[0]}")
        self.pos += 1
        return token
    
    def _parse_or(self) -> ASTNode:
        """Parse OR expressions."""
        left = self._parse_and()
        
        while self._current() and self._current()[0] == 'OR':
            self._consume()
            right = self._parse_and()
            left = BinaryOpNode('or', left, right)
        
        return left
    
    def _parse_and(self) -> ASTNode:
        """Parse AND expressions."""
        left = self._parse_not()
        
        while self._current() and self._current()[0] == 'AND':
            self._consume()
            right = self._parse_not()
            left = BinaryOpNode('and', left, right)
        
        return left
    
    def _parse_not(self) -> ASTNode:
        """Parse NOT expressions."""
        if self._current() and self._current()[0] == 'NOT':
            self._consume()
            operand = self._parse_not()
            return UnaryOpNode('not', operand)
        
        return self._parse_comparison()
    
    def _parse_comparison(self) -> ASTNode:
        """Parse comparison expressions."""
        left = self._parse_additive()
        
        comp_ops = {'GT': '>', 'LT': '<', 'GTE': '>=', 'LTE': '<=', 'EQ': '==', 'NEQ': '!='}
        
        while self._current() and self._current()[0] in comp_ops:
            token = self._consume()
            op = comp_ops[token[0]]
            right = self._parse_additive()
            left = BinaryOpNode(op, left, right)
        
        return left
    
    def _parse_additive(self) -> ASTNode:
        """Parse addition/subtraction."""
        left = self._parse_multiplicative()
        
        while self._current() and self._current()[0] in ('PLUS', 'MINUS'):
            token = self._consume()
            op = '+' if token[0] == 'PLUS' else '-'
            right = self._parse_multiplicative()
            left = BinaryOpNode(op, left, right)
        
        return left
    
    def _parse_multiplicative(self) -> ASTNode:
        """Parse multiplication/division."""
        left = self._parse_power()
        
        while self._current() and self._current()[0] in ('MULTIPLY', 'DIVIDE', 'MOD'):
            token = self._consume()
            op = {'MULTIPLY': '*', 'DIVIDE': '/', 'MOD': '%'}[token[0]]
            right = self._parse_power()
            left = BinaryOpNode(op, left, right)
        
        return left
    
    def _parse_power(self) -> ASTNode:
        """Parse exponentiation."""
        left = self._parse_unary()
        
        if self._current() and self._current()[0] == 'POWER':
            self._consume()
            right = self._parse_power()  # Right associative
            left = BinaryOpNode('^', left, right)
        
        return left
    
    def _parse_unary(self) -> ASTNode:
        """Parse unary operators."""
        if self._current() and self._current()[0] == 'MINUS':
            self._consume()
            operand = self._parse_unary()
            return UnaryOpNode('-', operand)
        
        return self._parse_primary()
    
    def _parse_primary(self) -> ASTNode:
        """Parse primary expressions."""
        token = self._current()
        
        if token is None:
            raise ExpressionError("Unexpected end of expression")
        
        # Number
        if token[0] == 'NUMBER':
            self._consume()
            return NumberNode(token[1])
        
        # Boolean
        if token[0] == 'TRUE':
            self._consume()
            return BooleanNode(True)
        if token[0] == 'FALSE':
            self._consume()
            return BooleanNode(False)
        
        # Parenthesized expression
        if token[0] == 'LPAREN':
            self._consume()
            expr = self._parse_or()
            self._consume('RPAREN')
            return expr
        
        # If expression
        if token[0] == 'IF':
            return self._parse_if()
        
        # Identifier (variable or function)
        if token[0] == 'IDENTIFIER':
            name = token[1]
            self._consume()
            
            # Check if it's a function call
            if self._current() and self._current()[0] == 'LPAREN':
                return self._parse_function_call(name)
            
            # It's a variable
            return VariableNode(name)
        
        raise ExpressionError(f"Unexpected token: {token}")
    
    def _parse_function_call(self, name: str) -> ASTNode:
        """Parse function call."""
        self._consume('LPAREN')
        args = []
        
        if self._current() and self._current()[0] != 'RPAREN':
            args.append(self._parse_or())
            
            while self._current() and self._current()[0] == 'COMMA':
                self._consume()
                args.append(self._parse_or())
        
        self._consume('RPAREN')
        return FunctionNode(name, args)
    
    def _parse_if(self) -> ASTNode:
        """Parse if expression: if(condition, true_val, false_val)."""
        self._consume('IF')
        self._consume('LPAREN')
        
        condition = self._parse_or()
        self._consume('COMMA')
        true_val = self._parse_or()
        self._consume('COMMA')
        false_val = self._parse_or()
        
        self._consume('RPAREN')
        return IfNode(condition, true_val, false_val)
