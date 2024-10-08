"""Create a neat dataframe, joining all datasets and converting some variables"""

from collections.abc import Callable

import pandas as pd
import sqlalchemy as sql
import sqlalchemy.orm as orm
from sqlalchemy.sql.expression import and_

from models import Personal, Speech, SpeechLink, TopicPrediction, Membership, ElectionCandidate, ParliamentSession
from config import config
from helpers import Task, sql_get, logged


# Personal x Membership --------------------------------------------------------
# => (identifier, parliament)

def grouped_any(df: pd.DataFrame, col: str, test: Callable, by: str | list[str], dummy_name: str):
    """Check if any value of `col` in the group defined satisfies `test` and
    creates a column `dummy_name` in the original dataframe"""
    grouped_df = pd.DataFrame(df.groupby(by)[col].apply(list))
    grouped_df[dummy_name] = [test(el) for el in grouped_df[col]]
    joined_df = df.join(grouped_df, on=by, how='left', rsuffix='_')
    return joined_df


def create_birth_year(df: pd.DataFrame) -> pd.DataFrame:
    """Create a birth year variable"""
    df['birth_year'] = [bd.year for bd in df['birth_day']]
    return df


def in_security_committee(memberships: list[str]):
    """Check if there is a security committee among the memberships"""
    in_sec = any(kw in m for kw in config['DATA']['COMMITTEE_KEYWORDS']
                 for m in memberships)
    return 1 if in_sec else 0


def create_security_committee_dummy(df: pd.DataFrame):
    """Create dummy variable whether MoP was part of a committee dealing with
    security topics"""
    df = grouped_any(df, 'committee', in_security_committee, [
                     'personal_id', 'parliament'], 'security_committee')
    return df


def is_security_profession(professions: list[str]):
    """Check if a security profession is among the list"""
    in_sec = any(
        kw in professions for kw in config['DATA']['PROFESSION_KEYWORDS'])
    return 1 if in_sec else 0


def create_security_profession_dummy(df: pd.DataFrame):
    """Create dummy variable indicating professions in a security field"""
    df['security_profession'] = [is_security_profession(el)
                                 for el in df['profession']]
    return df


def is_close(result: list[int]):
    """Check if an election (list of votes) was close"""
    threshold = config['DATA']['VOTE_SHARE_THRESHOLD']
    result.sort(reverse=True)
    try:
        return 1 if result[1] >= threshold * result[0] else 0
    except IndexError:
        return 0


def create_close_elec_dummy(df: pd.DataFrame) -> pd.DataFrame:
    """Create dummy variable for close elections"""
    df = grouped_any(df, 'votes', is_close, [
                     'election_id', 'constituency'], 'close_election')
    return df


def is_war_speech(speech_topic: int, war_topic: int):
    """Check if the speech topic is the war topic"""
    return 1 if speech_topic == war_topic else 0


def get_pers_memb_df(session: orm.Session):
    """Join Membership and Personal data and transform variables"""
    stmt = sql.Select(Membership.organization, Membership.parliament,
                      Personal.identifier, Personal.birth_day,
                      Personal.birth_place, Personal.profession,
                      Personal.military_experience).join(Personal, isouter=True)
    # several memberships per person (and parliament session) possible
    data = sql_get(stmt, session)
    columns = ['committee', 'parliament', 'personal_id', 'birth_day',
               'birth_place', 'profession', 'military_experience']
    df = pd.DataFrame(data, columns=columns).dropna()
    # type inference doesn't work here properly
    df = df.astype({'personal_id': int, 'parliament': int})
    df = create_birth_year(df).drop('birth_day', axis=1)
    df = create_security_committee_dummy(df).drop(
        ['committee', 'committee_'], axis=1)
    df = create_security_profession_dummy(df).drop('profession', axis=1)
    return df


# Election --------------------------------------------------------------------


