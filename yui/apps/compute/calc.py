import ast
import asyncio
import datetime
import decimal
import functools
import html
import itertools
import math
import operator
import random
import statistics
from typing import Any, Callable, Dict, List, Optional, Set, Union

import _ast

from async_timeout import timeout

import ujson

from ...bot import Bot
from ...box import box
from ...event import Message
from ...types.channel import Channel

TIMEOUT = 1
LENGTH_LIMIT = 300

RESULT_TEMPLATE = {
    True: {
        True: {
            True: '*Expr*\n```{expr}```\n*Result*: Empty string',
            False: '*Expr*\n```{expr}```\n*Result*\n```{result}{more}```',
        },
        False: {
            True: '*Expr*\n```{expr}```\n*Result*: Empty string',
            False: '*Expr*\n```{expr}```\n*Result*: `{result}{more}`',
        }
    },
    False: {
        True: {
            True: '*Expr*: `{expr}`\n*Result*: Empty string',
            False: '*Expr*: `{expr}`\n*Result*\n```{result}{more}```',
        },
        False: {
            True: '`{expr}` == Empty string',
            False: '`{expr}` == `{result}{more}`',
        }
    },
}


async def body(
    bot: Bot,
    channel: Channel,
    expr: str,
    help: str,
    decimal_mode: bool = True,
    ts: str = None
):
    expr_is_multiline = '\n' in expr
    if not expr:
        await bot.say(channel, help)
        return

    result = None
    local = None
    try:
        async with timeout(TIMEOUT):
            result, local = await bot.run_in_other_thread(
                calculate,
                expr,
                decimal_mode=decimal_mode,
            )
    except SyntaxError as e:
        await bot.say(
            channel,
            '에러가 발생했어요! {}'.format(e),
            thread_ts=ts,
        )
        return
    except ZeroDivisionError:
        if expr_is_multiline:
            await bot.say(
                channel,
                '주어진 식은 0으로 나누게 되어요. 0으로 나누는 건 안 돼요!',
                thread_ts=ts,
            )
        else:
            await bot.say(
                channel,
                '`{}` 는 0으로 나누게 되어요. 0으로 나누는 건 안 돼요!'.format(expr),
                thread_ts=ts,
            )
        return
    except asyncio.TimeoutError:
        if expr_is_multiline:
            await bot.say(
                channel,
                '주어진 식은 실행하기엔 너무 오래 걸려요!',
                thread_ts=ts,
            )
        else:
            await bot.say(
                channel,
                '`{}` 는 실행하기엔 너무 오래 걸려요!'.format(expr),
                thread_ts=ts,
            )
        return
    except Exception as e:
        await bot.say(
            channel,
            '에러가 발생했어요! {}: {}'.format(e.__class__.__name__, e),
            thread_ts=ts,
        )
        return

    if result is not None:
        result_string = str(result)

        if result_string.count('\n') > 30:
            await bot.say(
                channel,
                '계산 결과에 개행이 너무 많이 들어있어요!',
                thread_ts=ts
            )
        else:
            await bot.say(
                channel,
                RESULT_TEMPLATE[
                    expr_is_multiline
                ][
                    '\n' in result_string
                ][
                    result_string.strip() == ''
                ].format(
                    expr=expr,
                    result=result_string[:300],
                    more='⋯' if len(result_string) > LENGTH_LIMIT else '',
                ),
                thread_ts=ts
            )
    elif local:
        r = '\n'.join(
            '{} = {}'.format(key, value)
            for key, value in local.items()
        )
        if r.count('\n') > 30:
            await bot.say(
                channel,
                '계산 결과에 개행이 너무 많이 들어있어요!',
                thread_ts=ts
            )
        else:
            if expr_is_multiline:
                await bot.say(
                    channel,
                    '*Expr*\n```{}```\n*Local*\n```{}```'.format(expr, r),
                    thread_ts=ts,
                )
            else:
                await bot.say(
                    channel,
                    '*Expr*: `{}`\n*Local*\n```{}```'.format(expr, r),
                    thread_ts=ts,
                )
    else:
        if expr_is_multiline:
            await bot.say(
                channel,
                '*Expr*\n```{}```\n*Local*: Empty'.format(expr),
                thread_ts=ts,
            )
        else:
            await bot.say(
                channel,
                '*Expr*: `{}`\n*Local*: Empty'.format(expr),
                thread_ts=ts,
            )


