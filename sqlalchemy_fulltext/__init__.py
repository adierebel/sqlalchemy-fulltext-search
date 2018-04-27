# -*- coding: utf-8 -*-s

from __future__ import absolute_import

import re

from sqlalchemy import event, literal, Index
from sqlalchemy.schema import DDL
from sqlalchemy.orm.mapper import Mapper
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ClauseElement
from . import modes as FullTextMode


MYSQL = "mysql"
MYSQL_BUILD_INDEX_QUERY = u"""ALTER TABLE {0.__tablename__} ADD FULLTEXT ({1})"""
MYSQL_MATCH_AGAINST = u"""
                      MATCH ({0})
                      AGAINST ({1} {2})
                      """

def escape_quote(string):
    return re.sub(r"[\"\']+", "", string)

class FullTextSearch(ClauseElement):
    """
    Search FullText
    :param against: the search query
    :param table: the table needs to be query

    FullText support with in query, i.e.
        >>> from sqlalchemy_fulltext import FullTextSearch
        >>> session.query(Foo).filter(FullTextSearch('Spam', Foo))
    """
    def __init__(self, against, model, mode=FullTextMode.DEFAULT):
        self.model = model
        self.against = literal(against)
        self.mode = mode


def get_table_name(element):
    if hasattr(element.model, "__table__"):
        return "`" + element.model.__table__.fullname + "`."
    return ""


@compiles(FullTextSearch, MYSQL)
def __mysql_fulltext_search(element, compiler, **kw):
    assert issubclass(element.model, FullText), "{0} not FullTextable".format(element.model)
    return MYSQL_MATCH_AGAINST.format(
        ", ".join([get_table_name(element) + column for column in element.model.__fulltext_columns__]),
        compiler.process(element.against),
        element.mode)


class FullText(object):
    """
    FullText Minxin object for SQLAlchemy
    
        >>> from sqlalchemy_fulltext import FullText
        >>> class Foo(FullText, Base):
        >>>     __fulltext_columns__ = ('spam', 'ham')
        >>>     ...

    fulltext search spam and ham now
    """
    
    __fulltext_columns__ = tuple()

    @classmethod
    def build_fulltext(cls, table):
        """
        build up fulltext index after table is created
        """
        if FullText not in cls.__bases__:
            return
        if not cls.__fulltext_after_create__:
            return
        assert cls.__fulltext_columns__, "Model:{0.__name__} No FullText columns defined".format(cls)

        event.listen(table,
                     'after_create',
                     DDL(MYSQL_BUILD_INDEX_QUERY.format(cls,
                         ", ".join((escape_quote(c)
                                    for c in cls.__fulltext_columns__)))
                         )
                     )
    """
    TODO: black magic in the future
    @classmethod
    @declared_attr
    def __contains__(*arg):
        return True
    """

    __fulltext_after_create__ = True


class FullTextForMigration(FullText):
    __fulltext_after_create__ = False

    @classmethod
    def index_fulltext(cls):
        """
        call like Index('idx_<__tablename__>_fulltext', *__fulltext_columns__, mysql_prefix='FULLTEXT')
        """
        assert cls.__tablename__, "Model:{0.__name__} No table name defined".format(cls)
        assert cls.__fulltext_columns__, "Model:{0.__name__} No FullText columns defined".format(cls)
        Index('idx_%s_fulltext' % cls.__tablename__,
                *(getattr(cls, c) for c in cls.__fulltext_columns__),
                  mysql_prefix='FULLTEXT')


def __build_fulltext_index(mapper, class_):    
    if issubclass(class_, FullText):
        class_.build_fulltext(mapper.mapped_table)


event.listen(Mapper, 'instrument_class', __build_fulltext_index)