def get_elec_df(session: orm.Session):
    """Obtain election data and create close election dummy"""
    stmt = sql.Select(ElectionCandidate.person_id, ElectionCandidate.election_id,
                      ElectionCandidate.parliament, ElectionCandidate.constituency,
                      ElectionCandidate.votes, ElectionCandidate.result)
    data = sql_get(stmt, session)
    columns = ['personal_id', 'election_id', 'parliament',
               'constituency', 'votes', 'result']
    df = pd.DataFrame(data, columns=columns).dropna().astype(
        {'personal_id': int})
    df = create_close_elec_dummy(df).drop('votes', axis=1)
    return df[df['result'] == 'Elected']

# Speech ----------------------------------------------------------------------


def get_speech_df(war_topic: int, session: orm.Session):
    """Query speech data and create war topic dummy"""
    date_condition = and_(ParliamentSession.start_date <= Speech.speech_date,
                          ParliamentSession.end_date >= Speech.speech_date)
    stmt = sql.Select(Speech.speaker_party, TopicPrediction.topic,
                      SpeechLink.identifier, ParliamentSession.parliament).join(
        TopicPrediction).join(
        SpeechLink,
        onclause=Speech.speaker_name == SpeechLink.name).join(
        Personal,
        onclause=SpeechLink.identifier == Personal.identifier,
        isouter=True).join(
        ParliamentSession,
        onclause=date_condition)
    columns = ['speaker_party', 'topic', 'personal_id', 'parliament']
    data = sql_get(stmt, session)
    df = pd.DataFrame(data, columns=columns)
    df['topic'] = [is_war_speech(topic, war_topic)
                   for topic in df['topic']]
    return df


@ logged
def get_all_data(war_topic: int, session: orm.Session) -> tuple[pd.DataFrame]:
    """Execute calls to obtain all datasets"""
    elec = get_elec_df(session)
    pers_memb = get_pers_memb_df(session)
    speech = get_speech_df(war_topic, session)
    return elec, pers_memb, speech


# Join  -----------------------------------------------------------------------

@ logged
def create_df(items: tuple[pd.DataFrame]):
    """Join datasets"""
    elec, pers_memb, speech = items
    on_cols = ['personal_id', 'parliament']
    elec = elec[elec['result'] == 'Elected'].dropna().set_index(on_cols)
    elec_pers_memb = pers_memb.join(
        elec, on=on_cols, how='inner')
    df = speech.join(elec_pers_memb.set_index(
        on_cols), on=on_cols, how='inner')
    return df


DatasetTask = Task(get_all_data, create_df, None)


# Alternative -- 1 single database query ---------------------------------------


# m = orm.aliased(Membership)
# p = orm.aliased(Personal)
# e = orm.aliased(ElectionCandidate)
# s = orm.aliased(Speech)
# ps = orm.aliased(ParliamentSession)
# tp = orm.aliased(TopicPrediction)
# sl = orm.aliased(SpeechLink)

# date_condition = and_(ps.start_date <= s.speech_date,
#                       ps.end_date >= s.speech_date)

# subq = sql.Select(s.speaker_party, tp.topic, sl.identifier, ps.parliament).join(
#     tp).join(sl, onclause=s.speaker_name == sl.name).join(
#         ps, onclause=date_condition).subquery()

# # person x parliament conditions
# pp_condition1 = and_((m.parliament == e.parliament),
#                      (m.identifier == e.person_id))

# pp_condition2 = and_((subq.c.parliament == m.parliament),
#                      (subq.c.identifier == p.identifier))

# stmt = sql.Select(e.election_id, m.parliament, p.identifier, m.organization,
#                   p.birth_day, p.profession, p.military_experience,
#                   e.constituency, e.votes, e.result, s.speaker_party,
#                   tp.topic).join(
#     # keep all election candidates even if they were never in the parliament
#     # => evaluation of elections
#                       m, onclause=pp_condition1, full=True).join(p).join(
#     # keep all election x personal x membership records but discard any
#     # non-identifiable speeches
#                           subq, onclause=pp_condition2, isouter=True)

# data = sql_get(stmt, session)

# columns = ['election_id', 'parliament', 'person_id', 'organization',
#            'birth_day', 'profession', 'military_experience', 'constituency',
#            'votes', 'result', 'party', 'topic']

# df = pd.DataFrame(data, columns=columns)
