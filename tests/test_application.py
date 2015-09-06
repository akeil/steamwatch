#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_application
----------------------------------

Tests for `application` module.
"""
import pytest

from steamwatch import application
from steamwatch import storeapi


@pytest.fixture(scope='session')
def app():
    app = application.Application(':memory:')

    # sample data
    cur = app.db.conn.cursor()
    cur.executemany(
        'insert into games (appid, enabled, name) values (?, ?, ?)',
        (
            ('111', 1, 'Game One'),
            ('222', 1, 'Game Two'),
            ('333', 0, 'Game Three'),
        )
    )

    return app


@pytest.fixture
def mockapi(monkeypatch):

    def mock_appdetails(appid):
        return {
            appid: {
                'data': {
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
                },
            },
        }

    monkeypatch.setattr(storeapi, 'appdetails', mock_appdetails)


def test_add(app, mockapi):
    game = app.add('123')
    assert game is not None
    assert game.id > 0
    assert game.name == 'Name of the Game'
    assert game.appid == '123'


def test_enable(app):
    game = app.get('111')
    assert game is not None  # precondition
    assert game.enabled  # precondition

    app.disable('111')
    game = app.get('111')
    assert not game.enabled

    app.enable('111')
    game = app.get('111')
    assert game.enabled


def test_update_all(app, mockapi):
    pass


def test_report():
    pass



if __name__ == '__main__':
    pytest.main(__file__)
