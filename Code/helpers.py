"""Useful helper functions and a Task tuple"""

import logging
import re
from collections import namedtuple
from collections.abc import Callable
from datetime import date
from typing import Generator


import sqlalchemy as sql
import sqlalchemy.orm as orm

from config import config


# Logging ---------------------------------------------------------------------


def logged(func: Callable) -> Callable:
    """logged() adds separate Debugger to decorated functions"""
    def foo(*args, **kwargs):
        id = args[0] if len(args) > 0 else ''
        func.logger = logging.getLogger(func.__qualname__)
        func.logger.info('Started %s', id)
        result = func(*args, **kwargs)
        func.logger.info('Finished %s', id)
        return result
    return foo


# Setup -----------------------------------------------------------------------

Task = namedtuple("Task", ["setup", "run", "models"])


def sql_get(stmt: sql.Select, session: orm.Session):
    """Execute `stmt` using `session`"""
    return session.execute(stmt).all()


# ORM Base Class --------------------------------------------------------------

class Base(orm.DeclarativeBase):
    """SQLAlchemy base class for models"""

    keys: dict[str, str | int] = {}
    identifier: int = -1

    def __repr__(self):
        pass

    @staticmethod
    def get_info(key, data):
        """`get_info` extracts information from single data entry"""

    @classmethod
    def create(cls, data: dict, request: str) -> Generator["Base", None, None]:
        """`create` reads the information from the response using the key paths
        provided by the paths attribute and creates table instances"""
        # The following line is used for debugging but also to introduce the
        # identifier for Experience, Membership and Election!
        cls.request = request
        iterators = {}
        iterators = {field.lower(): cls.get_info(cls.keys[field], data)
                     for field in cls.keys}
        while True:
            try:
                entries = {field: next(iterators[field])
                           for field in iterators}
                yield cls(**entries)
            except StopIteration:
                break

    def clean(self):
        """`clean` and reformat the received data"""
        return self

    def save(self, session: orm.Session) -> None:
        """`save` saves the created instances to the database."""
        try:
            session.add(self)
            session.commit()
        # OperationalError is more specific than DBAPIError
        except sql.exc.OperationalError as err:
            Base.save.logger.error(
                f"Problem ({err}): {self.__tablename__}, {self.identifier}"
            )
        except sql.exc.DBAPIError as err:
            Base.save.logger.error(
                f"Problem ({err}): {self.__tablename__}, {self.identifier}"
            )
            session.rollback()


# Cleaning --------------------------------------------------------------------

# Not all of the following correspondences could be placed in a YAML file

config["REPLACE"] = {
    "\s+": " ",
    r"\.": "",
    r"\-": "",
    r"\*": "",
    r":": "",
    r",": "",
    r"\'": "",
    r"\(": "",
    r"\)": "",
    "the hon": "",
    "an hon member": "",
    "some hon members": "",
    "hon": "",
    "right": "",
    "righi": "",
    "major": "",
    "mr": "",
    "air": ""
}


def create_date(time_iso: str) -> date | None:
    """create_date creates Date objects from the ISO-like string"""
    try:
        d = time_iso.split("T")[0]
        return date.fromisoformat(d)
    except ValueError:
        return None


def repair_name(name: str) -> str:
    """repair_name handles problems resulting from Latin-1 encoding"""
    ltr_repl = config['TRANSLATIONS']['LATIN1-FRENCH']
    for right, false in ltr_repl.items():
        name = re.sub(false, right, name)
    return name


def clean_name(name: str) -> str:
    """clean_name repairs the encoding, normalizes and splits the names"""
    if not name:
        return None
    name = repair_name(name).lower()
    for old, new in config['REPLACE'].items():
        name = re.sub(old, new, name)
    # in () there is often information on the constituency that we cannot use here
    pattern1 = re.compile(r"\([^\)]*\)")
    # after @ the position follows
    pattern2 = re.compile(r"@.*$")
    name = pattern1.sub("", name)
    name = pattern2.sub("", name)
    for french, ascii in config['TRANSLATIONS']['ASCII-FRENCH'].items():
        name = re.sub(french, ascii, name)
    return name.strip()
