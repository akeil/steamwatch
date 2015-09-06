#! /usr/bin/python
# -*- coding: utf-8 -*-
'''
Main entry point as defined in setup.py.

Sets up the argument parser,
configures logging
and runs the program.
'''
import argparse
import sys
import os
import logging
from logging import handlers
try:
    import configparser  # python 3
except ImportError:
    import ConfigParser as configparser  # python 2

import steamwatch
from steamwatch import application
from steamwatch.exceptions import ConfigurationError


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
DEFAULT_CONFIG = {
    DEFAULT_CONFIG_SECTION: {
        'db_path': '~/.local/share/steamwatch.db'
    },
}

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
    args = parser.parse_args(argv)
    cfg = read_config()
    configure_logging(
        verbose=args.verbose,
        quiet=args.quiet,
        logfile=args.logfile,
        log_level=args.log_level,
    )

    log.info('Starting {!r}.'.format(PROG_NAME))
    log.debug('Command line: {!r}.'.format(' '.join(argv)))
    try:
        run(args, cfg)
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


def run(args, cfg):
    '''Run steamwatch with the given command line args
    and config.

    :param object args:
        A ``Namespace`` instance with arguments from the command line
    :param object cfg:
        A ``ConfigParser`` instance with values from the config file(s).
    '''
    db_path = os.path.expanduser(cfg.get(DEFAULT_CONFIG_SECTION, 'db_path'))
    app = application.Application(db_path)

    if args.add:
        app.add(args.add)
    if args.update:
        app.update_all()
    if args.report:
        reports = app.report_all()
        _print_report(reports)


def _print_report(reports):
    for game, measures in reports.items():
        print('{} [{}]'.format(game.name, game.appid))
        for m in measures:
            print('  {} {}'.format(m.datetaken, m.price))


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

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Increase console output.',
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Write nothing to stdout.',
    )

    parser.add_argument(
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

    parser.add_argument(
        '--log-level',
        action=LogLevelAction,
        default=logging.WARNING,
        choices=loglevels.keys(),
        help=('Controls the log-level for LOGFILE.'
            ' Defaults to {default}.').format(default=DEFAULT_LOG_LEVEL),
    )

    parser.add_argument(
        '--config',
        type=_path,
        help='Read configuration from the specified file.',
    )

    _add_arg(parser)
    _update_arg(parser)
    _report_arg(parser)

    return parser


def _add_arg(parser):

    parser.add_argument(
        '--add', '-a',
        metavar='APPID',
        help=('Add a new game'),
    )


def _update_arg(parser):

    parser.add_argument(
        '--update', '-u',
        action='store_true',
        help=('Omit argument to update all games.'),
    )


def _report_arg(parser):

    parser.add_argument(
        '--report', '-r',
        action='store_true',
        help=(''),
    )


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


def read_config(extra_config_paths=None, require=False):
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
    extra = [p for p in extra_config_paths or [] if p]
    paths = [SYSTEM_CONFIG_PATH, USER_CONFIG_PATH,] + extra
    cfg = configparser.ConfigParser()

    # set defaults
    for section, settings in DEFAULT_CONFIG.items():
        try:
            cfg.add_section(section)
        except configparser.DuplicateSectionError:
            pass
        for key, value in settings.items():
            cfg.set(section, key, value)

    read_from = cfg.read(paths)
    if not read_from and require:
        raise ConfigurationError(('No configuration file found.'
            ' Searchpath: {!r}.').format(':'.join(paths)))

    log.info('Read configuration from: {}.'.format(':'.join(read_from)))
    return cfg


def configure_logging(quiet=False, verbose=False,
    logfile=None, log_level=DEFAULT_LOG_LEVEL):
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

    if not quiet:
        console_hdl = logging.StreamHandler()
        console_level = logging.DEBUG if verbose else logging.WARNING
        console_hdl.setLevel(console_level)
        console_hdl.setFormatter(logging.Formatter(CONSOLE_FMT))
        rootlog.addHandler(console_hdl)

    if logfile:
        if logfile == 'syslog':
            logfile_hdl = handlers.SysLogHandler(address='/dev/log')
            logfile_hdl.setFormatter(logging.Formatter(SYSLOG_FMT))
        else:
            logfile_hdl = handlers.RotatingFileHandler(logfile)
            logfile_hdl.setFormatter(logging.Formatter(LOGFILE_FMT))
        logfile_hdl.setLevel(log_level)
        rootlog.addHandler(logfile_hdl)


if __name__ == '__main__':
    sys.exit(main())
