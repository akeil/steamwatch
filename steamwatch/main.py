#! /usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=logging-format-interpolation
'''
Main entry point as defined in setup.py.

Sets up the argument parser,
configures logging
and runs the program.
'''
import argparse
import io
import logging
from logging import handlers
import os
import sys

try:
    import configparser  # python 3
except ImportError:
    import ConfigParser as configparser  # python 2

from pkg_resources import resource_stream

import steamwatch
from steamwatch import application
from steamwatch.model import App
from steamwatch.render import TabularRenderer
from steamwatch.render import TreeRenderer
from steamwatch.util import extract_appid

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


LOG = logging.getLogger(PROG_NAME)


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

    LOG.info('Starting {!r}.'.format(PROG_NAME))
    LOG.debug('Command line: {!r}.'.format(' '.join(argv)))
    _log_options(options)

    try:
        run(options)
        status = EXIT_OK
    except KeyboardInterrupt:
        raise
    except Exception as err:
        LOG.exception(err)
        LOG.error(err)
        status = EXIT_ERROR
    finally:
        # TODO perform cleanup
        pass

    LOG.info('Exit with return code: {}.'.format(status))
    return status


def _log_options(options):
    for key, value in vars(options).items():
        if isinstance(value, argparse.Namespace):
            LOG.debug('Section {s!r}'.format(s=key))
            _log_options(value)
        else:
            LOG.debug('Option {k}: {v!r}'.format(k=key, v=value))


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

    class LogLevelAction(argparse.Action):  # pylint: disable=too-few-public-methods
        '''Set the Log level'''

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
    recent(subs, common)
    return parser


# Commands --------------------------------------------------------------------


def watch(subs, common):
    '''Set up command line arguments for the ``watch`` command.'''
    parser = subs.add_parser(
        'watch',
        parents=[common, ],
        help='Add a game (appid) to watch'
    )

    parser.add_argument(
        'appid',
        help='The id of the game to watch'
    )

    parser.add_argument(
        '-t', '--threshold',
        metavar='PRICE',
        type=float,
        help='Receive a notification if the game drops below this price'
    )

    def do_watch(app, options):
        '''Execute the ``watch`` command.'''
        appid = extract_appid(options.appid)
        app.watch(appid, threshold=options.threshold)

    parser.set_defaults(func=do_watch)


def unwatch(subs, common):
    '''Set up arguments for the ``unwatch`` command.'''
    parser = subs.add_parser(
        'unwatch',
        parents=[common, ],
        help='Remove a game (appid) from the watchlist'
    )

    parser.add_argument(
        'appid',
        help='The id of the game to remove'
    )

    parser.add_argument(
        '-d', '--delete',
        action='store_true',
        help='Fully delete instead of disable the game.'
    )

    def do_unwatch(app, options):
        '''Execute the ``unwatch`` command.'''
        appid = extract_appid(options.appid)
        app.unwatch(appid, delete=options.delete)

    parser.set_defaults(func=do_unwatch)


def ls(subs, common):  # pylint: disable=invalid-name
    '''Set up arguments for the ``ls`` command.'''
    parser = subs.add_parser(
        'ls',
        parents=[common, ],
        help='List watched games'
    )

    parser.add_argument(
        '-a', '--all',
        action='store_true',
        help='include disabled apps',
    )

    parser.add_argument(
        '-f', '--format',
        choices=('tree', 'tab'),
        help='output format',
    )

    def do_ls(app, options):
        '''Execute the ``ls`` command.'''
        renderers = {
            'tree': TreeRenderer,
            'tab': TabularRenderer,
        }
        renderer_cls = renderers[options.format or options.list_format]
        renderer = renderer_cls(sys.stdout, options)
        renderer.render_ls(app.ls(include_disabled=options.all))

    parser.set_defaults(func=do_ls)


def fetch(subs, common):
    '''Set up arguments for the ``fetch`` command.'''
    parser = subs.add_parser(
        'fetch',
        parents=[common, ],
        help='Fetch prices for watched games from steamstore'
    )

    parser.add_argument(
        '-g', '--games',
        help='List of game ids to query. Queries all games if omitted'
    )

    def do_fetch(app, options):
        '''Execute the ``fetch`` command.'''
        if options.games:
            for identifier in options.games:
                steamid = extract_appid(identifier)
                game = App.by_steamid(steamid)
                if not game:
                    LOG.warning(
                        'Game with id {s!r} is not watched'.format(s=steamid))
                else:
                    app.fetch(game)
        else:
            app.fetch_all()

    parser.set_defaults(func=do_fetch)


