#-*- coding: utf-8 -*-
'''
Models for steamwatch
'''
from datetime import datetime
import logging
import sqlite3


log = logging.getLogger(__name__)


# Conversion helpers ----------------------------------------------------------


DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'


def _datetime_to_str(dtvalue):
    return dtvalue.strftime(DATETIME_FORMAT)


def _str_to_datetime(strvalue):
    return datetime.strptime(strvalue, DATETIME_FORMAT)


def _boolean_to_int(boolvalue):
    if boolvalue is None:
        return None
    else:
        return 1 if boolvalue else 0


def _int_to_boolean(intvalue):
    if intvalue is None:
        return None
    elif intvalue == 1:
        return True
    elif intvalue == 0:
        return False
    else:
        raise ValueError('Invalid value {v!r} for boolean'.format(v=intvalue))


# Exceptions ------------------------------------------------------------------


class NotFoundError(Exception):
    pass


class Column(object):

    CONV_DEFAULT = {
        'text': (str, str),
        'integer': (int, int),
        'real': (float, float),
        'datetime': (_datetime_to_str, _str_to_datetime),
        'boolean': (_boolean_to_int, _int_to_boolean),
    }

    def __init__(self, name, datatype='text', null=True, unique=False,
        primary=False, fk=None,
        to_python=None, from_python=None):

        self.name = name
        self.datatype = datatype
        self.null = null
        self.unique = unique
        self.primary = primary
        self.fk = fk
        self._to_python_func = to_python
        self._from_python_func = from_python

    def to_python(self, raw_value):
        if raw_value is None and self.null:
            return None
        if self._to_python_func:
            return self._to_python_func(raw_value)
        else:
            return Column.CONV_DEFAULT[self.datatype][1](raw_value)

    def from_python(self, value):
        if value is None and self.null:
            raw_value = None
        elif self._from_python_func:
            raw_value = self._from_python_func(value)
        else:
            raw_value = Column.CONV_DEFAULT[self.datatype][0](value)

        return raw_value

    def set(self, instance, raw_value):
        value = self.to_python(raw_value)
        setattr(instance, self.name, value)

    def get(self, instance):
        value = getattr(instance, self.name)
        return self.from_python(value)

    @property
    def definition(self):
        constraints = []
        if self.unique:
            constraints.append('UNIQUE')
        if self.primary:
            constraints.append('PRIMARY KEY')
        if not self.null:
            constraints.append('NOT NULL')

        return '{s.name} {s.datatype} {constraints}'.format(
            s=self, constraints=' '.join(constraints))

    @property
    def fk_definition(self):
        if not self.fk:
            return ''
        else:

            return 'FOREIGN KEY({s.name}) REFERENCES {table}({field})'.format(
                s=self, table=self.fk[0].__table__, field=self.fk[1]
            )


