"""Download of election data"""

from lxml import etree
import httpx
from sqlalchemy.orm import Session

from helpers import Task, logged
from models import ElectionCandidate
from config import config


parser = etree.XMLPullParser(tag="ElectionCandidateForWeb")


@logged
def election_worker(item=None, session: Session) -> None:
    """`worker` handles the entire download process"""
    # item is just there for compatibility
    with httpx.stream("GET", config['DATA']['ELECTION_URL'], timeout=None) as stream:
        for text in stream.iter_text():
            parser.feed(text)
            for event, element in parser.read_events():
                election_date = element.find("ElectionDate").text
                if election_date < config['TIME_RANGE']['T1'] and election_date > config['TIME_RANGE']['T0']:
                    election_id = element.find("ElectionId").text
                    # There is only one instance created!
                    ec: ElectionCandidate = next(ElectionCandidate.create(
                        element, election_id))
                    ec.clean().save(session=session)
        parser.close()


ElectionTask = Task(lambda: [1], election_worker, ElectionCandidate)
