#-*- coding: utf-8 -*-
'''
Main application module.

Signals
-------
THe follwoing signals are emitted:

Signal                 args
====================== ===========================
app_added              app
app_removed            app
package_linked         package, app
---------------------- --------------------------
currency_changed       current, previous, package
price_changed          current, previous, package
release_date_changed   current, previous, package
coming_soon_changed    current, previous, package
supports_linux_changed current, previous, package
====================== ==========================

'''
import logging

from datetime import datetime
from pkg_resources import iter_entry_points

from steamwatch.exceptions import GameNotFoundError
from steamwatch.model import init as init_db
from steamwatch.model import App
from steamwatch.model import Package
from steamwatch.model import Snapshot
from steamwatch import storeapi


log = logging.getLogger(__name__)


EP_SIGNALS = 'steamwatch.signals'
SIGNAL_APP_ADDED = 'app_added'
SIGNAL_APP_REMOVED = 'app_removed'
SIGNAL_PACKAGE_LINKED = 'package_linked'
SIGNAL_THRESHOLD = 'threshold'

SIGNAL_CURRENCY = 'currency_changed'
SIGNAL_PRICE = 'price_changed'
SIGNAL_RELEASE_DATE = 'release_date_changed'
SIGNAL_COMING_SOON = 'coming_soon_changed'
SIGNAL_SUPPORTS_LINUX = 'supports_linux_changed'

FIELD_SIGNALS = {
    'currency': SIGNAL_CURRENCY,
    'price': SIGNAL_PRICE,
    'release_date': SIGNAL_RELEASE_DATE,
    'coming_soon': SIGNAL_COMING_SOON,
    'supports_linux': SIGNAL_SUPPORTS_LINUX,
}


