#-*- coding: utf-8 -*-
'''
Tests for models
'''
import datetime

from peewee import IntegrityError

from steamwatch.model import init
from steamwatch.model import App
from steamwatch.model import Package
from steamwatch.model import AppPackage
from steamwatch.model import Snapshot

import pytest


def setup_module():
    init(':memory:')


def test_app_create():
    app = App.create(
        steamid='1',
        kind='game',
        enabled=False,
        name='The Name',
        threshold=1000
    )
    assert app.id is not None
    assert app.steamid == '1'
    assert app.kind == 'game'
    assert not app.enabled
    assert app.name == 'The Name'
    assert app.threshold == 1000


def test_app_from_apidata():
    apidata = {
        'type': 'game',
        'name': 'The Name',
    }
    app = App.from_apidata('2', apidata, threshold=1000)
    assert app.id is not None
    assert app.steamid == '2'
    assert app.kind == 'game'
    assert app.enabled
    assert app.name == 'The Name'
    assert app.threshold == 1000


def test_app_integrity():
    App.create(steamid='3', kind='game')
    with pytest.raises(IntegrityError):
        App.create(steamid='3', kind='game')

    with pytest.raises(IntegrityError):
        App.create(steamid='4')  # missing 'kind'


# Package ---------------------------------------------------------------------


def test_package():
    pkg = Package.create(
        steamid='01',
        name='My Package'
    )
    assert pkg.id is not None
    assert pkg.steamid == '01'
    assert pkg.name == 'My Package'


def test_package_from_apidata():
    d = {
        'name': 'My Package',
    }
    pkg = Package.from_apidata('02', d)

    assert pkg.id is not None
    assert pkg.steamid == '02'
    assert pkg.name == 'My Package'


def test_package_integrity():
    Package.create(steamid='03', kind='game')
    with pytest.raises(IntegrityError):
        Package.create(steamid='03', kind='game')


def test_package_record_snapshot():
    package = Package.create(steamid='04', kind='game')
    apidata0 = {
        'price': {
            'currency': 'EUR',
            'final': 1500,
        },
        'platforms': {
            'linux': True,
        },
        'release_date': {
            'date': '02 September, 2015',
            'coming_soon': True
        }
    }
    apidata1 = {
        'price': {
            'currency': 'EUR',
            'final': 1500,
        },
        'platforms': {
            'linux': False,
        },
        'release_date': {
            'date': '02 September, 2015',
            'coming_soon': True
        }
    }

    assert package.snapshots.count() == 0  # precondition
    package.record_snapshot(apidata0)
    package.record_snapshot(apidata0)  # twice
    assert package.snapshots.count() == 1
    package.record_snapshot(apidata1)
    assert package.snapshots.count() == 2


# AppPackage ------------------------------------------------------------------


def test_app_package_create():
    app = App.create(steamid='5', kind='game')
    pkg = Package.create(steamid='5')
    app_pkg = AppPackage.create(app=app, package=pkg)
    assert app_pkg.app.id == app.id
    assert app_pkg.package.id == pkg.id


def test_app_package_link():
    app = App.create(steamid='6', kind='game')
    pkg0 = Package.create(steamid='6')
    pkg1 = Package.create(steamid='7')

    pkg0.link(app)
    pkg1.link(app)

    assert pkg0 in app.packages
    assert pkg1 in app.packages
    assert app in pkg0.apps
    assert app in pkg1.apps


# Snapshot --------------------------------------------------------------------


def test_snapshot_create():
    pkg = Package.create(steamid='8', kind='game')
    apidata = {
        'price': {
            'currency': 'EUR',
            'final': 1500,
        },
        'platforms': {
            'linux': True,
        },
        'release_date': {
            'date': '02 September, 2015',
            'coming_soon': True
        }
    }
    ss = Snapshot.from_apidata(pkg, apidata)
    assert ss.price == 1500
    assert ss.currency == 'EUR'
    assert ss.supports_linux
    assert ss.release_date == datetime.date(2015,9,2)
    assert ss.coming_soon
    assert ss.timestamp is not None
    assert ss.id is None


def test_snapshot_diff():
    pkg = Package.create(steamid='9', kind='game')
    apidata0 = {
        'price': {
            'currency': 'EUR',
            'final': 1500,
        },
        'platforms': {
            'linux': True,
        },
        'release_date': {
            'date': '02 September, 2015',
            'coming_soon': True
        }
    }
    ss0 = Snapshot.from_apidata(pkg, apidata0)

    apidata1 = {
        'price': {
            'currency': 'EUR',
            'final': 1500,
        },
        'platforms': {
            'linux': False,
        },
        'release_date': {
            'date': '02 September, 2015',
            'coming_soon': True
        }
    }
    ss1 = Snapshot.from_apidata(pkg, apidata1)
    assert ss0.is_different(ss1)

    ss2 = Snapshot.from_apidata(pkg, apidata1)
    assert not ss1.is_different(ss1)
