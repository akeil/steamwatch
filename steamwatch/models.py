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
        log.debug('Inserted row {i} into {t!r}'.format(i=instance.id, t=table))

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

        log.debug('Updated row {i} in {t!r}'.format(i=instance.id, t=table))

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


# select FIELDS from TABLE [where PREDICATES] [order by FIELDS asc|desc]
# update TABLE set ASSIGNMENTS [where PREDICATES]
# insert into TABLE fields VALUES values
# delete from TABLE where PREDICATES
class Statement:

    def __init__(self, db, table):
        self._db = db
        self._table = table
        self._where_clause = None
        self._predicates = []

    def _where(self, field):
        self._where_clause = _Where(self)
        predicate = _Predicate(self._where_clause, field)
        self._where_clause._predicates.append(predicate)
        return predicate

    def _build_where(self):
        if self._where_clause:
            return self._where_clause._build_fragment()
        else:
            return ''

        if self._predicates:
            fragment = 'WHERE '
            for predicate in self._predicates:
                fragment += predicate._build_predicate()
        else:
            fragment = ''

        return fragment

    def _where_params(self):
        if self._where_clause:
            return self._where_clause._params()
        else:
            return []

    @property
    def sql(self):
        return self._build()

    @property
    def params(self):
        return self._params()

    def _exec(self):
        return self._db._exec(self.sql, self.params)


class _Where:

    def __init__(self, statement,):
        self._statement = statement
        self._predicates = []

    def or_is(self, field):
        return self._op('OR', field)

    def or_not(self, field):
        return self._op('OR NOT', field)

    def and_is(self, field):
        return self._op('AND', field)

    def and_not(self, field):
        return self._op('AND NOT', field)

    def _op(self, token, field):
        self._predicates.append(_Token(token))
        predicate = _Predicate(self, field)
        self._predicates.append(predicate)
        return predicate

    def _build_fragment(self):
        fragment = 'WHERE '
        fragment += ' '.join([p._build_predicate() for p in self._predicates])
        return fragment

    def _params(self):
        return [p.predicate for p in self._predicates if hasattr(p, 'predicate')]

    def __getattr__(self, name):
        print(name)
        if name in ('or_is', 'or_not', 'and_is', 'and_not'):
            context = self
        else:
            context = self._statement
        return getattr(context, name)


class _Predicate:

    def __init__(self, parent, field):
        self._parent = parent
        self._field = field
        self._operator = None
        self.predicate = None

    def equals(self, predicate):
        self._operator = '='
        self.predicate = predicate
        return self._parent

    def equals_not(self, predicate):
        self._operator = '!='
        self.predicate = predicate
        return self._parent

    def _build_predicate(self):
        return self._field + self._operator + '?'


class _Token:

    def __init__(self, token):
        self._token = token

    def _build_predicate(self):
        return self._token


class Select(Statement):

    def __init__(self, db, model):
        super(Select, self).__init__(db, model.__table__)
        self._model = model
        self._predicates = []
        self._order = []
        self._limit = None

    def where(self, field):
        return self._where(field)

    def order_by(self, field, desc=False):
        self._order.append((field, 'DESC' if desc else 'ASC'))
        return self

    def limit(self, limit):
        self._limit = limit
        return self

    def many(self):
        '''Execute the select statement and map multiple model instances.'''
        cursor = self._exec()
        row = cursor.fetchone()
        results = []
        while row is not None:
            instance = self._model.map_row(row)
            results.append(instance)
            row = cursor.fetchone()

        return results

    def one(self):
        '''Execute the SELECT statement and require that exactly one row
        is returned.'''
        cursor = self._exec()
        first = cursor.fetchone()
        if not first:
            raise NotFoundError
        instance = self._model.map_row(first)
        additional_row = cursor.fetchone()
        if additional_row:
            raise ValueError('Got multiple rows')
        return instance

    def _build_fields(self):
        return ','.join([c.name for c in self._model.__columns__])

    def _build_order(self):
        if self._order:
            fragment = 'ORDER BY '
            fragment += ', '.join([' '.join(o) for o in self._order])
            return fragment

    def _build_limit(self):
        if self._limit:
            return 'LIMIT ' + str(self._limit)

    def _build(self):
        parts = [
            'SELECT',
            self._build_fields(),
            'FROM',
            self._table,
            self._build_where(),
            self._build_order(),
            self._build_limit()
        ]
        return ' '.join([p for p in parts if p])

    def _params(self):
        params = []
        params += self._where_params()
        return params


class Update(Statement):

    def __init__(self, db, instance):
        super(Update, self).__init__(db, instance.__table__)
        self._instance = instance

    def _build_assignments(self):
        return ','.join([
            '{c.name}=?'.format(c=c)
            for c in self._instance.__columns__
        ])

    def _params(self):
        params = [c.get(self._instance) for c in self._instance.__columns__]
        params.append(self._instance.id)
        return params

    def _build(self):
        sql = 'UPDATE '
        sql += self._table
        sql += ' SET '
        sql += self._build_assignments()
        sql += ' WHERE id=?'
        return sql

    def execute(self):
        cursor = self._exec()


class Insert(Statement):

    def __init__(self, db, instance):
        super(Insert, self).__init__(db, instance.__table__)
        self._instance = instance

    def _build(self):
        values = '('
        values += ','.join(['?' for c in self._instance.__columns__])
        values += ')'
        return 'INSERT INTO ' + self._table + ' VALUES ' + values

    def _params(self):
        return [c.get(self._instance) for c in self._instance.__columns__]

    def execute(self):
        cursor = self._exec()
        self._instance.id = cursor.lastrowid


class Delete:

    def __init__(self, db, instance):
        super(Insert, self).__init__(db, instance.__table__)
        self._instance = instance

    def _params(self):
        return [self._instance.id]

    def _build(self):
        return 'DELETE FROM ' + self._table + ' WHERE id=?'


class _Model:

    @classmethod
    def select(cls, db):
        return Select(db, cls)

    @classmethod
    def get(cls, db, id):
        return Select(db, cls).where('id').equals(id).one()

    def save(self, db):
        if getattr(self, 'id', None):
            self._update(db)
        else:
            self._insert(db)

    def _insert(self, db):
        Insert(db, self).execute()

    def _update(self, db):
        Update(db, self).execute()

    def delete(self, db):
        Delete(db, self).execute()

    @classmethod
    def map_row(cls, row):
        instance = cls()
        for col, raw_value in zip(cls.__columns__, row):
            col.set(instance, raw_value)
        return instance


class Game(_Model):

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


class Measure(_Model):

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
