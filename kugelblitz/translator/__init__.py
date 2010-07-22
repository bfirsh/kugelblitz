try:
    import ast
except ImportError:
    from kugelblitz.lib import ast

class CompileError(RuntimeError):
    pass

def translate(tree, **kwargs):
    return {
        ast.FunctionDef: translate_function,
        ast.Module: translate_module,
        ast.Return: translate_return,
        ast.Name: translate_name,
        ast.ClassDef: translate_class,
        ast.Assign: translate_assign,
        ast.Attribute: translate_attribute,
        ast.Num: translate_num,
        ast.Tuple: translate_tuple,
        ast.BoolOp: translate_bool_op,
        ast.BinOp: translate_bin_op,
        ast.Compare: translate_compare,
        ast.UnaryOp: translate_unary_op,
        ast.Lambda: translate_lambda,
        ast.Call: translate_call,
        ast.If: translate_if,
        ast.IfExp: translate_if_exp,
        ast.Expr: lambda n: translate(n.value),
        
        ast.And: lambda _: '&&',
        ast.Or: lambda _: '||',
        ast.Add: lambda _: '+',
        ast.Sub: lambda _: '-',
        ast.Mult: lambda _: '*',
        ast.Div: lambda _: '/', # TODO: Handle integers
        ast.Mod: lambda _: '%',
        ast.LShift: lambda _: '<<',
        ast.RShift: lambda _: '>>',
        ast.BitOr: lambda _: '|',
        ast.BitXor: lambda _: '^',
        ast.BitAnd: lambda _: '&',
        ast.FloorDiv: lambda _: '/',
        ast.Invert: lambda _: '~',
        ast.Not: lambda _: '!',
        ast.UAdd: lambda _: '+',
        ast.USub: lambda _: '-',
        
        ast.Eq: lambda _: '==',
        ast.Lt: lambda _: '<',
        ast.LtE: lambda _: '<=',
        ast.Gt: lambda _: '>',
        ast.GtE: lambda _: '>=',
    }[tree.__class__](tree, **kwargs)

def translate_body(body, line_separator='\n'):
    s = []
    for node in body:
        if isinstance(node, (ast.If,)):
            s.append(translate(node))
        else:
            s.append('%s;' % translate(node))
    return '\n'.join(s)

def translate_module(node):
    return translate_body(node.body, line_separator='\n\n')

def translate_function(node, instance_method=False):
    """
    Translates a function. If self_var is not none, it behaves as
    an instance method.
    """
    # Generate argument definition
    if instance_method:
        args_def = ", ".join([arg.id for arg in node.args.args[1:]])
        return "function (%(args_def)s) { %(body_def)s }" % {
            "args_def": args_def,
            "body_def": translate_body(node.body),
        }
    else:
        args_def = ", ".join([arg.id for arg in node.args.args])
        return "var %(name)s = function (%(args_def)s) { %(body_def)s }" % {
            "args_def": args_def,
            "body_def": translate_body(node.body),
            "name": node.name,
        }

def translate_return(node):
    return "return %s" % translate(node.value)

def translate_lambda(node):
    return "function(%(args_def)s) {\nreturn %(body_def)s\n}" % {
        'args_def': ", ".join([arg.id for arg in node.args.args]),
        'body_def': translate_body([node.body]),
    }

def translate_if(node):
    s = ["if (%(test_def)s) { %(body_def)s }" % {
        'test_def': translate(node.test),
        'body_def': translate_body(node.body),
    }]
    if node.orelse:
        s.append("else { %(orelse_def)s }" % {
            's': s,
            'orelse_def': translate_body(node.orelse),
        })
    return '\n'.join(s)

def translate_if_exp(node):
    return '%(test)s ? %(body)s : %(orelse)s' % {
        'test': translate(node.test),
        'body': translate(node.body),
        'orelse': translate(node.orelse),
    }

def translate_name(node):
    if node.id == "self":
        return "this"
    else:
        return node.id
    
def translate_tuple(node):
    return "?tuple?"
    
def translate_bool_op(node):
    return "(%(left)s %(op)s %(right)s)" % {
        'left': translate(node.values[0]),
        'op': translate(node.op),
        'right': translate(node.values[1]),
    }

def translate_bin_op(node):
    if isinstance(node.op, ast.Pow):
        return "Math.pow(%s, %s)" % tuple(map(translate, [node.left, node.right]))
    return "(%(left)s %(op)s %(right)s)" % {
        'left': translate(node.left),
        'op': translate(node.op),
        'right': translate(node.right),
    }

def translate_unary_op(node):
    return "".join(map(translate, [node.op, node.operand]))

def translate_attribute(node):
    return "%(left)s.%(right)s" % {
        "left": translate(node.value),
        "right": node.attr,
    }

def translate_assign(node):
    # For each target...
    statements = []
    for target in node.targets:
        # Is it a tuple-to-tuple assignment?
        if isinstance(target, ast.Tuple):
            # Is the RHS a tuple?
            if isinstance(node.value, ast.Tuple):
                # Make sure they're the same length
                if len(target.elts) != len(node.value.elts):
                    raise CompileError("Assigning one tuple to another of different length.")
                for t, v in zip(target.elts, node.value.elts):
                    statements.append("%(target)s = %(value)s" % {
                        'value': translate(v),
                        'target': translate(t),
                    })
            # No? Raise an error for now.
            else:
                raise CompileError("Assigning a non-tuple to a tuple.")
        else:
            statements.append("%(target)s = %(value)s" % {
                'value': translate(node.value),
                'target': translate(target),
            })
    return ";\n".join(statements)

def translate_num(node):
    return str(node.n)

def translate_call(node):
    args_def = ", ".join(map(translate, node.args))
    return "%(func)s(%(args_def)s)" % {
        "func": translate(node.func),
        "args_def": args_def,
    }

def translate_compare(node):
    assert len(node.ops) == 1, "Cannot have multiple comparison"
    assert len(node.comparators) == 1, "Cannot have multiple comparison"
    return "(%(left)s %(op)s %(comparator)s)" % {
        "left": translate(node.left),
        "op": translate(node.ops[0]),
        "comparator": translate(node.comparators[0]),
    }
    

def translate_class(node):
    
    # Is there an __init__?
    functions = {}
    assigns = {}
    classes = {}
    for item in node.body:
        if isinstance(item, ast.FunctionDef):
            functions[item.name] = item
        elif isinstance(item, ast.Assign):
            assert len(item.targets) == 1, "You can only assign to a single item."
            assert isinstance(item.targets[0], ast.Name), "You can only assign to simple names in classes"
            assigns[item.targets[0].id] = item.value

    # Make constructor def
    if "__init__" in functions:
        init_def = translate_function(functions['__init__'], instance_method=True)
    else:
        init_def = "function () {}"
    
    # Make other defs
    body = []
    for aname, anode in sorted(assigns.items()):
        body.append("'%s': %s" % (
            aname,
            translate(anode),
        ))
    
    # Make method defs
    for fname, fnode in sorted(functions.items()):
        if fname != "__init__":
            body.append("'%s': %s" % (
                fname,
                translate_function(fnode, instance_method=True),
            ))
    
    return "var %(name)s = %(init_def)s;\n%(name)s.prototype = { %(method_defs)s }" % {
        'name': node.name,
        'init_def': init_def,
        'method_defs': ",\n".join(body),
    }