class Database(object):

    def __init__(self, path):
        self.path = path
        self.conn = None
        self._setup()

    def _setup(self):
        # create tables
        for cls in (Game, Measure):
            if not self._table_exists(cls):
                self._create_table(cls)

    def _table_exists(self, modelclass):
        table = modelclass.__table__
        params = ('table', table)
        sql = 'SELECT name FROM sqlite_master WHERE type=? and name=?'
        cursor = self._exec(sql, params)
        return cursor.fetchone() is not None

    def _create_table(self, modelclass):
        create = 'CREATE TABLE {table} ({columns})'

        table = modelclass.__table__
        cols = modelclass.__columns__
        fields = []
        fk_defs = []
        # column definition
        # name type default collation_sequence
        for col in cols:
            fields.append(col.definition)
            if col.fk:
                fk_defs.append(col.fk_definition)

        columns = ', '.join(fields + fk_defs)

        sql = create.format(table=table, columns=columns)
        self._exec(sql)

    def _connect(self):
        if not self.conn:
            self.conn = sqlite3.connect(self.path)
            log.info('Connected to db {!r}.'.format(self.path))

    def _exec(self, sql, *params):
        log.debug('Execute {!r}'.format(sql))
        log.debug('Params: {!r}'.format(params))
        self._connect()
        cursor = self.conn.cursor()
        cursor.execute(sql, *params)
        self.conn.commit()
        return cursor

    def store(self, instance):
        log.debug('Store {!r}'.format(instance))
        if instance.id:
            self._update(instance)
        else:
            self._insert(instance)

    def _insert(self, instance):
        insert = 'INSERT into {table} VALUES ({placeholders})'
        table = instance.__table__
        cols = instance.__columns__
        placeholders = ','.join('?' * len(cols))

        params = [col.get(instance) for col in cols]
        sql = insert.format(table=table,placeholders=placeholders)
        cursor = self._exec(sql, params)
        instance.id = cursor.lastrowid

        log.debug('Rowcount: {}'.format(cursor.rowcount))
        log.debug('Inserted row ID: {}'.format(cursor.lastrowid))

    def _update(self, instance):
        update = 'UPDATE {table} SET {placeholders} WHERE id=?'
        table = instance.__table__
        cols = instance.__columns__

        assignments = []
        params = []
        for col in cols:
            assignments.append('{c.name}=?'.format(c=col))
            params.append(col.get(instance))

        placeholders = ','.join(assignments)
        params.append(instance.id)

        sql = update.format(table=table, placeholders=placeholders)
        cursor = self._exec(sql, params)

        if cursor.rowcount == 0:
            raise NotFoundError

    def select(self, modelclass, **kwargs):
        cursor = self._do_select(modelclass, **kwargs)
        results = []
        row = cursor.fetchone()
        while row is not None:
            instance = self._map(modelclass, row)
            results.append(instance)
            row = cursor.fetchone()

        return results

    def select_one(self, modelclass, **kwargs):
        cursor = self._do_select(modelclass, **kwargs)
        row = cursor.fetchone()
        if not row:
            raise NotFoundError

        additional_row = cursor.fetchone()
        if additional_row:
            raise ValueError('Query returned more than one row')
        else:
            return self._map(modelclass, row)

    def _do_select(self, modelclass, **kwargs):
        select = 'SELECT {fields} from {table}'
        table = modelclass.__table__
        cols = modelclass.__columns__
        col_by_name = {col.name: col for col in cols}

        fields = ', '.join(col.name for col in cols)
        sql = select.format(table=table, fields=fields)

        if kwargs:
            predicates = []
            params = []
            for k, v in kwargs.items():
                predicates.append('{field}=?'.format(field=k))
                params.append(col_by_name[k].from_python(v))
            where = ' where {}'.format(' AND '.join(predicates))
        else:
            where = ''
            params = []

        return self._exec(sql+where, params)

    def _map(self, modelclass, row):
        instance = modelclass()
        cols = modelclass.__columns__
        for col, raw_value in zip(cols, row):
            col.set(instance, raw_value)
        return instance


class Game(object):

    __table__ = 'games'
    __columns__ = (
        Column('id', datatype='integer', primary=True),
        Column('appid', null=False, unique=True),
        Column('enabled', datatype='boolean', null=False),
        Column('name'),
        Column('threshold', datatype='real')
    )

    def __init__(self, **kwargs):
        self.id = None
        self.appid = kwargs.get('appid')
        self.enabled = kwargs.get('enabled', True)
        self.name = kwargs.get('name')
        self.threshold = kwargs.get('threshold')
        self.categories = []
        self.dlc = []
        self.genres = []
        self.packages = []  # ?
        self.pf_linux = False
        self.pf_windows = False
        self.pf_mac = False

    def __repr__(self):
        return '<Game appid={s.appid!r}>'.format(s=self)


class Measure(object):

    __table__ = 'measures'
    __columns__ = (
        Column('id', datatype='integer', primary=True),
        Column('gameid', datatype='integer', null=False, fk=(Game, 'id')),
        Column('price', datatype='real'),
        Column('baseprice', datatype='real'),
        Column('discount', datatype='real'),
        Column('currency'),
        Column('metacritic', datatype='real'),
        Column('datetaken', datatype='datetime'),
    )

    def __init__(self, **kwargs):
        self.id = None
        self.gameid = kwargs.get('gameid')
        self.price = kwargs.get('price')  # discounted price
        self.baseprice = kwargs.get('baseprice')
        self.discount = kwargs.get('discount')
        self.currency = kwargs.get('currency')
        self.metacritic = kwargs.get('metacritic')
        self.datetaken = kwargs.get('datetaken')

    def __repr__(self):
        return '<Measure gameid={s.gameid!r}>'.format(s=self)
