#! /usr/bin/python
# -*- coding: utf-8 -*-
'''
Main entry point as defined in setup.py.

Sets up the argument parser,
configures logging
and runs the program.
'''
import argparse
import io
import logging
import os
import sys

from logging import handlers
from pkg_resources import resource_stream

try:
    import configparser  # python 3
except ImportError:
    import ConfigParser as configparser  # python 2

import steamwatch
from steamwatch import application
from steamwatch.exceptions import ConfigurationError
from steamwatch.model import App


PROG_NAME = 'steamwatch'
VERSION = steamwatch.__version__
DESCRIPTION = 'Watch prices on Steam store'
AUTHOR = steamwatch.__author__
AUTHOR_MAIL = steamwatch.__email__

# Logging config
CONSOLE_FMT = '%(levelname)s: %(message)s'
SYSLOG_FMT = '%(levelname)s [%(name)s]: %(message)s'
LOGFILE_FMT = '%(asctime)s %(levelname)s [%(name)s]: %(message)s'
DEFAULT_LOG_LEVEL = 'warning'

# Default locations for config files.
SYSTEM_CONFIG_PATH = '/etc/steamwatch.conf'
USER_CONFIG_PATH = os.path.expanduser(
    '~/.config/steamwatch/steamwatch.conf')

DEFAULT_CONFIG_SECTION = 'steamwatch'

EXIT_OK = 0
EXIT_ERROR = 1


log = logging.getLogger(PROG_NAME)


def main(argv=None):
    '''Main entry point for console scripts as defined in setup.py.

    Parses command-line args, reads configuration files
    and configures logging.
    Then launches the application.

    Return Codes
    ------------

    Value Constant    Description
    ===== =========== =========================
    0     EXIT_OK     no errors
    1     EXIT_ERROR  error during execution

    :param list argv:
        Command line arguments. If *None* (default), ``sys.argv`` is used.
    :rtype int:
        An integer return code.
    '''
    if argv is None:
        argv = sys.argv[1:]

    parser = setup_argparser()
    options = read_config()
    parser.parse_args(argv, namespace=options)
    configure_logging(options)

    log.info('Starting {!r}.'.format(PROG_NAME))
    log.debug('Command line: {!r}.'.format(' '.join(argv)))
    _log_options(options)

    try:
        run(options)
        rv = EXIT_OK
    except KeyboardInterrupt:
        raise
    except Exception as e:
        log.exception(e)
        log.error(e)
        rv = EXIT_ERROR
    finally:
        # TODO perform cleanup
        pass

    log.info('Exit with return code: {}.'.format(rv))
    return rv


def _log_options(options):
    for k, v in vars(options).items():
        if isinstance(v, argparse.Namespace):
            log.debug('Section {s!r}'.format(s=k))
            _log_options(v)
        else:
            log.debug('Option {k}: {v!r}'.format(k=k, v=v))


def run(options):
    '''Run steamwatch with the given command line args
    and config.

    :param object options:
        A ``Namespace`` instance with arguments from the command line
        and from the config file(s).
    '''
    app = application.Application(options)
    return options.func(app, options)


# Argument parser ------------------------------------------------------------


def setup_argparser():
    '''Create an configure the ``ArgumentParser`` used to interpret
    command line arguments.

    :rtype object ArgumentParser:
        The configured ArgumentParser instance.
    '''
    parser = argparse.ArgumentParser(
        prog=PROG_NAME,
        description=DESCRIPTION,
        epilog='{p} Version {v} -- {author} <{mail}>'.format(
            p=PROG_NAME, v=VERSION,
            author=AUTHOR, mail=AUTHOR_MAIL
        )
    )

    parser.add_argument(
        '--version',
        action='version',
        version='{p} {v}'.format(p=PROG_NAME, v=VERSION),
        help='Print version number and exit.'
    )

    common = argparse.ArgumentParser(add_help=False)

    common.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Increase console output.',
    )

    common.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Write nothing to stdout.',
    )

    common.add_argument(
        '-l', '--logfile',
        help=('Write logs to the specified file. Use LOGFILE="syslog"'
            ' to write logging output to syslog.')
    )

    loglevels = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL,
    }

    class LogLevelAction(argparse.Action):

        def __call__(self, parser, namespace, values, option_string=None):
            level = loglevels[values]
            setattr(namespace, self.dest, level)

    common.add_argument(
        '--log-level',
        action=LogLevelAction,
        default=logging.WARNING,
        choices=loglevels.keys(),
        help=('Controls the log-level for LOGFILE.'
            ' Defaults to {default}.').format(default=DEFAULT_LOG_LEVEL),
    )

    subs = parser.add_subparsers()
    watch(subs, common)
    unwatch(subs, common)
    ls(subs, common)
    fetch(subs, common)
    report(subs, common)

    return parser


