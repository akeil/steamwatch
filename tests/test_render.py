#-*- coding: utf-8 -*-
'''
[Module Documentation here]
'''
import pytest


# Style ----------------------------------------------------------------------

from steamwatch.render import red
from steamwatch.render import bold


def test_simple():
    styled = str(red('text'))
    assert styled == '\033[31mtext\033[0m'


def test_nested():
    styled = str(red(bold('text')))
    assert (styled == '\033[31;1mtext\033[0m'
        or styled == '\033[1;31mtext\033[0m')

def test_disable():
    disabled = red('text', enabled=False)
    assert str(disabled) == 'text'  # no control chars

    # passed on to new instances
    assert str(disabled.copy_style('abc')) == 'abc'


def test_left_concat():
    styled = red('text')
    combined = 'normal ' + styled
    assert combined == 'normal \033[31mtext\033[0m'


def test_styled_concat():
    styled = red('text')
    also_styled = bold('text')
    s = styled + also_styled
    assert s == '\033[31mtext\033[0m' + '\033[1mtext\033[0m'


def test_right_concat():
    styled = red('text')
    combined = styled + ' normal'
    assert combined == '\033[31mtext\033[0m normal'


def test_plus_equals():
    styled = red('text')
    styled += ' normal'
    assert str(styled) == '\033[31mtext\033[0m normal'


def test_multiply():
    styled = red('text')
    assert str(3 * styled) == '\033[31m' + 'texttexttext' + '\033[0m'

    styled *= 3
    assert str(styled) == '\033[31m' + 'texttexttext' + '\033[0m'


def test_multiply_nested():
    nested = red(bold('text'))
    assert (str(3 * nested) == '\033[31;1mtexttexttext\033[0m'
        or str(3 * nested) == '\033[1;31mtexttexttext\033[0m')


def test_length():
    styled = red('text')
    assert len(styled) == 4

    empty = red('')
    assert len(empty) == 0

    with pytest.raises(TypeError):
        len(red(None))


def test_comparsion():
    smaller = red('a')
    greater = red('b')
    assert smaller < greater
    assert smaller <= greater
    assert smaller != greater
    assert not smaller > greater
    assert not smaller >= greater
    assert not smaller == greater

    # different instances should be treated as equal
    equal = red('x')
    twin = red('x')
    assert not equal < twin
    assert not equal > twin
    assert not equal != twin
    assert equal == twin
    assert equal >= twin
    assert equal <= twin

def test_equality_ignores_style():
    # for now, test for equality ignores different styles
    assert red('x') == bold('x')


def test_bool():
    content = red('text')
    assert bool(content) == True

    empty = red('')
    assert bool(empty) == False

    nothing = red(None)
    assert bool(nothing) == False


def test_slice():
    styled = red('abcd')
    assert str(styled[0]) == '\033[31m' + 'a' + '\033[0m'
    assert str(styled[1]) == '\033[31m' + 'b' + '\033[0m'

    assert str(styled[-1]) == '\033[31m' + 'd' + '\033[0m'
    assert str(styled[-2]) == '\033[31m' + 'c' + '\033[0m'

    assert str(styled[:2]) == '\033[31m' + 'ab' + '\033[0m'
    assert str(styled[2:]) == '\033[31m' + 'cd' + '\033[0m'
    assert str(styled[1:3]) == '\033[31m' + 'bc' + '\033[0m'


def test_slice_nested():
    styled = red(bold('abcd'))
    assert (str(styled[0]) == '\033[31;1m' + 'a' + '\033[0m'
        or str(styled[0]) == '\033[1;31m' + 'a' + '\033[0m')


def test_iter():
    unstyled = 'abcd'
    styled = red(unstyled)
    for styled_char, unstyled_char in zip(styled, unstyled):
        assert str(styled_char) == '\033[31m' + unstyled_char + '\033[0m'


def test_iter_nested():
    unstyled = 'abcd'
    styled = red(bold(unstyled))
    for styled_char, unstyled_char in zip(styled, unstyled):
        assert (str(styled_char) == '\033[31;1m' + unstyled_char + '\033[0m'
            or str(styled_char) == '\033[1;31m' + unstyled_char + '\033[0m')


def test_str_functions():
    assert red('text').upper() == red('TEXT')
    assert red('TEXT').lower() == red('text')

    # with args
    assert red('text').replace('t', '_') == red('_ex_')

    # format
    assert red('{s}').format(s='text') == red('text')

    # functions that do not return a new str
    assert red('text').isupper() == False
    assert red('TEXT').isupper() == True
    assert red('text').count('t') == 2


def test_split():
    parts = red('a b').split()
    assert str(parts[0]) == '\033[31m' + 'a' + '\033[0m'
    assert str(parts[1]) == '\033[31m' + 'b' + '\033[0m'


def test_split_nested():
    parts = bold(red('a b')).split()
    assert str(parts[0]) == '\033[31;1m' + 'a' + '\033[0m'
    assert str(parts[1]) == '\033[31;1m' + 'b' + '\033[0m'


def test_join():
    styled = red('-')
    joined = styled.join(['a', 'b'])
    assert joined == 'a' + '\033[31m' + '-' + '\033[0m' + 'b'
