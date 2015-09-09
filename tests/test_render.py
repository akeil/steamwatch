#-*- coding: utf-8 -*-
'''
[Module Documentation here]
'''
import pytest


# Style ----------------------------------------------------------------------

from steamwatch.render import Red
from steamwatch.render import Bold


def test_simple():
    styled = str(Red('text'))
    assert styled == '\033[33mtext\033[0m'


def test_nested():
    styled = str(Red(Bold('text')))
    assert (styled == '\033[33;1mtext\033[0m'
        or styled == '\033[1;33mtext\033[0m')


def test_left_concat():
    styled = Red('text')
    combined = 'normal ' + styled
    assert combined == 'normal \033[33mtext\033[0m'


def test_styled_concat():
    styled = Red('text')
    also_styled = Bold('text')
    s = styled + also_styled
    assert s == '\033[33mtext\033[0m' + '\033[1mtext\033[0m'


def test_right_concat():
    styled = Red('text')
    combined = styled + ' normal'
    assert combined == '\033[33mtext\033[0m normal'


def test_plus_equals():
    styled = Red('text')
    styled += ' normal'
    assert str(styled) == '\033[33mtext\033[0m normal'


def test_multiply():
    styled = Red('text')
    assert str(3 * styled) == '\033[33m' + 'texttexttext' + '\033[0m'

    styled *= 3
    assert str(styled) == '\033[33m' + 'texttexttext' + '\033[0m'


def test_multiply_nested():
    nested = Red(Bold('text'))
    assert (str(3 * nested) == '\033[33;1mtexttexttext\033[0m'
        or str(3 * nested) == '\033[1;33mtexttexttext\033[0m')


def test_length():
    styled = Red('text')
    assert len(styled) == 4

    empty = Red('')
    assert len(empty) == 0

    with pytest.raises(TypeError):
        len(Red(None))


def test_comparsion():
    smaller = Red('a')
    greater = Red('b')
    assert smaller < greater
    assert smaller <= greater
    assert smaller != greater
    assert not smaller > greater
    assert not smaller >= greater
    assert not smaller == greater

    # different instances should be treated as equal
    equal = Red('x')
    twin = Red('x')
    assert not equal < twin
    assert not equal > twin
    assert not equal != twin
    assert equal == twin
    assert equal >= twin
    assert equal <= twin

def test_equality_ignores_style():
    # for now, test for equality ignores different styles
    assert Red('x') == Bold('x')


def test_bool():
    content = Red('text')
    assert bool(content) == True

    empty = Red('')
    assert bool(empty) == False

    nothing = Red(None)
    assert bool(nothing) == False


def test_slice():
    styled = Red('abcd')
    assert str(styled[0]) == '\033[33m' + 'a' + '\033[0m'
    assert str(styled[1]) == '\033[33m' + 'b' + '\033[0m'

    assert str(styled[-1]) == '\033[33m' + 'd' + '\033[0m'
    assert str(styled[-2]) == '\033[33m' + 'c' + '\033[0m'

    assert str(styled[:2]) == '\033[33m' + 'ab' + '\033[0m'
    assert str(styled[2:]) == '\033[33m' + 'cd' + '\033[0m'
    assert str(styled[1:3]) == '\033[33m' + 'bc' + '\033[0m'


def test_slice_nested():
    styled = Red(Bold('abcd'))
    assert (str(styled[0]) == '\033[33;1m' + 'a' + '\033[0m'
        or str(styled[0]) == '\033[1;33m' + 'a' + '\033[0m')


def test_iter():
    unstyled = 'abcd'
    styled = Red(unstyled)
    for styled_char, unstyled_char in zip(styled, unstyled):
        assert str(styled_char) == '\033[33m' + unstyled_char + '\033[0m'


def test_iter_nested():
    unstyled = 'abcd'
    styled = Red(Bold(unstyled))
    for styled_char, unstyled_char in zip(styled, unstyled):
        assert (str(styled_char) == '\033[33;1m' + unstyled_char + '\033[0m'
            or str(styled_char) == '\033[1;33m' + unstyled_char + '\033[0m')


def test_str_functions():
    assert Red('text').upper() == Red('TEXT')
    assert Red('TEXT').lower() == Red('text')

    # with args
    assert Red('text').replace('t', '_') == Red('_ex_')

    # format
    assert Red('{s}').format(s='text') == Red('text')

    # functions that do not return a new str
    assert Red('text').isupper() == False
    assert Red('TEXT').isupper() == True
    assert Red('text').count('t') == 2


def test_split():
    parts = Red('a b').split()
    assert str(parts[0]) == '\033[33m' + 'a' + '\033[0m'
    assert str(parts[1]) == '\033[33m' + 'b' + '\033[0m'


def test_split_nested():
    parts = Bold(Red('a b')).split()
    assert str(parts[0]) == '\033[33;1m' + 'a' + '\033[0m'
    assert str(parts[1]) == '\033[33;1m' + 'b' + '\033[0m'


def test_join():
    styled = Red('-')
    joined = styled.join(['a', 'b'])
    assert joined == 'a' + '\033[33m' + '-' + '\033[0m' + 'b'