# Commands --------------------------------------------------------------------


def watch(subs, common):
    watch = subs.add_parser(
        'watch',
        parents=[common, ],
        help='Add a game (appid) to watch'
    )

    watch.add_argument(
        'appid',
        help=('The id of the game to watch')
    )

    watch.add_argument(
        '-t', '--threshold',
        metavar='PRICE',
        type=float,
        help=('Receive a notification if the game drops below this price')
    )

    def do_watch(app, options):
        app.watch(options.appid, threshold=options.threshold)

    watch.set_defaults(func=do_watch)


def unwatch(subs, common):
    unwatch = subs.add_parser(
        'unwatch',
        parents=[common, ],
        help='Remove a game (appid) from the watchlist'
    )

    unwatch.add_argument(
        'appid',
        help=('The id of the game to remove')
    )

    unwatch.add_argument(
        '-d', '--delete',
        action='store_true',
        help=('Fully delete instead of disable the game.')
    )

    def do_unwatch(app, options):
        app.unwatch(options.appid, delete=options.delete)

    unwatch.set_defaults(func=do_unwatch)


def ls(subs, common):
    ls = subs.add_parser(
        'ls',
        parents=[common, ],
        help='List watched games'
    )

    def do_ls(app, options):
        _render_apps(app.ls())

    ls.set_defaults(func=do_ls)


def _render_apps(apps):
    for app in apps:
        print('{e} [{a.steamid: >6}] {a.name}'.format(
            a=app, e='*' if app.enabled else '-'))


def fetch(subs, common):
    fetch = subs.add_parser(
        'fetch',
        parents=[common, ],
        help='Fetch prices for watched games from steamstore'
    )

    fetch.add_argument(
        '-g', '--games',
        help=('List of game ids to query. Queries all games if omitted')
    )

    def do_fetch(application, options):
        if options.games:
            for steamid in options.games:
                app = App.by_steamid(steamid)
                if not app:
                    log.warning(
                        'Game with id {s!r} is not watched'.format(s=steamid))
                else:
                    application.fetch(app)
        else:
            application.fetch_all()

    fetch.set_defaults(func=do_fetch)


def report(subs, common):
    report = subs.add_parser(
        'report',
        parents=[common, ],
        help='Show measures for watched apps'
    )

    report.add_argument(
        '-g', '--games',
        nargs='*',
        help=('List of game ids to report. Reports all games if omitted')
    )

    report.add_argument(
        '-n', '--limit',
        type=int,
        help='Limit the number of entries per game'
    )

    def do_report(application, options):
        if options.games:
            reports = []
            for steamid in options.games:
                app = App.by_steamid(steamid)
                if not app:
                    log.warning(
                        'Game with id {s!r} is not watched'.format(s=steamid))
                else:
                    reports.append(
                        (app, application.report(app, limit=options.limit)),
                    )
        else:
            reports = application.report_all(limit=options.limit)

        _render_reports(reports)

    report.set_defaults(func=do_report)


def _render_reports(reports):
    # 007C vertical
    # 2015 horizontal
    # 22AA triple vertical bar right turnstile
    # 22AB double vertical bar right turnstile

    vert = '\u2502'  # │
    turn = '\u2514'  # └╴
    split = '\u251C' # ├╴
    hor = '\u2500\u2574'  # ─ and ╴
    gut = ' '
    out = sys.stdout

    def _(s):
        out.write(s)

    _('Steamwatch Report')
    _('\n')
    for app_index, app_packages in enumerate(reports):
        app, packages = app_packages
        last_app = app_index + 1 >= len(reports)
        _(turn if last_app else split)
        _(hor)
        _('{a.name} [{a.steamid: >6}]'.format(a=app))
        _('\n')
        for pkg_index, pkg_snapshots in enumerate(packages):
            package, snapshots = pkg_snapshots
            last_pkg = pkg_index + 1 >= len(packages)
            _(gut if last_app else vert)
            _(2 * gut)
            _(turn if last_pkg else split)
            _(hor)
            _('{p.name} [{p.steamid: >6}]'.format(p=package))
            _('\n')
            for ss_index, snapshot in enumerate(snapshots):
                last_ss = ss_index + 1 >= len(snapshots)
                _(gut if last_app else vert)
                _(2 * gut)
                _(gut if last_pkg else vert)
                _(2 * gut)
                _(turn if last_ss else split)
                _(hor)
                _(snapshot.timestamp.strftime('%Y-%m-%d %H:%M'))
                _('  {yn}'.format(yn='Linux' if snapshot.supports_linux else '-----'))
                _('  ')
                if snapshot.release_date:
                    _(snapshot.release_date.strftime('%Y-%m-%d '))
                elif snapshot.coming_soon:
                    _('coming soon')
                else:
                    _('-----------')

                _('  {s.price:0>5} {s.currency:>3}'.format(s=snapshot))
                _('\n')


