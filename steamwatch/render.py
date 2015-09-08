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
        self.out.write(str(text))

    def writeln(self, text=None):
        if text:
            self.write(text)
        self.write('\n')


class TreeRenderer(Renderer):
    #TODO: convert datetimes to local tz

    def __init__(self, out, options):
        super(TreeRenderer, self).__init__(out, options)

        unicode = True
        if unicode:
            self.vert = '\u2502'  # │
            self.vert_bold = '\u2503'
            self.split = '\u251C' # ├╴
            self.split_bold = '\u2523' # ├╴
            self.turn = '\u2514'  # └╴
            self.turn_bold = '\u2517'  # └╴
            self.hor = '\u2500'  # ─
            self.hor_bold = '\u2501'
            self.hor_end = '\u2574'  # ╴
            self.hor_end_bold = '\u2578'
            self.gut = ' '
        else:
            self.vert = '|'
            self.vert_bold = '|'
            self.split = '+'
            self.split_bold = '+'
            self.turn = '`'
            self.turn_bold = '`'
            self.hor = '-'
            self.hor_bold = '-'
            self.hor_end = '-'
            self.hor_end_bold = '-'
            self.gut = ' '

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
        self.write(self.turn_bold if last_app else self.split_bold)
        self.write(self.hor_bold)
        self.write(self.hor_end_bold)

        # app details
        self.write(bold(app.name))
        self.write(' ')
        self.write(dim('[{s: >6}]'.format(s=app.steamid)))
        self.writeln()

    def _render_pkg(self, pkg, last_app, last_pkg):
        # app level
        self.write(self.gut if last_app else self.vert_bold)
        self.write(self.gut)
        self.write(self.gut)

        # pkg level
        self.write(self.turn if last_pkg else self.split)
        self.write(self.hor)
        self.write(self.hor_end)

        # details
        self.write(pkg.name)
        self.write(' ')
        self.write(dim('[{s: >6}]'.format(s=pkg.steamid)))
        self.writeln()

    def _render_snapshot(self, snapshot, last_app, last_pkg, last_snapshot):
        # app level
        self.write(self.gut if last_app else self.vert_bold)
        self.write(self.gut)
        self.write(self.gut)

        # pkg level
        self.write(self.gut if last_pkg else self.vert)
        self.write(self.gut)
        self.write(self.gut)

        # snapshot level
        self.write(self.turn if last_snapshot else self.split)
        self.write(self.hor)
        self.write(self.hor_end)

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
        self.write(bold('{s.price:>5}'.format(s=snapshot)))
        self.writeln()


