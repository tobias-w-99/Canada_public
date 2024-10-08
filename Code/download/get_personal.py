"""Get personal information on members of parliament"""

import httpx
from sqlalchemy.orm import Session

from helpers import logged, Task
from models import Personal, Experience, Election, Membership
from config import config

tables = [Personal,  Election, Membership, Experience]


@logged
def get_ids() -> list:
    """get_ids() reads the list of IDs from file"""
    # alternatively use the list provided by the following link
    # https://lop.parl.ca/ParlinfoWebAPI/Person/SearchAndRefine?refiners=4-29%2C4-28%2C4-27%2C4-26%2C&_=1717999924321
    # => MoP in parliaments 17-20 (1930-09-08 to 1949-04-30)
    with open(config['FILES']['ID_FILE'], encoding="utf-8", mode="r") as file_obj:
        contents = [el.replace("\n", "") for el in file_obj.readlines()]
    return contents


def get(identifier: str) -> dict:
    """get() requests the web profile from the API using the parliament
    identification key"""
    request_url = config['DATA']['PERSONAL_URL'] + identifier
    resp = httpx.get(request_url, timeout=10)
    resp.raise_for_status()
    return resp.json()


@logged
def personal_worker(item: str, session: Session) -> None:
    """Each worker executes the logic defined in the other modules. Each of
    them can be a separate thread"""
    profile = get(item)
    for model in tables:
        for instance in model.create(profile, item):
            instance.clean().save(session=session)


PersonalTask = Task(get_ids, personal_worker, tables)