@box.command('=', ['calc'])
async def calc_decimal(bot, event: Message, raw: str):
    """
    정수타입 수식 계산기

    `{PREFIX}= 1+2+3`

    Python 문법과 모듈 일부가 사용 가능합니다.

    """

    await body(
        bot,
        event.channel,
        raw,
        '사용법: `{}= <계산할 수식>`'.format(bot.config.PREFIX),
        True,
    )


@box.command('=', ['calc'], subtype='message_changed')
async def calc_decimal_on_change(bot, event: Message, raw: str):
    if event.message:
        await body(
            bot,
            event.channel,
            raw,
            '사용법: `{}= <계산할 수식>`'.format(bot.config.PREFIX),
            True,
            event.message.ts,
        )


@box.command('==')
async def calc_num(bot, event: Message, raw: str):
    """
    부동소숫점타입 수식 계산기

    `{PREFIX}== 1+2+3`

    Python 문법과 모듈 일부가 사용 가능합니다.

    """

    await body(
        bot,
        event.channel,
        raw,
        '사용법: `{}== <계산할 수식>`'.format(bot.config.PREFIX),
        False,
    )


@box.command('==', subtype='message_changed')
async def calc_num_on_change(bot, event: Message, raw: str):
    if event.message:
        await body(
            bot,
            event.channel,
            raw,
            '사용법: `{}== <계산할 수식>`'.format(bot.config.PREFIX),
            False,
            event.message.ts,
        )


class Decimal(decimal.Decimal):

    def __neg__(self):
        return Decimal(super(Decimal, self).__neg__())

    def __pos__(self):
        return Decimal(super(Decimal, self).__pos__())

    def __abs__(self):
        return Decimal(super(Decimal, self).__abs__())

    def __add__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        return Decimal(super(Decimal, self).__add__(other))

    def __radd__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        return Decimal(super(Decimal, other).__add__(self))

    def __sub__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        return Decimal(super(Decimal, self).__sub__(other))

    def __rsub__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        return Decimal(super(Decimal, other).__sub__(self))

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        return Decimal(super(Decimal, self).__mul__(other))

    def __rmul__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        return Decimal(super(Decimal, other).__mul__(self))

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        return Decimal(super(Decimal, self).__truediv__(other))

    def __rtruediv__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        return Decimal(super(Decimal, other).__truediv__(self))

    def __floordiv__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        return Decimal(super(Decimal, self).__floordiv__(other))

    def __rfloordiv__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        return Decimal(super(Decimal, other).__floordiv__(self))

    def __mod__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        return Decimal(super(Decimal, self).__mod__(other))

    def __rmod__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        return Decimal(super(Decimal, other).__mod__(self))

    def __divmod__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        quotient, remainder = super(Decimal, self).__divmod__(other)
        return Decimal(quotient), Decimal(remainder)

    def __rdivmod__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        quotient, remainder = super(Decimal, other).__divmod__(self)
        return Decimal(quotient), Decimal(remainder)

    def __pow__(self, power, modulo=None):
        if isinstance(power, (int, float)):
            power = Decimal(power)
        return Decimal(super(Decimal, self).__pow__(power, modulo))

    def __rpow__(self, other):
        if isinstance(other, (int, float)):
            other = Decimal(other)
        return Decimal(super(Decimal, other).__pow__(self))


TYPE_STORE = type(ast.Store())
TYPE_LOAD = type(ast.Load())
TYPE_DEL = type(ast.Del())
TYPE_EXPR = type(ast.Expr())


class BadSyntax(Exception):
    pass