class TabularRenderer(Renderer):
    '''Render as a table like this:

    Report
    ------
    ::
        -------+--------------------------------------------------------------+
        ID     | Game                                                         |
        ID     | Package     | Timestamp        | Linux | Release     | Price |
        -------+-------------+------------------+-------+-------------+-------|
        000006 | One Game                                                     |
        -------+-------------+------------------+-------+-------------+-------+
        000011 | One Package | 2015-09-07 11:00 |  Yes  | 2015-09-11  |  1999 |
        000011 | One Package | 2015-09-08 15:00 |  Yes  | 2015-09-11  |  2499 |
        -------+-------------+------------------+-------+-------------+-------+
        004711 | Other Pa... | 2015-09-07 11:00 |  Yes  | Coming Soon |  1999 |
        004711 | Other Pa... | 2015-08-31 16:00 |  Yes  | Coming Soon |  2499 |
        -------+-------------+------------------+-------+-------------+-------+
        000006 | Another Game                                                 |
        -------+-------------+------------------+-------+-------------+-------|

    Columns:
        0   steamid         6
        1   name            %
        2   timestamp       16
        3   supports_linux  5 (values: 3)
        4   release         10
        5   price           5
    '''

    def __init__(self, out, options):
        super(TabularRenderer, self).__init__(out, options)
        self.columns = (
            ('steamid', 'ID', 6, None),
            ('name', 'Name', None, None),
            ('timestamp', 'Timestamp', 16, TabularRenderer._timestamp),
            ('supports_linux', 'Linux', 5,  TabularRenderer._yesno),
            ('release', 'Release', 10,  TabularRenderer._date),
            ('price', 'Price', 5, TabularRenderer._price),
        )
        unicode = True
        if unicode:
            # box drawings
            self.top = '\u2501'  # heavy horizontal
            self.bottom = '\u2501'  # heavy horizontal
            self.top_left = '\u250F'  # heavy down and right
            self.top_right = '\u2513'  # heavy down and left
            self.bottom_left = '\u2517'  # heavy up and right
            self.bottom_right = '\u251B'  # heavy up and left
            self.top_split = '\u252F'  # down light and horizontal heavy
            self.top_split_body = '\u252C'  # light down and horizontal
            self.bottom_split = '\u2537'  # up light and horizontal heavy
            self.bottom_split_body = '\u2534'  # light up and horizontal
            self.left_split = '\u2520'  # vertical heavy and right light
            self.right_split = '\u2528'  # vertical heavy and left light
            self.left = '\u2503'  # heavy vertical
            self.right = '\u2503'  # heavy vertical
            self.center = '\u2502'  # light vertical
            self.cross = '\u253C'  # light vertical and horizontal
            self.hor = '\u2500'  # light horizontal
        else:
            self.top = '-'
            self.bottom = '-'
            self.top_left = '+'
            self.top_right = '+'
            self.bottom_left = '+'
            self.bottom_right = '+'
            self.top_split = '+'
            self.top_split_body = '+'
            self.bottom_split = '+'
            self.bottom_split_body = '+'
            self.left_split = '+'
            self.right_split = '+'
            self.left = '|'
            self.right = '|'
            self.center = '|'
            self.cross = '+'
            self.hor = '-'

    def render_report(self, report):
        col_widths = self._calc_col_widths()

        self._render_top_grid(col_widths)
        self._render_header(col_widths)

        for app_index, app_packages in enumerate(report):
            app, packages = app_packages
            last_app = app_index == len(report) - 1
            self._render_app(app)
            self._render_body_grid_below_cellspan(col_widths)

            for pkg_index, pkg_snapshots in enumerate(packages):
                pkg, snapshots = pkg_snapshots
                last_pkg = pkg_index == len(packages) -1

                for snapshot_index, snapshot in enumerate(snapshots):
                    last_snapshot = snapshot_index == len(snapshots) - 1
                    self._render_snapshot(col_widths, pkg, snapshot)

                    if not (last_app and last_pkg and last_snapshot):
                        if last_snapshot and last_pkg:
                            self._render_body_grid_above_cellspan(col_widths)
                        else:
                            self._render_hgrid(col_widths)

        self._render_bottom_grid(col_widths)

    def _calc_col_widths(self):
        available = 79
        #TODO actually calculate from col defs
        #TODO avalable space from self.options
        #TODO deal with insuffcient space
        num_cols = len(self.columns)
        used_by_cols = 6+16+5+10+5
        used_by_grid = num_cols + 1 # grid lines
        # space around grid lines in inner grid (2) and outer (1)
        used_by_gutter = (num_cols - 1) * 2 + 2
        return (
            6,
            79-(used_by_cols + used_by_grid + used_by_gutter),
            16, 6, 10, 5
        )

    def _render_header(self, col_widths):
        # first header
        self.write(self.left)
        self.write(' ')  # gutter
        self.write('ID')
        self.write(' ' * (col_widths[0] - 2))
        self.write(' ')  # gutter
        self.write(self.center)
        self.write(' ')  # gutter
        self.write('Name')
        self.write(' ' * (col_widths[1] - 4))
        for i in range(2, len(col_widths)):
            self.write(' ' * col_widths[i])
            self.write(' ')  # gutter
            self.write(' ')  # gutter
            self.write(' ')  # gutter
        self.write(' ')  # gutter
        self.write(self.right)
        self.writeln()

        # second header
        for index, column in enumerate(self.columns):
            if index == 0:  # first
                self.write(self.left)
                self.write(' ')  # gutter
            label = column[1]
            self.write(label)
            w = col_widths[index]
            self.write(' ' * (w-len(label)))
            self.write(' ')  # gutter
            if index >= len(self.columns) - 1:  # last
                self.write(self.right)
            else:
                self.write(self.center)
                self.write(' ')  # gutter

        self.writeln()

        self._render_hgrid(col_widths)


    def _render_hgrid(self, col_widths):
        for index, column in enumerate(self.columns):
            if index == 0:  # first
                self.write(self.left_split)

            self.write(self.hor) # gutter
            self.write(self.hor * col_widths[index])
            self.write(self.hor) # gutter
            if index == len(self.columns) - 1:  # last
                self.write(self.right_split)
            else:
                self.write(self.cross)

        self.writeln()

    def _render_body_grid_below_cellspan(self, col_widths):
        for index, column in enumerate(self.columns):
            if index == 0:  # first
                self.write(self.left_split)

            self.write(self.hor) # gutter
            self.write(self.hor * col_widths[index])
            self.write(self.hor) # gutter
            if index == len(self.columns) - 1:  # last
                self.write(self.right_split)
            elif index == 0:
                self.write(self.cross)
            else:
                self.write(self.top_split_body)

        self.writeln()

    def _render_body_grid_above_cellspan(self, col_widths):
        for index, column in enumerate(self.columns):
            if index == 0:  # first
                self.write(self.left_split)

            self.write(self.hor) # gutter
            self.write(self.hor * col_widths[index])
            self.write(self.hor) # gutter
            if index == len(self.columns) - 1:  # last
                self.write(self.right_split)
            elif index == 0:
                self.write(self.cross)
            else:
                self.write(self.bottom_split_body)

        self.writeln()

    def _render_top_grid(self, col_widths):
        # grid
        self.write(self.top_left)
        self.write(self.top)  # gutter
        self.write(self.top * col_widths[0])
        self.write(self.top)  # gutter
        self.write(self.top_split)
        self.write(self.top)  # gutter
        for i in range(1, len(col_widths)):
            #self.write(i)
            self.write(self.top * col_widths[i])
            self.write(self.top)  # gutter
            if i >= len(col_widths) - 1:  # last column
                self.write(self.top_right)
            else:
                self.write(self.top)  # would be top split
                self.write(self.top)  # gutter
        self.writeln()

    def _render_bottom_grid(self, col_widths):
        for index, w in enumerate(col_widths):
            if index == 0:
                self.write(self.bottom_left)

            self.write(self.bottom) # gutter
            self.write(self.bottom * w)
            self.write(self.bottom) # gutter

            if index == len(col_widths) -1:
                self.write(self.bottom_right)
            else:
                self.write(self.bottom_split)
        self.writeln()

    def _render_app(self, app):
        self.write(self.left)
        self.write(' ')
        self.write(dim('{s: >6}'.format(s=app.steamid)))
        self.write(' ')
        self.write(self.center)
        self.write(' ')
        name = app.name
        self.write(bold(name))
        w = 79 - 2 - 6 - 3 - 2 - len(name) + 1
        self.write(' ' * w)
        self.write(' ')
        self.write(self.right)
        self.writeln()

    def _render_snapshot(self, col_widths, pkg, snapshot):
        for index, column in enumerate(self.columns):
            if index == 0:  #first
                self.write(self.left)
            else:
                self.write(' ')
                self.write(self.center)
            self.write(' ')

            if index == 0:
                self.write(dim('{s: >6}'.format(s=pkg.steamid)))
            elif index == 1:
                name = pkg.name
                if len(name) > col_widths[1]:
                    name = pkg.name[:col_widths[1]]
                    #TODO ellipsis
                self.write(name)
                self.write(' ' * max(0, col_widths[1] - len(name)))
            else:
                v = self._get(column, snapshot)
                w = col_widths[index]
                self.write(v[:w])
                self.write(' ' * max(0, w - len(v)))

            if index == len(self.columns) - 1:  # last
                self.write(' ')
                self.write(self.right)

        self.writeln()

    def _get(self, column, snapshot):
        if column[0] == 'release':
            return ''
        else:
            raw = getattr(snapshot, column[0])
            if column[3]:
                return column[3](raw)
            else:
                return str(raw)

    @staticmethod
    def _timestamp(v):
        if v:
            return v.strftime('%Y-%m-%d %H:%M')
        else:
            return ''

    @staticmethod
    def _date(v):
        if v:
            return v.strftime('%Y-%m-%d')
        else:
            return ''

    @staticmethod
    def _price(v):
        return '{v: >5}'.format(v=v)

    @staticmethod
    def _yesno(v):
        return 'Yes' if v else 'No'


def bold(text):
    return '\033[1m' + text + '\033[0m'

def dim(text):
    return '\033[2m' + text + '\033[0m'

# RSSRenderer
# JSONRenderer
# XMLRenderer
# HTMLRenderer