# Argtypes --------------------------------------------------------------------


def _path(argstr):
    '''Convert the given ``argstr`` into an absolute path.
    To be used as the ``type`` parameter for an argument parser.

      - expand user
      - make relative path relative to the working dir.
    :param str argstr:
        The command line argument.
    :rtype str:
        The converted path.
    '''
    path = os.path.expanduser(argstr)
    path = os.path.normpath(path)
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    return path


# Config ---------------------------------------------------------------------


CFG_TYPES = {
    DEFAULT_CONFIG_SECTION: {
        'db_path': _path,
        'report_limit': int,
    },
}


def read_config():
    '''Read configuration from the ``DEFAULT_CONFIG_PATH and
    optionally supplied ``extra_config_paths``.

    :param list extra_config_paths:
        Additional locations to be scanned for config files.
    :param bool require:
        If *True*, raise an error if no config file was found.
        Defaults to *False*.
    :rtype ConfigParser:
        A ``ConfigParser`` with the values read from the
        configuration file(s).
    :raises:
        ``ValueError`` is raised if ``require`` is *True*
        and if no config-file was found.
    '''
    root = argparse.Namespace()
    cfg = configparser.ConfigParser()

    # default config from package
    cfg.readfp(io.TextIOWrapper(
        resource_stream('steamwatch', 'default.conf'))
    )

    # system + user config from files
    read_from = cfg.read([SYSTEM_CONFIG_PATH, USER_CONFIG_PATH,])

    def ns(name):
        rv = None
        if name == DEFAULT_CONFIG_SECTION:
            rv = root
        else:
            try:
                rv = getattr(root, name)
            except AttributeError:
                rv = argparse.Namespace()
                setattr(root, name, rv)
        return rv

    def identity(x):
        return x

    # set config values on namespace(s)
    for section in cfg.sections():
        for option in cfg.options(section):
            value = cfg.get(section, option)
            try:
                conv = CFG_TYPES.get(section, {}).get(option, identity)
                setattr(ns(section), option, conv(value))
            except (TypeError, ValueError):
                log.error(('Failed to convert config value {v!r}'
                    ' for {s!r}, {o!r}').format(s=section, o=option, v=value))

    return root


def configure_logging(options):
    '''Configure log-level and logging handlers.

    :param bool quiet:
        If *True*, do not configure a console handler.
        Defaults to *False*.
    :param bool verbose:
        If *True*, set the log-level for the console handler
        to DEBUG. Has no effect if ``quiet`` is *True*.
        Defaults to *False*.
    :param str logfile:
        If given, set up a RotatingFileHandler to receive logging output.
        Should be the absolute path to the desired logfile
        or special value "syslog".
        Defaults to *None* (no logfile).
    :param int log_level:
        Level to use for ``logfile``.
        Must be one of the constants defined in the ``logging`` module
        (e.g. DEBUG, INFO, ...).
        Has no effect if ``logfile`` is not given.
    '''
    rootlog = logging.getLogger()
    rootlog.setLevel(logging.DEBUG)

    if not options.quiet:
        console_hdl = logging.StreamHandler()
        console_level = logging.DEBUG if options.verbose else logging.WARNING
        console_hdl.setLevel(console_level)
        console_hdl.setFormatter(logging.Formatter(CONSOLE_FMT))
        rootlog.addHandler(console_hdl)

    if options.logfile:
        if logfile == 'syslog':
            logfile_hdl = handlers.SysLogHandler(address='/dev/log')
            logfile_hdl.setFormatter(logging.Formatter(SYSLOG_FMT))
        else:
            logfile_hdl = handlers.RotatingFileHandler(options.logfile)
            logfile_hdl.setFormatter(logging.Formatter(LOGFILE_FMT))
        logfile_hdl.setLevel(options.log_level)
        rootlog.addHandler(logfile_hdl)


if __name__ == '__main__':
    sys.exit(main())
