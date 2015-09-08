#-*- coding: utf-8 -*-
'''
Model classes for *steamwatch*.
This mirrors the Steam Store data model
And adds *Snapshots* for collected data::

    [App] <-- [AppPackage] --> [Package]
                                   ^
                                   |
                               [Snapshot]

The main business obect is the *App*, which is either a *Game*
or a piece downloadable content (DLC).

However, sales relevant information if available for *Packages*, which
are aggregates of one or more *Apps*.
Each *App* will have at least one default package with the app as its single
member.

.. note::
    Not sure whther this is guaranteed by the steam API.
    If not, we can create the default package ourselves.

'''
import logging
from datetime import datetime

from peewee import Model
from peewee import SqliteDatabase
from peewee import SQL
#from peewee import PrimaryKeyField
from peewee import CompositeKey
from peewee import ForeignKeyField
from peewee import CharField
#from peewee import TextField
from peewee import DateField
from peewee import DateTimeField
from peewee import BooleanField
from peewee import IntegerField
#from peewee import FloatField


log = logging.getLogger(__name__)


# needs to be initialized externally, e.g.
# model.db.init('sqlite://path/to/my/db')
# see
# https://peewee.readthedocs.org/en/latest/peewee/database.html#run-time-database-configuration
db = SqliteDatabase(None)


def init(db_path):
    db.init(db_path)
    db.connect()
    db.create_tables([App, Package, AppPackage, Snapshot], safe=True)


class BaseModel(Model):

    class Meta:

        database = db


class App(BaseModel):
    '''A game or DLC on the steam store.'''

    steamid = CharField(unique=True, index=True)
    kind = CharField()
    enabled = BooleanField(default=True, index=True)
    name = CharField(null=True)
    threshold = IntegerField(null=True)

    def link(self, package):
        AppPackage.create(app=self, package=package)

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    @property
    def packages(self):
        return [ap.package for ap in self.app_packages]

    @classmethod
    def by_steamid(cls, steamid):
        '''Find an App by its ``steamid``'''
        return cls.select().where(cls.steamid==steamid).limit(1).first()

    @classmethod
    def from_apidata(cls, steamid, d, **extra):
        return cls.create(
            steamid=steamid,
            kind=d['type'],
            enabled=extra.get('enabled', True),
            name=d.get('name'),
            threshold=extra.get('threshold'),
        )

    def __repr__(self):
        return '<App id={s.id!r} steamid={s.steamid!r}>'.format(s=self)


class Package(BaseModel):

    steamid = CharField(unique=True, index=True)
    name = CharField(null=True)

    def record_snapshot(self, data):
        '''Record a Snapshot from the given api-data *only if* it is different
        from the previously recorded snapshot.

        Returns the Snapshot instance if one was created, else None.
        '''
        ss = Snapshot.from_apidata(self, data)
        if ss.is_different():  # to previous
            ss.save()
            return ss

    def link(self, app):
        AppPackage.create(app=app, package=self)

    @property
    def apps(self):
        return [ap.app for ap in self.app_packages]

    @classmethod
    def by_steamid(cls, steamid):
        '''Find a Package by its ``steamid``'''
        return cls.select().where(cls.steamid==steamid).limit(1).first()

    @classmethod
    def from_apidata(cls, steamid, d):
        return cls.create(
            steamid=steamid,
            name=d.get('name')
        )

    def __repr__(self):
        return '<Package id={s.id!r} steamid={s.steamid!r}>'.format(s=self)


class AppPackage(BaseModel):

    app = ForeignKeyField(App, related_name='app_packages')
    package = ForeignKeyField(Package, related_name='app_packages')

    class Meta:

        # see
        # https://peewee.readthedocs.org/en/latest/peewee/models.html#non-integer-primary-keys-composite-keys-and-other-tricks
        primary_key = CompositeKey('app', 'package')

    def __repr__(self):
        return '<AppPackage app={s.app!r} package={s.package!r}>'.format(s=self)


class Snapshot(BaseModel):

    package = ForeignKeyField(Package, related_name='snapshots')
    timestamp = DateTimeField(index=True)
    currency = CharField(null=True)
    price = IntegerField(null=True)
    release_date = DateField(null=True)
    coming_soon = BooleanField(null=True)
    supports_linux = BooleanField()

    @classmethod
    def from_apidata(self, pkg, data):
        '''Create a Snapshot instance with package details from the storeapi.

        The Snapshot is not saved to the database.
        '''
        price = data.get('price', {})
        release = data.get('release_date', {})
        return Snapshot(
            package = pkg,
            timestamp=datetime.utcnow(),
            currency=price.get('currency'),
            price=price.get('final'),
            release_date=_parse_date(release.get('date', '')),
            coming_soon=release.get('coming_soon'),
            supports_linux=data.get('platforms', {}).get('linux', False)
        )

    @property
    def previous(self):
        '''Get the Snapshot that was recorded before this one.'''
        select = Snapshot.select().where(Snapshot.package==self.package)
        select.order_by(Snapshot.timestamp.desc())
        if self.id:
            # TODO only works if this is the most recent snapshot
            select.offset(1).limit(1)
        else:
            select.limit(1)
        return select.first()

    def diff(self, other=None):
        '''Return the *diff* between this Snapshot and another snapshot.

        The following properties are taken into account:
        - currency
        - price
        - release_date
        - coming_soon
        - supports_linux

        The "other" snapshot can be passed in as an argument.
        If *None* is passed, the diff will be made against the previous
        instance. If there is no previous instance, all properties are
        compared to None.

        Return a list of tuples with entries for each changed field::

            [
                (<fieldname>, <self-value>, <other-value>),
                (...)
            ]
        '''
        if not other:
            other = self.previous

        diffs = []
        fields = ('currency', 'price', 'release_date',
            'coming_soon', 'supports_linux')
        for field in fields:
            mine = getattr(self, field)
            thine = getattr(other, field, None)  # in case `other` is None
            if mine != thine:
                diffs.append((field, mine, thine))

        return diffs

    def is_different(self, other=None):
        return bool(self.diff(other=other))

    def __repr__(self):
        return '<Snapshot id={s.id!r} package={s.package!r}>'.format(s=self)


# https://docs.python.org/3.3/library/datetime.html#strftime-and-strptime-behavior
# expected: "30 May, 2014"
DATEFORMAT = '%d %B, %Y'


def _parse_date(datestr):
    try:
        return datetime.strptime(datestr, DATEFORMAT).date()
    except ValueError:
        pass
