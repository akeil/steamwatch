#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_application
----------------------------------

Tests for `application` module.
"""
import argparse
import pytest

from steamwatch import application
from steamwatch import storeapi
from steamwatch import model
from steamwatch.model import App


@pytest.fixture
def app():
    options = argparse.Namespace()
    options.db_path = ':memory:'
    app = application.Application(options)
    # db is initialized, insert sample data
    cur = model.db.get_cursor()
    cur.executemany(
        'insert into app (steamid, kind, enabled, name) values (?, ?, ?, ?)',
        (
            ('111', 'game', 1, 'Game One'),
            ('222', 'game', 1, 'Game Two'),
            ('333', 'game', 0, 'Game Three'),
        )
    )

    return app


@pytest.fixture
def mockapi(monkeypatch):

    def mock_appdetails(appid):
        return {
            'type': 'game',
            'steam_appid': appid,
            'metacritic': {
                'score': 70
            },
            'name': 'Name of the Game',
            'price_overview': {
                'currency': 'EUR',
                'discount_percent': 66,
                'final': 679,
                'initial': 1999,
            },
        'success': True,
        }

    monkeypatch.setattr(storeapi, 'appdetails', mock_appdetails)


def test_watch(app, mockapi):
    game = app.watch('123')
    assert game is not None
    assert game.id > 0
    assert game.enabled
    assert game.name == 'Name of the Game'
    assert game.steamid == '123'

    # watching it again should be possible (i.e. no errors)
    game = app.watch('123')


def test_unwatch(app, mockapi):
    app.watch('123')
    app.unwatch('123', delete=False)
    game = App.by_steamid('123')
    assert not game.enabled

    app.unwatch('123', delete=True)
    assert App.by_steamid('123') is None


def test_unwatch_non_existing(app):
    app.unwatch('does-not-exist')


def test_watch_enable(app, mockapi):
    app.watch('123')
    game = App.by_steamid('123')
    assert game.enabled  # precondition

    app.unwatch('123', delete=False)
    game = App.by_steamid('123')
    assert not game.enabled

    app.watch('123')
    game = App.by_steamid('123')
    assert game.enabled  # precondition


if __name__ == '__main__':
    pytest.main(__file__)
