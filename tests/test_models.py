#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
test_models
###########

Tests for `steamwatch` module.
'''
import pytest

from steamwatch import models
from steamwatch.models import _Model
from steamwatch.models import Column
from steamwatch.models import NotFoundError
from steamwatch.models import Select
from steamwatch.models import Update
from steamwatch.models import Insert
from steamwatch.models import Delete


@pytest.fixture(scope='module')
def db():
    db = models.Database(':memory:')
    cur = db.conn.cursor()
    cur.executemany(
        'insert into games (appid, enabled, name) values (?, ?, ?)',
        (
            ('111', 1, 'Game One'),
            ('222', 1, 'Game Two'),
            ('333', 0, 'Game Three'),
        )
    )

    cur.executemany(
        'insert into measures (gameid, price, baseprice, discount) values (?, ?, ?, ?)',
        (
            (1, 123, None, None),
            (1, 456, None, None),
            (1, 789, None, None),
            (2, 11, None, None),
        )
    )

    return db


@pytest.fixture
def emptydb():
    db = models.Database(':memory:')
    return db


def test_db_insert(db):
    model = models.Measure(
        gameid=123,
        price=699,
        baseprice=1999,
        discount=66,
        metacritic=77,
        currency='EUR',
    )
    db.store(model)
    assert model.id > 0


def test_db_select(db):
    results = db.select(models.Measure, gameid=1)
    assert len(results) == 3
    assert type(results[0]) == models.Measure


def test_game_store_load(emptydb):
    game = models.Game(
        appid='123',
        name='Game One'
    )
    emptydb.store(game)
    reloaded = emptydb.select_one(models.Game, id=game.id)
    assert game.id is not None
    assert reloaded.id == game.id
    assert reloaded.appid == game.appid
    assert reloaded.name == game.name


def test_game_select_enabled(db):
    # relies on fixture data with three games
    # and game with appid 333 being disabled
    games = db.select(models.Game, enabled=True)
    assert len(games) == 2
    assert '333' not in [game.appid for game in games]


def test_measure_store_load(emptydb):
    pass


def test_not_found(db):
    with pytest.raises(models.NotFoundError):
        db.select_one(models.Game, appid='does-not-exist')


def test_update_non_existing(db):
    non_existing = models.Game(
        appid='999',
        enabled=True,
        name='Foo'
    )
    non_existing.id = 999
    with pytest.raises(models.NotFoundError):
        db.store(non_existing)


def test_convert_to_boolean():
    assert models._int_to_boolean(0) == False
    assert models._int_to_boolean(1) == True
    assert models._int_to_boolean(None) == None
    with pytest.raises(ValueError):
        models._int_to_boolean(2)


def test_convert_from_boolean():
    assert models._boolean_to_int(True) == 1
    assert models._boolean_to_int(False) == 0
    assert models._boolean_to_int(None) == None
    assert models._boolean_to_int('true-ish') == 1


# SQL Builder -----------------------------------------------------------------

class Foo(_Model):

    __table__ = 'tbl'
    __columns__ = [
        Column('id', datatype='integer', primary=True),
        Column('foo'),
        Column('bar'),
        Column('baz'),
    ]

    def __init__(self, id=None, foo=None, bar=None, baz=None):
        self.id = id
        self.foo = foo
        self.bar = bar
        self.baz = baz


def test_select():
    db = None
    model = Foo
    select = Select(db, model)
    assert select.sql == 'SELECT id,foo,bar,baz FROM tbl'
    assert not select.params

    select = Select(db, model)
    select.where('foo').equals('a')
    assert select.sql == 'SELECT id,foo,bar,baz FROM tbl WHERE foo=?'
    assert select.params == ['a']

    select = Select(db, model)
    select.where('bar').equals('b').or_is('bar').equals('bb')
    assert select.sql == 'SELECT id,foo,bar,baz FROM tbl WHERE bar=? OR bar=?'
    assert select.params == ['b', 'bb']

    select = Select(db, model).order_by('foo')
    assert select.sql == 'SELECT id,foo,bar,baz FROM tbl ORDER BY foo ASC'
    assert not select.params

    select = Select(db, model).order_by('foo').order_by('bar', desc=True)
    assert select.sql == 'SELECT id,foo,bar,baz FROM tbl ORDER BY foo ASC, bar DESC'
    assert not select.params

    statement = Select(db, model).limit(1)
    assert statement.sql == 'SELECT id,foo,bar,baz FROM tbl LIMIT 1'
    assert not statement.params


def test_insert():
    db = None
    instance = Foo(foo='a', bar='b', baz='c')
    statement = Insert(db, instance)
    assert statement.sql == 'INSERT INTO tbl VALUES (?,?,?,?)'
    assert statement.params == [None, 'a', 'b', 'c']


def test_update():
    db = None
    instance = Foo(foo='a', bar='b', baz='c')
    instance.id = 1
    statement = Update(db, instance)
    assert statement.sql == 'UPDATE tbl SET id=?,foo=?,bar=?,baz=? WHERE id=?'
    assert statement.params == [1, 'a', 'b', 'c', 1]

def test_model_select(db):
    db._create_table(Foo)
    assert not Foo.select(db).many()  # table is empty

    with pytest.raises(NotFoundError):
        Foo.select(db).one()

    instance = Foo(foo='a', bar='b', baz='c')
    instance.save(db)
    assert instance.id is not None

    instances = Foo.select(db).where('foo').equals('a').many()
    assert len(instances) == 1

    instance = Foo.select(db).where('foo').equals('a').one()
    assert isinstance(instance, Foo)
    id = instance.id
    instance.foo='aa'
    instance.save(db)

    reloaded = Foo.get(db, id)
    assert reloaded.foo == 'aa'

    with pytest.raises(NotFoundError):
        Foo.select(db).where('foo').equals('a').one()



if __name__ == '__main__':
    pytest.main(__file__)
