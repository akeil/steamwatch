#-*- coding: utf-8 -*-
'''
Main application module.
'''
import logging

from datetime import datetime
from pkg_resources import iter_entry_points

from steamwatch.exceptions import GameNotFoundError
from steamwatch.models import Game, Measure
from steamwatch.models import Database
from steamwatch.models import NotFoundError
from steamwatch import storeapi


log = logging.getLogger(__name__)


EP_SIGNALS = 'steamwatch.signals'
SIGNAL_ADDED = 'added'
SIGNAL_REMOVED = 'removed'
SIGNAL_PRICE = 'price'
SIGNAL_THRESHOLD = 'threshold'


class Application(object):

    def __init__(self, db_path):
        self.db = Database(db_path)

    def watch(self, appid, threshold=None):
        '''Start watching for changes on the steam item with the given
        ``appid``.

        If this ``appid`` is new, it is added to the database.

        If the item is already in the database but is *disabled*, it is
        *enabled*.

        If the item is already being watched, nothing happens.
        '''
        should_update = False
        try:
            known = self.get(appid)
        except NotFoundError:
            known = None

        if known and known.enabled:
            log.warning(('Attempted to add {a!r} to the watchlist'
                ' but it is already being watched.').format(a=appid))
            game = known
        elif known:  # is disabled
            game = known
            game.enable()
            game.save(self.db)
            should_update = True

        else:  # not previously known
            results = storeapi.appdetails(appid)
            try:
                data = results[appid]['data']
            except KeyError:
                raise GameNotFoundError('No game with appid {!r}.'.format(appid))
            game = Game(
                appid=appid,
                name = data.get('name'),
                threshold=threshold,
            )
            game.save(self.db)
            should_update = True

        if should_update:
            log.info('{g.name!r} was added to the watchlist.'.format(g=game))
            self._signal(SIGNAL_ADDED, gameid=game.id, appid=game.appid)
            self.fetch(game)

        return game

    def unwatch(self, appid, delete=False):
        '''Stop watching the game with the given appid.

        If the game is currently bein watched, it will be *disabled*,
        unless the optional parameter ``delete`` is set to *True*
        (which will completely remove the game and all measures.)

        If the game is currently not being watched, nothing happens.'''
        try:
            game = self.get(appid)
        except NotFoundError:
            log.warning(('Attempted to remove {a!r} from the watchlist'
                ' but it was not watched.').format(a=appid))
            return

        if delete:
            m = Measure.select(self.db).where('gameid').equals(game.id).many()
            for measure in m:
                measure.delete(self.db)
            game.delete(self.db)
            log.info('Deleted {g.name!r}'.format(g=game))
        else:
            game.disable()
            game.save(self.db)
            log.info('Disabled {g.name!r}'.format(g=game))

        self._signal(SIGNAL_REMOVED, gameid=game.id, appid=game.appid)

    def get(self, appid):
        '''Get the :class:`Game` that is associated with the given ``appid``.

        :param str appid:
            The steam appid.
        :rtype:
            A :class:`Game` object.
        :raises:
            `NotFoundError` if we are not watching the given ``appid``.
        '''
        return Game.select(self.db).where('appid').equals(appid).one()

    def ls(self):
        '''List games'''
        select = Game.select(self.db)
        select.order_by('enabled', desc=True).order_by('name')
        return select.many()

    def fetch_all(self):
        '''Update measures for all enabled Games.'''
        #TODO should be possible to call .equals(True)
        games = Game.select(self.db).where('enabled').equals('1').many()
        for game in games:
            self.fetch(game)

    def fetch(self, game):
        '''Update measures for the given Game.'''
        if not game.enabled:
            log.warning('{g!r} is disabled and will not be updated.'.format(
                g=Game))
            return

        appid = game.appid
        results = storeapi.appdetails(appid)
        data = results[appid]['data']
        self._store_measure(game, data)

    def _store_measure(self, game, data):
        po = data.get('price_overview', {})
        currency = po.get('currency')
        price = po.get('final')
        baseprice = po.get('initial')
        discount = po.get('discount_percent')

        current = Measure(
            gameid=game.id,
            currency=currency,
            price=price / 100.0 if price else None,
            baseprice=baseprice / 100.0 if baseprice else None,
            discount=discount,
            metacritic=data.get('metacritic', {}).get('score'),
            datetaken=datetime.now()
        )

        select = Measure.select(self.db).where('gameid').equals(game.id)
        select.order_by('datetaken', desc=True).limit(1)
        try:
            previous = select.one()
        except NotFoundError:
            previous = None

        if not previous or previous.is_different(current):
            current.save(self.db)
            if previous:
                self._changes(game, current, previous)

    def _changes(self, game, current, previous):
        if current.price != previous.price:
            self._signal(SIGNAL_PRICE,
                gameid=game.id,
                previous=previous.price,
                current=current.price
            )

            if game.threshold and current_measure.price <= game.threshold:
                self._signal(SIGNAL_THRESHOLD,
                    gameid=game.id,
                    threshold=game.threshold,
                    current=current.price
                )

    def report(self, game):
        '''List Measures for the given Game.'''
        measures = Measure.select(self.db).where('gameid').equals(game.id).many()
        #TODO order_by
        measures.sort(key=lambda x: x.datetaken)
        return measures

    def report_all(self):
        '''List Measures for all enabled Games.'''
        #TODO .equals(True)
        games = Game.select(self.db).where('enabled').equals('1').many()
        reports = {}
        for game in games:
            reports[game] = self.report(game)

        return reports

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


def log_signal(name, app, **kwargs):
    '''Default hook function for signals.'''
    s = ', '.join(['{k}={v!r}'.format(k=k, v=v) for k, v in kwargs.items()])
    log.debug('Signal {n!r} with {s!r}'.format(n=name, s=s))