BINOP_TABLE: Dict[Any, Callable[[Any, Any], Any]] = {
    _ast.Add: lambda a, b: a + b,
    _ast.BitAnd: lambda a, b: a & b,
    _ast.BitOr: lambda a, b: a | b,
    _ast.BitXor: lambda a, b: a ^ b,
    _ast.Div: lambda a, b: a / b,
    _ast.FloorDiv: lambda a, b: a // b,
    _ast.LShift: lambda a, b: a << b,
    _ast.MatMult: lambda a, b: a @ b,
    _ast.Mult: lambda a, b: a * b,
    _ast.Mod: lambda a, b: a % b,
    _ast.Pow: lambda a, b: a ** b,
    _ast.RShift: lambda a, b: a >> b,
    _ast.Sub: lambda a, b: a - b,
}
BOOLOP_TABLE: Dict[Any, Callable[[Any, Any], Any]] = {
    _ast.And: lambda a, b: a and b,
    _ast.Or: lambda a, b: a or b,
}
COMPARE_TABLE: Dict[Any, Callable[[Any, Any], bool]] = {
    _ast.Eq: lambda a, b: a == b,
    _ast.Gt: lambda a, b: a > b,
    _ast.GtE: lambda a, b: a >= b,
    _ast.In: lambda a, b: a in b,
    _ast.Is: lambda a, b: a is b,
    _ast.IsNot: lambda a, b: a is not b,
    _ast.Lt: lambda a, b: a < b,
    _ast.LtE: lambda a, b: a <= b,
    _ast.NotEq: lambda a, b: a != b,
    _ast.NotIn: lambda a, b: a not in b,
}
UNARYOP_TABLE: Dict[Any, Callable[[Any], Any]] = {
    _ast.Invert: lambda x: ~x,
    _ast.Not: lambda x: not x,
    _ast.UAdd: lambda x: +x,
    _ast.USub: lambda x: -x,
}


