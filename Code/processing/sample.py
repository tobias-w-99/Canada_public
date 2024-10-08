"""Create a random sample of speeches for cluster training"""

import random

import sqlalchemy as sql
import sqlalchemy.orm as orm
from sqlalchemy.sql.expression import func


from models import Speech, Sample
from helpers import Task, sql_get, logged
from config import config


@logged
def get_speeches(session) -> list[int]:
    """`load_data` loads the speeches (length >= minimal length, 
    see config). It returns a list of speech identifiers"""
    length_condition = func.length(
        Speech.speech_text) >= config['SPEECH_CRITERIA']['LENGTH']
    stmt = sql.select(Speech.speech_id).where(length_condition)
    result = sql_get(stmt, session)
    return [r[0] for r in result]


@logged
def create_sample(items: list[int], session: orm.Session) -> list:
    """Create a random sample, stored as Sample records"""
    size = round(len(items) * config['SPEECH_CRITERIA']['TRAIN_SIZE'])
    random.seed(1)
    train_set = random.sample(items, size)
    for el in items:
        instance = Sample(speech_id=el, in_training=el in train_set)
        session.add(instance)
    session.commit()


SampleTask = Task(get_speeches, create_sample, Sample)
