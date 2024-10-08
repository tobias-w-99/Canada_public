"""Get date information for parliament session"""

import httpx
from sqlalchemy.orm import Session

from models import ParliamentSession
from helpers import Task, logged
from config import config

# SessionTask ------------------------------------------------------------------


@logged
def get_session_data(session: Session):
    """Download parliamentary sessions data from the library of the Canadian parliament"""
    # session argument is just for compatibility
    data = httpx.get(config['DATA']['SESSION_URL']).json()
    return data


@logged
def session_worker(s_list: list[dict], session: Session):
    """Obtain start and end dates of each session and save it as a ParliamentSession"""
    # data in JSON format
    for s in s_list:
        # only one instance per iteration
        el = next(ParliamentSession.create(s, ''))
        el.handle_missing().clean().save(session=session)


SessionTask = Task(get_session_data, session_worker, ParliamentSession)
