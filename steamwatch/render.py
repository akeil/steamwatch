#-*- coding: utf-8 -*-
'''
Renderers for the command line interface.

Each output option is implemented by a :class:`Renderer`.
Each renderer must implement
- render ls
- render report

'''
import logging


log = logging.getLogger(__name__)


class Renderer:
    '''Renderer base class'''
    def __init__(self, out, options):
        self.out = out
        self.options = options

    def render_ls(self):
        pass

    def render_report(self, report):
        '''Render a report.

        The report structure is::

        [
            (<app>, [
                (<package>, [<snapshot>, <snapshot>]),
                (<package>, [<snapshot>, <snapshot>]),
            ]),
            (<app>, [
                (<package>, [<snapshot>, <snapshot>]),
                (<package>, [<snapshot>, <snapshot>]),
            ]),
        ]

        '''
        pass

    def write(self, text):
        self.out.write(text)

    def writeln(self, text=None):
        if text:
            self.write(text)
        self.write('\n')


VERT = '\u2502'  # │
SPLIT = '\u251C' # ├╴
TURN = '\u2514'  # └╴
HOR = '\u2500'  # ─
HOR_END = '\u2574'  # ╴
GUT = ' '


class TreeRenderer(Renderer):

    def render_report(self, report):
        self._render_root()
        for app_index, app_pkgs in enumerate(report):
            last_app = app_index + 1 >= len(report)
            app, pkgs = app_pkgs  # unpack
            self._render_app(app, last_app)

            for pkg_index, pkg_snapshots in enumerate(pkgs):
                last_pkg = pkg_index + 1 >= len(pkgs)
                pkg, snapshots = pkg_snapshots  # unpack
                self._render_pkg(pkg, last_app, last_pkg)

                for snapshot_index, snapshot in enumerate(snapshots):
                    last_snapshot = snapshot_index + 1 >= len(snapshots)
                    self._render_snapshot(snapshot, last_app, last_pkg, last_snapshot)

    def _render_root(self):
        self.writeln('Report')

    def _render_app(self, app, last_app):
        # app level
        self.write(TURN if last_app else SPLIT)
        self.write(HOR)
        self.write(HOR_END)

        # app details
        self.write(app.name)
        self.write(' ')
        self.write(app.steamid)
        self.writeln()

    def _render_pkg(self, pkg, last_app, last_pkg):
        # app level
        self.write(GUT if last_app else VERT)
        self.write(GUT)
        self.write(GUT)

        # pkg level
        self.write(TURN if last_pkg else SPLIT)
        self.write(HOR)
        self.write(HOR_END)

        # details
        self.write(pkg.name)
        self.write(' ')
        self.write(pkg.steamid)
        self.writeln()

    def _render_snapshot(self, snapshot, last_app, last_pkg, last_snapshot):
        # app level
        self.write(GUT if last_app else VERT)
        self.write(GUT)
        self.write(GUT)

        # pkg level
        self.write(GUT if last_pkg else VERT)
        self.write(GUT)
        self.write(GUT)

        # snapshot level
        self.write(TURN if last_snapshot else SPLIT)
        self.write(HOR)
        self.write(HOR_END)

        # details
        self.write(snapshot.timestamp.strftime('%Y-%m-%d %H:%M'))
        self.write('  ')
        self.write('Linux' if snapshot.supports_linux else '-----')
        self.write('  ')
        if snapshot.release_date:
            self.write(snapshot.release_date.strftime('%Y-%m-%d'))
            self.write(' ')
        elif snapshot.coming_soon:
            self.write('coming soon')
        else:
            self.write('-----------')
        self.write('  ')
        self.write(snapshot.currency)
        self.write(' ')
        self.write('{s.price:>5}'.format(s=snapshot))
        self.writeln()