class Evaluator:

    last_dump: str

    def __init__(self, decimal_mode: bool = False) -> None:
        self.decimal_mode = decimal_mode
        self.allowed_modules = {
            datetime: {
                'date',
                'datetime',
                'time',
                'timedelta',
                'tzinfo',
            },
            functools: {
                'reduce',
            },
            html: {
                'escape',
                'unescape',
            },
            itertools: {
                'accumulate',
                'chain',
                'chain.from_iterable',
                'compress',
                'dropwhile',
                'filterfalse',
                'groupby',
                'starmap',
                'takewhile',
                'tee',
                'zip_longest',
                'product',
                'permutations',
                'combinations',
                'combinations_with_replacement',
            },
            math: {
                'acos',
                'acosh',
                'asin',
                'asinh',
                'atan',
                'atan2',
                'atanh',
                'ceil',
                'copysign',
                'cos',
                'cosh',
                'degrees',
                'erf',
                'erfc',
                'exp',
                'expm1',
                'fabs',
                'factorial',
                'floor',
                'fmod',
                'frexp',
                'fsum',
                'gamma',
                'gcd',
                'hypot',
                'isclose',
                'isfinite',
                'isinf',
                'isnan',
                'ldexp',
                'lgamma',
                'log',
                'log1p',
                'log10',
                'log2',
                'modf',
                'pow',
                'radians',
                'sin',
                'sinh',
                'sqrt',
                'tan',
                'tanh',
                'trunc',
                'pi',
                'e',
                'tau',
                'inf',
                'nan',
            },
            operator: {
                'lt',
                'le',
                'eq',
                'ne',
                'ge',
                'gt',
                'not_',
                'truth',
                'is_',
                'is_not',
                'add',
                'and_',
                'floordiv',
                'index',
                'inv',
                'invert',
                'lshift',
                'mod',
                'mul',
                'matmul',
                'neg',
                'or_',
                'pos',
                'pow',
                'rshift',
                'sub',
                'truediv',
                'xor',
                'concat',
                'contains',
                'countOf',
                'delitem',
                'getitem',
                'indexOf',
                'setitem',
                'length_hint',
                'itemgetter',
            },
            random: {
                'randrange',
                'randint',
                'choice',
                'choices',
                'shuffle',
                'sample',
                'random',
                'uniform',
                'triangular',
                'betavariate',
                'expovariate',
                'gammavariate',
                'gauss',
                'lognormvariate',
                'normalvariate',
                'vonmisesvariate',
                'paretovariate',
                'weibullvariate',
            },
            statistics: {
                'mean',
                'harmonic_mean',
                'median',
                'median_low',
                'median_high',
                'median_grouped',
                'mode',
                'pstdev',
                'pvariance',
                'stdev',
                'variance',
            },
            ujson: {
                'dumps',
                'loads',
            },
        }
        self.allowed_class_properties = {
            bytes: {
                'fromhex',
                'maketrans',
            },
            datetime.date: {
                'today',
                'fromtimestamp',
                'fromordinal',
                'fromisoformat',
                'min',
                'max',
                'resolution',
            },
            datetime.datetime: {
                'today',
                'now',
                'utcnow'
                'fromtimestamp',
                'utcfromtimestamp',
                'fromordinal',
                'combine',
                'fromisoformat',
                'strptime',
                'min',
                'max',
                'resolution',
            },
            datetime.time: {
                'min',
                'max',
                'resolution',
                'fromisoformat',
            },
            datetime.timedelta: {
                'min',
                'max',
                'resolution',
            },
            datetime.timezone: {
                'utc',
            },
            dict: {
                'fromkeys',
            },
            float: {
                'fromhex',
            },
            int: {
                'from_bytes',
            },
            str: {
                'maketrans',
            },
        }
        self.allowed_instance_properties = {
            bytes: {
                'hex',
                'count',
                'decode',
                'endswith',
                'find',
                'index',
                'join',
                'partition',
                'replace',
                'rfind',
                'rindex',
                'rpartition',
                'startswith',
                'translate',
                'center',
                'ljust',
                'lstrip',
                'rjust',
                'rsplit',
                'rstrip',
                'split',
                'strip',
                'capitalize',
                'expandtabs',
                'isalnum',
                'isalpha',
                'isdigit',
                'islower',
                'isspace',
                'istitle',
                'isupper',
                'lower',
                'splitlines',
                'swapcase',
                'title',
                'upper',
                'zfill',
            },
            datetime.date: {
                'year',
                'month',
                'day',
                'replace',
                'timetuple',
                'toordinal',
                'weekday',
                'isoweekday',
                'isocalendar',
                'isoformat',
                'ctime',
                'strftime',
            },
            datetime.datetime: {
                'year',
                'month',
                'day'
                'hour',
                'minute',
                'second',
                'microsecond',
                'tzinfo',
                'fold',
                'date',
                'time',
                'timetz',
                'replace',
                'astimezone',
                'dst',
                'tzname',
                'timetuple',
                'utctimetuple',
                'toordinal',
                'timestamp',
                'weekday',
                'isoweekday',
                'isocalendar',
                'isoformat',
                'ctime',
                'strftime',
            },
            datetime.time: {
                'hour',
                'minute',
                'second',
                'microsecond',
                'tzinfo',
                'fold',
                'replace',
                'isoformat',
                'strftime',
                'utcoffset',
                'dst',
                'tzname',
            },
            datetime.timedelta: {
                'total_seconds',
            },
            datetime.timezone: {
                'utcoffset',
                'tzname',
                'dst',
                'fromutc',
            },
            datetime.tzinfo: {
                'utcoffset',
                'dst',
                'tzname',
                'fromutc',
            },
            dict: {
                'copy',
                'get',
                'items',
                'keys',
                'pop',
                'popitem',
                'setdefault',
                'update',
                'values',
            },
            float: {
                'as_integer_ratio',
                'is_integer',
                'hex',
            },
            int: {
                'bit_length',
                'to_bytes',
            },
            list: {
                'index',
                'count',
                'append',
                'clear',
                'copy',
                'extend',
                'insert',
                'pop',
                'remove',
                'reverse',
                'sort',
            },
            range: {
                'start',
                'stop',
                'step',
            },
            str: {
                'capitalize',
                'casefold',
                'center',
                'count',
                'encode',
                'endswith',
                'expandtabs',
                'find',
                'format',
                'format_map',
                'index',
                'isalnum',
                'isalpha',
                'isdecimal',
                'isdigit',
                'isidentifier',
                'islower',
                'isnumeric',
                'isprintable',
                'isspace',
                'istitle',
                'isupper',
                'join',
                'ljust',
                'lower',
                'lstrip',
                'partition',
                'replace',
                'rfind',
                'rindex',
                'rjust',
                'rpartition',
                'rsplit',
                'rstrip',
                'split',
                'splitlines',
                'swapcase',
                'startswith',
                'strip',
                'title',
                'translate',
                'upper',
                'zfill',
            },
            set: {
                'isdisjoint',
                'issubset',
                'issuperset',
                'union',
                'intersection',
                'difference',
                'symmetric_difference',
                'copy',
                'update',
                'intersection_update',
                'difference_update',
                'symmetric_difference_update',
                'add',
                'remove',
                'discard',
                'pop',
                'clear',
            },
            tuple: {
                'index',
                'count',
                'append',
                'clear',
                'copy',
                'extend',
                'insert',
                'pop',
                'remove',
                'reverse',
            },
        }
        self.global_symbol_table: Dict[str, Any] = {
            # builtin type
            'bool': bool,
            'bytes': bytes,
            'complex': complex,
            'dict': dict,
            'float': float,
            'frozenset': frozenset,
            'int': int,
            'list': list,
            'set': set,
            'str': str,
            'tuple': tuple,
            # builtin func
            'abs': abs,
            'all': all,
            'any': any,
            'ascii': ascii,
            'bin': bin,
            'chr': chr,
            'divmod': divmod,
            'enumerate': enumerate,
            'filter': filter,
            'hex': hex,
            'isinstance': isinstance,
            'issubclass': issubclass,
            'len': len,
            'map': map,
            'max': max,
            'min': min,
            'oct': oct,
            'ord': ord,
            'pow': pow,
            'range': range,
            'repr': repr,
            'reversed': reversed,
            'round': round,
            'sorted': sorted,
            'zip': zip,
            # additional type
            'Decimal': Decimal,
            # module level injection
            'datetime': datetime,
            'functools': functools,
            'html': html,
            'itertools': itertools,
            'json': ujson,
            'math': math,
            'operator': operator,
            'random': random,
            'statistics': statistics,
        }
        self.symbol_table: Dict[str, Any] = {}
        self.current_interrupt: Optional[
            Union[_ast.Break, _ast.Continue]
        ] = None

    def run(self, expr: str):
        h = ast.parse(expr, mode='exec')
        self.last_dump = ast.dump(h)
        return self._run(h)

    def _run(self, node):
        if node is None:
            return None

        return getattr(
            self,
            f'visit_{node.__class__.__name__.lower()}',
            self.no_impl,
        )(node)

    def assign(self, node, val):
        cls = node.__class__

        if cls == _ast.Name:
            self.symbol_table[node.id] = val
        elif cls in (_ast.Tuple, _ast.List):
            if len(val) == len(node.elts):
                for telem, tval in zip(node.elts, val):
                    self.assign(telem, tval)
            else:
                raise ValueError('too many values to unpack')
        elif cls == _ast.Subscript:
            sym = self._run(node.value)
            xslice = self._run(node.slice)
            if isinstance(node.slice, _ast.Index):
                sym[xslice] = val
            elif isinstance(node.slice, _ast.Slice):
                sym[slice(xslice.start, xslice.stop)] = val
            elif isinstance(node.slice, _ast.ExtSlice):
                sym[xslice] = val
        else:
            raise BadSyntax('This assign method is not allowed')

    def delete(self, node):
        cls = node.__class__

        if cls == _ast.Name:
            del self.symbol_table[node.id]
        elif cls == _ast.Tuple:
            for elt in node.elts:
                self.delete(elt)

    def no_impl(self, node):
        raise NotImplementedError

    def visit_annassign(self, node: _ast.AnnAssign):
        raise BadSyntax('You can not use annotation syntax')

    def visit_assert(self, node: _ast.Assert):
        raise BadSyntax('You can not use assertion syntax')

    def visit_assign(self, node: _ast.Assign):  # targets, value
        value = self._run(node.value)
        for tnode in node.targets:
            self.assign(tnode, value)
        return

    def visit_asyncfor(self, node: _ast.AsyncFor):
        raise BadSyntax('You can not use `async for` loop syntax')

    def visit_asyncfunctiondef(self, node: _ast.AsyncFunctionDef):
        raise BadSyntax('Defining new coroutine via def syntax is not allowed')

    def visit_asyncwith(self, node: _ast.AsyncWith):
        raise BadSyntax('You can not use `async with` syntax')

    def visit_attribute(self, node: _ast.Attribute):  # value, attr, ctx
        value = self._run(node.value)
        t = type(value)
        try:
            if value in self.allowed_modules:
                if node.attr in self.allowed_modules[value]:
                    return getattr(value, node.attr)
                raise BadSyntax(f'You can not access `{node.attr}` attribute')
            if value in self.allowed_class_properties:
                if node.attr in self.allowed_class_properties[value]:
                    return getattr(value, node.attr)
                raise BadSyntax(f'You can not access `{node.attr}` attribute')
        except TypeError:
            pass
        if t in self.allowed_instance_properties:
            if node.attr in self.allowed_instance_properties[t]:
                return getattr(value, node.attr)
            raise BadSyntax(f'You can not access `{node.attr}` attribute')
        raise BadSyntax(f'You can not access attributes of {t}')

    def visit_augassign(self, node: _ast.AugAssign):  # target, op, value
        value = self._run(node.value)
        target = node.target
        target_cls = target.__class__
        op_cls = node.op.__class__

        if target_cls == _ast.Name:
            self.symbol_table[target.id] = BINOP_TABLE[op_cls](
                self.symbol_table[target.id],
                value,
            )
        elif target_cls == _ast.Subscript:
            sym = self._run(target.value)
            xslice = self._run(target.slice)
            if isinstance(target.slice, _ast.Index):
                sym[xslice] = BINOP_TABLE[op_cls](
                    sym[xslice],
                    value,
                )
            else:
                raise BadSyntax('This assign method is not allowed')
        else:
            raise BadSyntax('This assign method is not allowed')
        return

    def visit_await(self, node: _ast.Await):
        raise BadSyntax('You can not await anything')

    def visit_binop(self, node: _ast.BinOp):  # left, op, right
        op = BINOP_TABLE.get(node.op.__class__)

        if op:
            return op(self._run(node.left), self._run(node.right))
        raise NotImplementedError

    def visit_boolop(self, node: _ast.BoolOp):  # left, op, right
        op = BOOLOP_TABLE.get(node.op.__class__)

        if op:
            return functools.reduce(op, map(self._run, node.values), True)
        raise NotImplementedError

    def visit_bytes(self, node: _ast.Bytes):  # s,
        return node.s

    def visit_break(self, node: _ast.Break):
        self.current_interrupt = node

    def visit_call(self, node: _ast.Call):  # func, args, keywords
        func = self._run(node.func)
        args = [self._run(x) for x in node.args]
        keywords = {x.arg: self._run(x.value) for x in node.keywords}
        return func(*args, **keywords)

    def visit_compare(self, node: _ast.Compare):  # left, ops, comparators
        lval = self._run(node.left)
        out = True
        for op, rnode in zip(node.ops, node.comparators):
            rval = self._run(rnode)
            cmpop = COMPARE_TABLE.get(op.__class__)
            if cmpop:
                out = cmpop(lval, rval)
                lval = rval
            else:
                raise NotImplementedError
        return out

    def visit_continue(self, node: _ast.Continue):
        self.current_interrupt = node

    def visit_classdef(self, node: _ast.ClassDef):
        raise BadSyntax('Defining new class via def syntax is not allowed')

    def visit_delete(self, node: _ast.Delete):  # targets
        for target in node.targets:
            target_cls = target.__class__
            if target_cls == _ast.Name:
                del self.symbol_table[target.id]
            elif target_cls == _ast.Subscript:
                sym = self._run(target.value)
                xslice = self._run(target.slice)
                if isinstance(target.slice, _ast.Index):
                    del sym[xslice]
                else:
                    raise BadSyntax('This delete method is not allowed')
            else:
                raise BadSyntax('This delete method is not allowed')
        return

    def visit_dict(self, node: _ast.Dict):  # keys, values
        return {
            self._run(k): self._run(v) for k, v in zip(node.keys, node.values)
        }

    def visit_dictcomp(self, node: _ast.DictComp):  # key, value, generators
        result: Dict[Any, Any] = {}
        current_gen = node.generators[0]
        if current_gen.__class__ == _ast.comprehension:
            for val in self._run(current_gen.iter):
                self.assign(current_gen.target, val)
                add = True
                for cond in current_gen.ifs:
                    add = add and self._run(cond)
                if add:
                    if len(node.generators) > 1:
                        r = self.visit_dictcomp(
                            _ast.DictComp(
                                key=node.key,
                                value=node.value,
                                generators=node.generators[1:],
                            )
                        )
                        result.update(r)
                    else:
                        key = self._run(node.key)
                        value = self._run(node.value)
                        result[key] = value
                self.delete(current_gen.target)
        return result

    def visit_ellipsis(self, node: _ast.Ellipsis):
        return Ellipsis

    def visit_expr(self, node: _ast.Expr):  # value,
        return self._run(node.value)

    def visit_extslice(self, node: _ast.ExtSlice):  # dims,
        return tuple(self._run(x) for x in node.dims)

    def visit_functiondef(self, node: _ast.FunctionDef):
        raise BadSyntax('Defining new function via def syntax is not allowed')

    def visit_for(self, node: _ast.For):  # target, iter, body, orelse
        for val in self._run(node.iter):
            self.assign(node.target, val)
            self.current_interrupt = None
            for tnode in node.body:
                self._run(tnode)
                if self.current_interrupt is not None:
                    break
            if isinstance(self.current_interrupt, _ast.Break):
                break
        else:
            for tnode in node.orelse:
                self._run(tnode)

        self.current_interrupt = None

    def visit_formattedvalue(self, node: _ast.FormattedValue):
        # value, conversion, format_spec
        value = self._run(node.value)
        format_spec = self._run(node.format_spec)
        if format_spec is None:
            format_spec = ''
        return format(value, format_spec)

    def visit_generatorexp(self, node: _ast.GeneratorExp):
        raise BadSyntax('Defining new generator expression is not allowed')

    def visit_global(self, node: _ast.Global):
        raise BadSyntax('You can not use `global` syntax')

    def visit_if(self, node: _ast.If):  # test, body, orelse
        stmts = node.body if self._run(node.test) else node.orelse
        for stmt in stmts:
            self._run(stmt)
        return

    def visit_ifexp(self, node: _ast.IfExp):  # test, body, orelse
        return self._run(node.body if self._run(node.test) else node.orelse)

    def visit_import(self, node: _ast.Import):
        raise BadSyntax('You can not import anything')

    def visit_importfrom(self, node: _ast.ImportFrom):
        raise BadSyntax('You can not import anything')

    def visit_index(self, node: _ast.Index):  # value,
        return self._run(node.value)

    def visit_joinedstr(self, node: _ast.JoinedStr):  # values,
        return ''.join(self._run(x) for x in node.values)

    def visit_lambda(self, node: _ast.Lambda):
        raise BadSyntax('Defining new function via lambda'
                        ' syntax is not allowed')

    def visit_list(self, node: _ast.List):  # elts, ctx
        return [self._run(x) for x in node.elts]

    def visit_listcomp(self, node: _ast.ListComp):  # elt, generators
        result: List[Any] = []
        current_gen = node.generators[0]
        if current_gen.__class__ == _ast.comprehension:
            for val in self._run(current_gen.iter):
                self.assign(current_gen.target, val)
                add = True
                for cond in current_gen.ifs:
                    add = add and self._run(cond)
                if add:
                    if len(node.generators) > 1:
                        r = self.visit_listcomp(
                            _ast.ListComp(
                                elt=node.elt,
                                generators=node.generators[1:],
                            )
                        )
                        result += r
                    else:
                        r = self._run(node.elt)
                        result.append(r)
                self.delete(current_gen.target)
        return result

    def visit_module(self, node: _ast.Module):  # body,
        last = None
        for body_node in node.body:
            last = self._run(body_node)
        return last

    def visit_name(self, node: _ast.Name):  # id, ctx
        ctx = node.ctx.__class__
        if ctx in (_ast.Param, _ast.Del):
            return node.id
        else:
            if node.id in self.symbol_table:
                return self.symbol_table[node.id]
            if node.id in self.global_symbol_table:
                return self.global_symbol_table[node.id]
            raise NameError()

    def visit_nameconstant(self, node: _ast.NameConstant):  # value,
        return node.value

    def visit_nonlocal(self, node: _ast.Nonlocal):
        raise BadSyntax('You can not use `nonlocal` syntax')

    def visit_num(self, node: _ast.Num):  # n,
        if self.decimal_mode:
            return Decimal(str(node.n))
        return node.n

    def visit_pass(self, node: _ast.Pass):
        return

    def visit_raise(self, node: _ast.Raise):
        raise BadSyntax('You can not use `raise` syntax')

    def visit_return(self, node: _ast.Return):
        raise BadSyntax('You can not use `return` syntax')

    def visit_set(self, node: _ast.Set):  # elts,
        return {self._run(x) for x in node.elts}

    def visit_setcomp(self, node: _ast.SetComp):  # elt, generators
        result: Set[Any] = set()
        current_gen = node.generators[0]
        if current_gen.__class__ == _ast.comprehension:
            for val in self._run(current_gen.iter):
                self.assign(current_gen.target, val)
                add = True
                for cond in current_gen.ifs:
                    add = add and self._run(cond)
                if add:
                    if len(node.generators) > 1:
                        r = self.visit_setcomp(
                            _ast.SetComp(
                                elt=node.elt,
                                generators=node.generators[1:],
                            )
                        )
                        result |= r
                    else:
                        r = self._run(node.elt)
                        result.add(r)
                self.delete(current_gen.target)
        return result

    def visit_slice(self, node: _ast.Slice):  # lower, upper, step
        return slice(
            self._run(node.lower),
            self._run(node.upper),
            self._run(node.step),
        )

    def visit_str(self, node: _ast.Str):  # s,
        return node.s

    def visit_subscript(self, node: _ast.Subscript):  # value, slice, ctx
        return self._run(node.value)[self._run(node.slice)]

    def visit_try(self, node: _ast.Try):
        raise BadSyntax('You can not use `try` syntax')

    def visit_tuple(self, node: _ast.Tuple):  # elts, ctx
        return tuple(self._run(x) for x in node.elts)

    def visit_unaryop(self, node: _ast.UnaryOp):  # op, operand
        op = UNARYOP_TABLE.get(node.op.__class__)
        if op:
            return op(self._run(node.operand))
        raise NotImplementedError

    def visit_while(self, node: _ast.While):  # test, body, orelse
        while self._run(node.test):
            self.current_interrupt = None
            for tnode in node.body:
                self._run(tnode)
                if self.current_interrupt is not None:
                    break
            if isinstance(self.current_interrupt, _ast.Break):
                break
        else:
            for tnode in node.orelse:
                self._run(tnode)

        self.current_interrupt = None

    def visit_with(self, node: _ast.With):
        raise BadSyntax('You can not use `with` syntax')

    def visit_yield(self, node: _ast.Yield):
        raise BadSyntax('You can not use `yield` syntax')

    def visit_yieldfrom(self, node: _ast.YieldFrom):
        raise BadSyntax('You can not use `yield from` syntax')


def calculate(
    expr: str,
    *,
    decimal_mode: bool = True
):
    e = Evaluator(decimal_mode=decimal_mode)
    result = e.run(expr)

    return result, e.symbol_table