def report(subs, common):
    '''Set up arguments for the ``report`` command.'''
    parser = subs.add_parser(
        'report',
        parents=[common, ],
        help='Show measures for watched apps'
    )

    parser.add_argument(
        '-g', '--games',
        nargs='*',
        help='List of game ids to report. Reports all games if omitted'
    )

    parser.add_argument(
        '-n', '--limit',
        type=int,
        help='Limit the number of entries per game'
    )

    parser.add_argument(
        '-f', '--format',
        choices=('tree', 'tab'),
        help='output format',
    )

    def do_report(app, options):
        '''Execute the ``report`` command.'''
        if options.games:
            reports = []
            for identifier in options.games:
                steamid = extract_appid(identifier)
                game = App.by_steamid(steamid)
                if not game:
                    LOG.warning(
                        'Game with id {s!r} is not watched'.format(s=steamid))
                else:
                    reports.append(
                        (game, app.report(game, limit=options.limit)),
                    )
        else:
            reports = app.report_all(limit=options.limit)

        renderers = {
            'tree': TreeRenderer,
            'tab': TabularRenderer
        }
        renderer_cls = renderers[options.format or options.report_format]
        renderer = renderer_cls(sys.stdout, options)
        renderer.render_report(reports)

    parser.set_defaults(func=do_report)


def recent(subs, common):
    '''List recent changes'''
    parser = subs.add_parser(
        'recent',
        parents=[common, ],
        help='Show recent changes'
    )
    parser.add_argument(
        '-n', '--limit',
        type=int,
        help='Limit the number of entries'
    )
    parser.add_argument(
        '-f', '--format',
        choices=('tree', 'tab'),
        help='output format',
    )

    def do_recent(app, options):
        '''Execute the ``recent`` command.'''
        snapshots = app.recent(
            limit=options.limit or options.recent_limit
        )

        renderers = {
            'tree': TreeRenderer,
            'tab': TabularRenderer
        }
        renderer_cls = renderers[options.format or options.recent_format]
        renderer = renderer_cls(sys.stdout, options)
        renderer.render_recent(snapshots)

    parser.set_defaults(func=do_recent)


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
        'recent_limit': int,
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
    cfg.read_file(io.TextIOWrapper(
        resource_stream('steamwatch', 'default.conf')))

    # system + user config from files
    cfg.read([SYSTEM_CONFIG_PATH, USER_CONFIG_PATH,])

    def namespace(name):
        '''Get the *Namespace* with the given ``name`` from the ``root``
        Namespace. Create a new Namespace if necessary.
        '''
        result = None
        if name == DEFAULT_CONFIG_SECTION:
            result = root
        else:
            try:
                result = getattr(root, name)
            except AttributeError:
                result = argparse.Namespace()
                setattr(root, name, result)
        return result

    def identity(value):
        '''Default conversion, returns ``value`` unchanged.'''
        return value

    # set config values on namespace(s)
    for section in cfg.sections():
        for option in cfg.options(section):
            value = cfg.get(section, option)
            try:
                conv = CFG_TYPES.get(section, {}).get(option, identity)
                setattr(namespace(section), option, conv(value))
            except (TypeError, ValueError):
                LOG.error(('Failed to convert config value {v!r}'
                           ' for {s!r}, {o!r}'
                          ).format(s=section, o=option, v=value))

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
        if options.logfile == 'syslog':
            logfile_hdl = handlers.SysLogHandler(address='/dev/log')
            logfile_hdl.setFormatter(logging.Formatter(SYSLOG_FMT))
        else:
            logfile_hdl = handlers.RotatingFileHandler(options.logfile)
            logfile_hdl.setFormatter(logging.Formatter(LOGFILE_FMT))
        logfile_hdl.setLevel(options.log_level)
        rootlog.addHandler(logfile_hdl)


if __name__ == '__main__':
    sys.exit(main())
