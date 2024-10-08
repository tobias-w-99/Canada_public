"""Combining the dataset of speeches with the data on members of parliament
through the name of the speaker"""

from collections import namedtuple
from collections.abc import Sequence
from typing import Iterable

from jaro import jaro_winkler_metric as jw
import sqlalchemy as sql
from sqlalchemy.orm import Session

from models import Speech, Personal, SpeechLink
from helpers import Task, sql_get, logged


# SpeechLinkTask----------------------------------------------------------------

# STEP 1: close to perfect matches (max Jaro-Winkler > 0.97)
# STEP 2: last name or first and last name matches (*single* close to perfect match)
# ------------------------  restriction of group -------------------------------
# -> This is currently not part of the matching procedure
# STEP 3: unique close to perfect match of last name or first and last name
# among the set of parliamentarians for which we have an election record for the
# corresponding parliament

# Named tuples => query results  -----------------------------------------------

Parl = namedtuple('Parl', [
                  'name', 'first_name', 'last_name', 'identifier'])

Match = namedtuple('Match', ['name', 'identifier', 'speaker', 'score'])


# Helper functions -------------------------------------------------------------


def join_names(entry: Sequence) -> Parl:
    """Join first and last names"""
    return ' '.join(entry[:2])


def find_highest_match(speaker: str, parl_set: list[Parl]) -> Match:
    """Find parliamemtarian that best matches the speaker"""
    p_max = max(parl_set, key=lambda x: jw(x.name, speaker))
    return Match(p_max.name, p_max.identifier, speaker, jw(p_max.name, speaker))


def single(i: Iterable):
    """Checks if i is a singleton"""
    return len(i) == 1


def mean_jw(first: str, last: str, p: Parl):
    """Obtain average of scores of first name and last name (excluding second
    names)"""
    p_first = p.first_name.split(' ')[0]
    return (jw(first, p_first) + jw(last, p.last_name)) / 2

# Queries ----------------------------------------------------------------------


@logged
def get_speech_personal(session: Session) -> tuple[list[Parl], list[Speech]]:
    """Query lists of parliamentarians and speakers"""
    p_stmt = sql.select(Personal.first_name,
                        Personal.last_name, Personal.identifier)
    parls = sql_get(p_stmt, session)
    parliamentarians: list[Parl] = [Parl(join_names(p), *p) for p in parls]
    s_stmt = sql.select(Speech.speaker_name)
    speakers: set[str] = set(r[0] for r in sql_get(s_stmt, session))
    return (parliamentarians, speakers)


# Matching functions -----------------------------------------------------------


def match_name(name: str, p_set: list[Parl], how: str):
    """Create link instances with best matches of either first and last name
    (ho='first_last) or last name only (how='last')"""
    if how == 'first_last':
        # it is assumed that name in this case is only first and last name
        first, last = name.split(' ')
        candidates = [Match(p.name, p.identifier, name, mean_jw(first, last, p))
                      for p in p_set]
    elif how == 'last':
        candidates = [Match(p.last_name, p.identifier, name,
                            jw(name, p.last_name)) for p in p_set]
    else:
        raise ValueError('`how` argument must not be `None`')
    close_matches = [c for c in candidates if c.score >= 0.97]
    perfect_matches = [c for c in close_matches if c.score == 1]
    if single(perfect_matches):
        instance = SpeechLink(
            identifier=perfect_matches[0].identifier, name=perfect_matches[0].speaker)
    elif single(close_matches):
        instance = SpeechLink(
            identifier=close_matches[0].identifier, name=close_matches[0].speaker)
    else:
        instance = None
    return instance


def create_link(speaker: str, p_set: list[Parl]) -> SpeechLink:
    """Rules for link creation: single best match if maximal score is above the
    threshold, last name if length of speaker name is 1, first and last name if
    it is two"""
    best_match: Match = find_highest_match(speaker, p_set)
    speaker_length = len(speaker.split(' '))
    if best_match.score >= 0.97:
        instance = SpeechLink(identifier=best_match.identifier,
                              name=best_match.name)
    elif speaker_length == 1:
        # only last_name; if list of MoP is not comprehensive, we migth use non-unique values
        instance = match_name(speaker, p_set, 'last')
    elif speaker_length == 2:
        # middle name is missing
        instance = match_name(speaker, p_set, 'first_last')
    else:
        instance = None
    return instance


# ------------------------------------------------------------------------------

@logged
def speech_link_worker(items: tuple[set[str], list[Parl]], session: Session) -> bool:
    """Try to create a link to a parliamentarian for each speaker"""
    parliamentarians, speakers = items
    for s in speakers:
        instance = create_link(s, parliamentarians)
        if instance:
            session.add(instance)
            session.commit()


SpeechLinkTask = Task(get_speech_personal, speech_link_worker, SpeechLink)


# -----------------------------------------------------------------------------


# def get_parliament(entry: Parl):
#     return -1 if entry.parliament is None else entry.parliament


# def create_grouped_person(parliamentarians: list[Parl]) -> list[list[Parl]]:
#     parliamentarians.sort(key=get_parliament)
#     grouped_parliamentarians = [
#         g for k, g in groupby(parliamentarians, get_parliament)]
#     return grouped_parliamentarians


# def query_grouped_speeches(session: Session) -> list[list[Speech]]:
#     stmt = sql.select(ParliamentSession)
#     parliaments: list[ParliamentSession] = [s[0]
#                                             for s in session.execute(stmt).all()]
#     grouped_speeches: list[Speech] = []
#     for p in parliaments:
#         query = sql.select(Speech).where(sql.between(
#             Speech.speech_date, p.start_date, p.end_date))
#         result = [r[0] for r in session.execute(query).all()]
#         grouped_speeches.append(result)
#     return grouped_speeches


# def get_grouped_speech_personal(parliamentarians, session: Session) -> tuple[list]:
#     grouped_parliamentarians = create_grouped_person(parliamentarians)
#     grouped_speeches = query_grouped_speeches(session)
#     grouped_speakers = [set(s.speaker_name for s in g)
#                         for g in grouped_speeches]
#     return (grouped_parliamentarians, grouped_speakers)


# GroupedSpeechTask = Task(get_grouped_speech_personal,
#                          speech_link_worker, SpeechLink)
