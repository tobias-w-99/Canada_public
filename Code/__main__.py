#!/usr/bin/python3
# ~/Code/__main__.py

"""
main() runs a program that downloads the PersonWebProfile from the API
as JSON data for all IDs in Link_ID.csv, after that it processes the data to
create links and a training set for speech clustering. Grouping speeches
according to the trained model, it runs a regression to look at variables
correlated to the likelihood that a member of parliament put higher emphasis on
WWII, exhibited through the topic of his or her speeches.
"""

import logging
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from collections.abc import Iterable


import sqlalchemy as sql
import sqlalchemy.orm as orm


from download.get_speech import SpeechTask
from download.get_personal import PersonalTask
from download.get_election import ElectionTask
from download.get_session import SessionTask
from processing.link_speech import SpeechLinkTask
from processing.sample import SampleTask
from analysis.speech_clustering import ClusteringTask
from analysis.regression_analysis import RegressionTask

from config import config
from helpers import Base, logged


# Setup -----------------------------------------------------------------------

logging.basicConfig(
    filename=config['FILES']['LOG'] + "download_files_async.log",
    encoding="utf-8",
    level=logging.INFO,
    filemode="w",
    format="%(levelname)s %(asctime)s %(name)s %(message)s",
)

sql_logger = logging.getLogger("sqlalchemy")
sql_logger.setLevel(logging.WARNING)
# we have a lot of database transactions which each triggers several logging
# messages; for debugging purposes it is sensible to choose `INFO` instead

PreparationTasks = [PersonalTask, ElectionTask, SpeechTask,
                    SessionTask, SampleTask, SpeechLinkTask,  ClusteringTask]

DownloadTasks = [PersonalTask, ElectionTask, SpeechTask]
# Download differ in two respects: they can be run simultaneously (using
# `work_parallel`) and they download data from the web, whereas later Tasks use
# data from the built database (and therefore need a database session)

# Program ---------------------------------------------------------------------


@ logged
def setup_db(base_class: orm.DeclarativeBase) -> orm.Session:
    """setup() sets up the database connection."""
    engine = sql.create_engine(config['DATABASE_URI'])
    session_factory = orm.sessionmaker(bind=engine)
    Session = orm.scoped_session(session_factory)
    base_class.metadata.create_all(engine)
    return Session


@ logged
def work_parallel(worker: Callable, session: orm.Session, items: Iterable) -> None:
    """work_parallel() creates up to n threads which fetch the profiles and
    handle the obtained data"""
    with ThreadPoolExecutor(max_workers=config['MAX_CONCUR_REQ']) as pool:
        worker = partial(worker, session=session)
        pool.map(worker, items)


def main():
    Session = setup_db(Base)
    for Task in PreparationTasks:
        if Task in DownloadTasks:
            items = Task.setup()
            work_parallel(Task.run, Session, items)
        else:
            items = Task.setup(Session)
            Task.run(items, Session)
    i = input(
        f'Please checkout the file {config["FILES"]["CLUSTER_WORDS"]} and enter the index of the cluster related to war: ')
    logging.info('Received input %s', i)
    df = RegressionTask.setup(int(i), Session)
    RegressionTask.run(df)


if __name__ == "__main__":
    main()