class Application(object):

    def __init__(self, options):
        self.options = options
        self.country_code = options.country_code
        init_db(self.options.db_path)

    def watch(self, appid, threshold=None):
        '''Start watching for changes on the steam item with the given
        ``appid``.

        If this ``appid`` is new, it is added to the database.

        If the item is already in the database but is *disabled*, it is
        *enabled*.

        If the item is already being watched, nothing happens.

        Emits ``SIGNAL_APP_ADDED`` when the application is added/enabled.
        '''
        should_update = False
        known = App.by_steamid(appid)

        if known and known.enabled:
            log.warning(('Attempted to add {a!r} to the watchlist'
                ' but it is already being watched.').format(a=appid))
            app = known
        elif known:  # is disabled
            app = known
            app.enable()
            app.save()
            should_update = True

        else:  # not previously known
            data = storeapi.appdetails(appid)
            app = App.from_apidata(appid, data, threshold=threshold)
            app.save()
            should_update = True

        if should_update:
            log.info('{a.name!r} was added to the watchlist.'.format(a=app))
            self._signal(SIGNAL_APP_ADDED, app=app)
            self.fetch(app)

        return app

    def unwatch(self, appid, delete=False):
        '''Stop watching the game with the given appid.

        If the game is currently bein watched, it will be *disabled*,
        unless the optional parameter ``delete`` is set to *True*
        (which will completely remove the game and all measures.)

        If the game is currently not being watched, nothing happens.

        Emits ``SIGNAL_APP_REMOVED`` when the application is deleted/disabled.
        '''
        app = App.by_steamid(appid)
        if app is None:
            log.warning(('Attempted to remove {a!r} from the watchlist'
                ' but it was not watched.').format(a=appid))
            return

        if delete:
            log.debug('Delete {a!r}.'.format(a=app))
            # packages linked to this app can be deleted
            # only if they are not linked to another app
            delete_pkgs = []
            unlink_pkgs = []
            log.debug('Find deletable packages.')
            for pkg in app.packages:
                no_delete = False
                for linked_app in pkg.apps:
                    if linked_app.id != app.id:
                        log.debug(('{p!r} will not be deleted, it is also'
                            ' linked to {a!r}.').format(p=pkg, a=linked_app))
                        no_delete = True
                if no_delete:
                    unlink_pkgs.append(pkg)
                else:
                    delete_pkgs.append(pkg)

            for unlinkable_pkg in unlink_pkgs:
                app.unlink(unlinkable_pkg)

            for deletable_pkg in delete_pkgs:
                log.debug('Delete {p!r}.'.format(p=deletable_pkg))
                # delete associated snapshots
                for snapshot in deletable_pkg.snapshots:
                    log.debug('Delete {s!r}.'.format(s=snapshot))
                    snapshot.delete_instance()
                # delete the package itself
                deletable_pkg.delete_instance()

            # finally, delete the app
            app.delete_instance()
            log.info('Deleted {a.name!r}.'.format(a=app))
        else:
            app.disable()
            app.save()
            log.info('Disabled {a.name!r}'.format(a=app))

        self._signal(SIGNAL_APP_REMOVED, app=app)

    def ls(self):
        '''List apps'''
        return App.select().order_by(App.enabled.desc()).order_by(App.name)

    def fetch_all(self):
        '''Update measures for all enabled Games.'''
        apps = App.select().where(App.enabled==True)
        for app in apps:
            self.fetch(app)

    def fetch(self, app):
        '''Update measures for the given Game.'''
        if not app.enabled:
            log.warning('{a!r} is disabled and will not be updated.'.format(
                a=app))
            # TODO returning w/o saying anything is not ok
            # raise error or update anyway (and skip disabled in fetch_all)
            return

        appdata = storeapi.appdetails(
            app.steamid,
            country_code=self.country_code
        )
        found = appdata.get('packages', [])
        existing = {p.steamid: p for p in app.packages}
        for packageid in found:
            try:
                pkgdata = storeapi.packagedetails(
                    packageid,
                    country_code=self.country_code
                )
                if packageid in existing:
                    pkg = existing[packageid]
                else:
                    # might be present but not linked to this app
                    pkg = Package.by_steamid(packageid)
                    if not pkg:
                        # not yet in db - create it
                        pkg = Package.from_apidata(packageid, pkgdata)
                    pkg.link(app)
                    self._signal(SIGNAL_PACKAGE_LINKED, package=pkg, app=app)

                snapshot = pkg.record_snapshot(pkgdata)
                if snapshot:
                    self._signal_changes(snapshot)
            except GameNotFoundError:
                continue

    def _signal_changes(self, snapshot):
        for field, current, previous in snapshot.diff():
            self._signal(
                FIELD_SIGNALS[field],
                current=current,
                previous=previous,
                package=snapshot.package
            )

    def report(self, app, limit=None):
        '''List Snapshots for the given Game.

        Returns a list of packages with their snapshots::

            [
                (<package-0>, [<snapshot-0>, <snapshot-1>, ...]),
                (<package-1>, [<snapshot-0>, <snapshot-1>, ...]),
            ]
        '''
        results = []
        for package in app.packages:
            select = package.snapshots.order_by(Snapshot.timestamp.desc())
            if limit:
                select = select.limit(limit)
            results.append((package, [s for s in select]))

        return results

    def report_all(self, limit=None):
        '''List Measures for all enabled Games.

        Returns a list of games with packages and snapshots::

            [
                (<game-0>, [
                    (<package-0>, [<snapshot-0>, <snapshot-1>, ...]),
                    (<package-1>, [<snapshot-0>, <snapshot-1>, ...]),
                ]),
                (<game-1>, [
                    (<package-0>, [<snapshot-0>, <snapshot-1>, ...]),
                    (<package-1>, [<snapshot-0>, <snapshot-1>, ...]),
                ]),
                ...
            ]
        '''
        apps = App.select().where(App.enabled == True).order_by(App.name)
        results = []
        for app in apps:
            results.append((app, self.report(app, limit=limit)))

        return results

    def _signal(self, name, **data):
        log.debug('Emit {s!r}.'.format(s=name))
        for ep in iter_entry_points(EP_SIGNALS, name=name):
            try:
                hook = ep.load()
            except (ImportError, SyntaxError) as e:
                log.error('Failed to load entry point {ep!r}'.format(ep=ep))
                log.debug(e, exc_info=True)
                continue

            try:
                kwargs = {k: v for k, v in data.items()}
                hook(name, self, **kwargs)
                log.debug('Dispatched {n!r} to {ep!r}'.format(n=name, ep=ep))
            except Exception as e:
                log.error(('Failed to run entry point for {s!r}.'
                    ' Error was: {e!r}').format(s=name, e=e))
                log.debug(e, exc_info=True)


def log_signal(name, steamwatch, **kwargs):
    '''Default hook function for signals.'''
    s = ', '.join(['{k}={v!r}'.format(k=k, v=v) for k, v in kwargs.items()])
    log.debug('Signal {n!r} with {s!r}'.format(n=name, s=s))
