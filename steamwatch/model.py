#-*- coding: utf-8 -*-
# pylint: disable=logging-format-interpolation
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
    Not sure whether this is guaranteed by the steam API.
    If not, we can create the default package ourselves.

'''
import logging
from datetime import datetime

from peewee import Model
from peewee import SqliteDatabase
from peewee import CompositeKey
from peewee import ForeignKeyField
from peewee import CharField
from peewee import DateField
from peewee import DateTimeField
from peewee import BooleanField
from peewee import IntegerField


LOG = logging.getLogger(__name__)


# needs to be initialized externally, e.g.
# model.db.init('sqlite://path/to/my/db')
# see
# https://peewee.readthedocs.org/en/latest/peewee/database.html#run-time-database-configuration
_db = SqliteDatabase(None)


def init(db_path):
    '''Initialize the SQLite DB at the given ``db_path``.

    This is normally called from the
    :class:`steamwatch.application.Application`
    on startup.

    The DB file and tables inside the datebase will be created
    if they do not exist.
    '''
    _db.init(db_path)
    _db.connect()
    _db.create_tables([App, Package, AppPackage, Snapshot], safe=True)


class BaseModel(Model):
    '''Base class for all models, holds the reference to the databse.'''

    class Meta:

        database = _db  # global


class App(BaseModel):
    '''A game or DLC on the steam store.

    :var str steamid:
        The ``appid`` on the steam store.
    :var str kind:
        Whther this is a game, DLC or somethng else.
    :var bool enabled:
        Whether *watch* is enabled for this *App*.
        Disabled Apps will not be updated e.g. in
        :meth:`steamwatch.application.Application.fetch`.
    :var str name:
        The display name for this *App*.
    :var int threshold:
        Price threshold for triggering ???
        **NOT IMPLEMENTED**
    '''

    steamid = CharField(unique=True, index=True)
    kind = CharField()
    enabled = BooleanField(default=True, index=True)
    name = CharField(null=True)
    threshold = IntegerField(null=True)

    def link(self, package):
        '''Link this App to the given :class:`Package`.'''
        # TODO raise error if already linked?
        AppPackage.create(app=self, package=package)

    def unlink(self, pkg):
        '''Unlink this App from the given :class:`Package`.'''
        LOG.debug('Unlink {p!r} from {s!r}.'.format(p=pkg, s=self))
        link = self.app_packages.where(AppPackage.package == pkg).first()
        # TODO: raise error if not linked?
        link.delete_instance()

    def enable(self):
        '''Enable this App. Only enabled Apps will be updated.'''
        self.enabled = True

    def disable(self):
        '''Disable this App. No snapshots will be created for disabled apps.'''
        self.enabled = False

    @property
    def packages(self):
        '''A list of :class:`Package` instances that are linked to this app.'''
        return [ap.package for ap in self.app_packages]

    @classmethod
    def by_steamid(cls, steamid):
        '''Retrieve an App from the database by its ``steamid``.

        :param str steamid:
            The ``appid`` to retrieve.
        :returns: The requested :class:`App` instance
        :rtype: :class:`App`
        '''
        return cls.select().where(cls.steamid == steamid).limit(1).first()

    @classmethod
    def from_apidata(cls, steamid, apidata, **extra):
        '''Create an App with data from the ``storeapi``.

        This method accepts the result from a call to
        :func:`steamwatch.storeapi.appdetails`.
        The ``apidata`` *dict* looks like this,
        only ``kind`` is required:

        .. code:: python

            {
                'type':      '<type>',           # required
                'enabled':   True,
                'name':      'Display Name',
                'threshold': 123,
            }

        :param str steamid:
            The steam ``appid`` for the App.
        :param dict apidata:
            A dictionary with app details.
        :returns:
            A new App instance is already **saved to the database**.
        :rtype: :class:`App`
        '''
        return cls.create(
            steamid=steamid,
            kind=apidata['type'],
            enabled=extra.get('enabled', True),
            name=apidata.get('name'),
            threshold=extra.get('threshold'),
        )

    def __repr__(self):
        return '<App id={s.id!r} steamid={s.steamid!r}>'.format(s=self)


class Package(BaseModel):
    '''A *Package* on the steam store.

    :var str steamid:
        The id of this package on the steam store.
    :var str name:
        The display name for this package.
    '''

    steamid = CharField(unique=True, index=True)
    name = CharField(null=True)

    def record_snapshot(self, apidata):
        '''Record a Snapshot from the given ``apidata``
        *only if* it is different from the previously recorded snapshot.

        :param dict apidata:
            *dict* with package details; accepts the format from
            :func:`steamwatch.storeapi.packagedetails`.
        :returns:
            The :class:`Snapshot` instance if one was created, else *None*.
        :rtype: :class:`Snapshot`
        '''
        snapshot = Snapshot.from_apidata(self, apidata)
        if snapshot.is_different():  # to previous
            snapshot.save()
            return snapshot

    def link(self, app):
        '''Link this Package to an :class:`App`.

        This has the same effect as :meth:`App.link`.

        '''
        AppPackage.create(app=app, package=self)

    def recent_snapshots(self, limit=None):
        '''Get a list of recent :class:`Snapshot`s for this *Package*.'''
        query = (self.snapshots
                 .select()
                 .order_by(Snapshot.timestamp.desc())
                 .limit(limit or 1)
                )
        return [snapshot for snapshot in query]

    @property
    def apps(self):
        '''A list of :class:`App` instances linked to this package.

        The list is read only, use :meth:`link` to link an App to this package.
        '''
        return [ap.app for ap in self.app_packages]

    @classmethod
    def by_steamid(cls, steamid):
        '''Find a Package by its ``steamid``'''
        return cls.select().where(cls.steamid == steamid).limit(1).first()

    @classmethod
    def from_apidata(cls, steamid, apidata):
        '''Create a Package with data from the ``storeapi``.

        The ``apidata`` dict is the same format as created by
        :func:`steamwatch.storeapi.packagedetails`

        .. code:: python

            {
                'name': 'Display Name',
            }

        The newly created package is **saved to the database**.

        '''
        return cls.create(
            steamid=steamid,
            name=apidata.get('name')
        )

    def __repr__(self):
        return '<Package id={s.id!r} steamid={s.steamid!r}>'.format(s=self)


class AppPackage(BaseModel):
    '''Link between an :class:`App` and a :class:`Package`.

    :var object app: The *App*.
    :var object package: The *Package*.
    '''

    app = ForeignKeyField(App, related_name='app_packages')
    package = ForeignKeyField(Package, related_name='app_packages')

    class Meta:
        # see
        # https://peewee.readthedocs.org/en/latest/peewee/models.html#non-integer-primary-keys-composite-keys-and-other-tricks
        primary_key = CompositeKey('app', 'package')

    def __repr__(self):
        return '<AppPackage app={s.app!r} package={s.package!r}>'.format(s=self)


class Snapshot(BaseModel):
    '''A snapshot of :class:`Package` related data.

    Snapshot instances hold the values of all tracked fields and a timestamp.
    Snapshots are normally created in :meth:`steamwatch.application.fetch`
    when one or more properties of a package have changed compared to the
    most recent snapshot in the database.

    :var object package:
        The :class:`Package`
    :var datetime timestamp:
        Date nad time when this snapshot was recorded.
    :var str currency:
        The recorded *currency* property.
    :var int price:
        The recorded price property.
    :var date release_date:
        The recorded release date property.
    :var bool coming_soon:
        The recorded "coming soon" property.
    :var bool supports_linux:
        The recorded "supports linux" property.
    '''

    package = ForeignKeyField(Package, related_name='snapshots')
    timestamp = DateTimeField(index=True)
    currency = CharField(null=True)
    price = IntegerField(null=True)
    release_date = DateField(null=True)
    coming_soon = BooleanField(null=True)
    supports_linux = BooleanField()

    @classmethod
    def from_apidata(cls, pkg, apidata):
        '''Create a Snapshot instance with package details from the storeapi.

        The ``apidata`` dict is the same format as created by
        :func:`steamwatch.storeapi.packagedetails`:

        .. code:: python

            {
                'price': {
                    'currency': 'EUR',
                    'final': 1299,
                },
                'release': {
                    'date': '30 May, 2014',
                    'coming_soon': False,
                },
                'platforms': {
                    'linux': True,
                }
            }

        The Snapshot is not saved to the database.
        '''
        price = apidata.get('price', {})
        release = apidata.get('release_date', {})
        return cls(
            package=pkg,
            timestamp=datetime.utcnow(),
            currency=price.get('currency'),
            price=price.get('final'),
            release_date=_parse_date(release.get('date', '')),
            coming_soon=release.get('coming_soon'),
            supports_linux=apidata.get('platforms', {}).get('linux', False)
        )

    @property
    def previous(self):
        '''Get the Snapshot that was recorded before this one.'''
        return Snapshot.select().where(
            Snapshot.package == self.package,
            Snapshot.timestamp < self.timestamp
        ).order_by(
            Snapshot.timestamp.desc()
        ).limit(1).first()

    def diff(self, other=None):
        '''Return the *diff* between this snapshot and another snapshot.

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
            # return None if `other` is None
            thine = getattr(other, field, None)
            if mine != thine:
                diffs.append((field, mine, thine))

        return diffs

    def is_different(self, other=None):
        '''Tell if this snapshot is different to another snapshot.
        The snapshot to compare against can be supplied (with ``other``).
        If not supplied, we compare against the ``previous`` snapshot.

        See :meth:`diff` for a list of properties that are considered when
        checking for differences.
        '''
        return bool(self.diff(other=other))

    @classmethod
    def recent(cls, limit=None):
        '''List recent snapshots and their associated packages.'''
        query = (
            cls.select(cls, Package)
            .join(Package)
            .order_by(cls.timestamp.desc())
        )
        if limit:
            query = query.limit(limit)
        return query

    def __repr__(self):
        return '<Snapshot id={s.id!r} package={s.package!r}>'.format(s=self)


# Helpers ---------------------------------------------------------------------


# https://docs.python.org/3.3/library/datetime.html#strftime-and-strptime-behavior
DATEFORMAT = '%d %B, %Y'  # e.g. "30 May, 2014"


def _parse_date(datestr):
    try:
        return datetime.strptime(datestr, DATEFORMAT).date()
    except ValueError:
        pass
