"""Download speech data"""

from io import StringIO
import csv
from sqlite3 import IntegrityError

from lxml import etree
import httpx
import sqlalchemy as sql
from sqlalchemy.orm import Session

from helpers import Task, logged
from models import Speech
from config import config


parser = etree.HTMLParser()


@logged
def get_speech_links() -> list:
    """Obtain links to all hainsards from the timeline"""
    timeline = httpx.get(config['DATA']['SPEECH_URL'], timeout=30)
    tree = etree.fromstring(timeline.text, parser)
    decades_xpath = [
        '//*[@id="main"]/div[2]/div[1]/ul/li[4]/div[3]/ul',
        '//*[@id="main"]/div[2]/div[1]/ul/li[5]/div[3]/ul',
    ]
    links = []
    for decade in decades_xpath:
        d_list = tree.xpath(decade)
        for year in d_list[0]:
            for month in year[2]:
                for day in month[2]:
                    links.append(day[0].get('href'))
    return links


@logged
def speech_worker(item: str, session: Session) -> None:
    """`worker` downloads speech data given the (sub)paths"""
    resp = httpx.get(config['DATA']['SPEECH_URL'] + item + "exportcsv/")
    resp.raise_for_status()
    # The following might be unnecessary as httpx logs for itself
    speech_data = resp.text
    stream = StringIO(speech_data)
    # csv header is not relevant to us
    stream.readline()
    reader = csv.reader(stream)
    for row in reader:
        try:
            # only one instance per iteration
            next(Speech.create(row, item)).handle_missing(
                row).clean().save(session=session)
        except sql.exc.IntegrityError:
            session.rollback()
            continue
        except IntegrityError:
            session.rollback()
            continue
    stream.close()


SpeechTask = Task(get_speech_links, speech_worker, Speech)
