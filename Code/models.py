# ~/Code/models.py

"""Database models"""


from datetime import date

from sqlalchemy.orm import Mapped, mapped_column
import sqlalchemy as sql
import spacy


from helpers import clean_name, create_date, Base, logged
from config import config


class Personal(Base):
    """Personal information on the member of parliament"""

    __tablename__ = "personal_information"
    keys = config['DATA']['KEYS']['PERS']

    identifier: Mapped[int] = mapped_column(sql.Integer, primary_key=True)
    birth_day: Mapped[date] = mapped_column(sql.Date, nullable=True)
    birth_place: Mapped[str] = mapped_column(sql.String, nullable=True)
    profession: Mapped[str] = mapped_column(sql.String, nullable=True)
    first_name: Mapped[str] = mapped_column(sql.String)
    last_name: Mapped[str] = mapped_column(sql.String)
    military_experience: Mapped[bool] = mapped_column(sql.Boolean)

    def __repr__(self):
        return f"Personal(identifier = {self.identifier!r},  ...)"

    @staticmethod
    def get_info(key, data):
        if key == '':
            info = data['MilitaryExperience']
            if info is None:
                yield False
            else:
                yield True
        else:
            info = data['Person'][key]
            yield info

    def clean(self):
        self.birth_day = create_date(self.birth_day)
        self.first_name = clean_name(self.first_name)
        self.last_name = clean_name(self.last_name)
        return self


class Membership(Base):
    """Information on a committe membership of the member of parliament"""

    __tablename__ = "committee_membership"

    keys = config['DATA']['KEYS']["MEMB"]

    membership_id: Mapped[int] = mapped_column(
        sql.Integer, primary_key=True, autoincrement=True
    )
    session: Mapped[int] = mapped_column(sql.Integer, nullable=True)
    composition: Mapped[str] = mapped_column(sql.String, nullable=True)
    type: Mapped[str] = mapped_column(sql.String)
    role: Mapped[str] = mapped_column(sql.String, nullable=True)
    organization: Mapped[str] = mapped_column(sql.String, nullable=True)
    party: Mapped[str] = mapped_column(sql.String, nullable=True)
    parliament: Mapped[str] = mapped_column(sql.String)
    identifier: Mapped[int] = mapped_column(
        sql.Integer, sql.ForeignKey("personal_information.identifier")
    )

    def __repr__(self):
        return f"Membership(membership_id = {self.membership_id!r}, ...)"

    @staticmethod
    def get_info(key, data):
        for el in data['CommitteeMembership']:
            yield el[key]

    def clean(self):
        # We abuse this method to introduce the identifier for each instance
        self.identifier = self.request
        return self


class Election(Base):
    """Election (result) of a member of parliament"""

    __tablename__ = "election_results"

    keys = config['DATA']['KEYS']["ELEC"]

    election_id: Mapped[int] = mapped_column(
        sql.Integer, primary_key=True, autoincrement=True
    )
    parliament: Mapped[int] = mapped_column(sql.Integer)
    election_date: Mapped[date] = mapped_column(sql.Date)
    election_type: Mapped[str] = mapped_column(sql.String, nullable=True)
    constituency: Mapped[str] = mapped_column(sql.String)
    party: Mapped[str] = mapped_column(sql.String, nullable=True)
    result: Mapped[str] = mapped_column(sql.String, nullable=True)
    votes: Mapped[str] = mapped_column(sql.String)
    identifier: Mapped[int] = mapped_column(
        sql.Integer, sql.ForeignKey("personal_information.identifier")
    )

    def __repr__(self):
        return f"Election(election_id = {self.election_id!r}, ...)"

    @staticmethod
    def get_info(key, data):
        for el in data['Person']['ElectionCandidates']:
            yield el[key]

    def clean(self):
        # We abuse this method to introduce the identifier for each instance
        self.identifier = self.request
        self.election_date = create_date(
            self.election_date) if self.election_date else create_date("2050-01-01")
        return self


class Experience(Base):
    """Position held by a member of parliament in federal politics"""

    __tablename__ = "federal_experience"
    keys = config['DATA']['KEYS']["EXP"]

    experience_id: Mapped[int] = mapped_column(
        sql.Integer, primary_key=True, autoincrement=True
    )
    section: Mapped[str] = mapped_column(sql.String)
    role: Mapped[str] = mapped_column(sql.String, nullable=True)
    organization: Mapped[str] = mapped_column(sql.String, nullable=True)
    party: Mapped[str] = mapped_column(sql.String)
    start_date: Mapped[date] = mapped_column(sql.Date)
    end_date: Mapped[date] = mapped_column(sql.Date)
    identifier: Mapped[int] = mapped_column(
        sql.Integer, sql.ForeignKey("personal_information.identifier")
    )

    def __repr__(self):
        return f"Experience(experience_id: {self.experience_id!r},  ...)"

    @staticmethod
    def get_info(key, data):
        for el in data['FederalExperienceList']:
            yield el[key]

    def clean(self):
        # We abuse this method to introduce the identifier for each instance
        self.identifier = self.request
        for attr, path in self.keys.items():
            info = getattr(self, attr.lower())
            if "Date" in path:
                if info:
                    info = create_date(info)
                else:
                    info = create_date("2050-01-01")
            setattr(self, attr.lower(), info)
        return self


class Speech(Base):
    """Speech data"""

    __tablename__ = "speech"
    keys = config['DATA']['KEYS']["SPEECH"]
    nlp = spacy.load('en_core_web_sm')

    speech_id: Mapped[int] = mapped_column(sql.Integer, primary_key=True)
    speech_date: Mapped[date] = mapped_column(sql.Date)
    topic: Mapped[str] = mapped_column(sql.String, nullable=True)
    speech_text: Mapped[str] = mapped_column(sql.Text)
    speaker_party: Mapped[str] = mapped_column(sql.String, nullable=True)
    speaker_name: Mapped[str] = mapped_column(sql.String)

    def __repr__(self):
        return f"Speech(speech_id: {self.speech_id!r}, ...)"

    @staticmethod
    def get_info(key, data):
        yield data[key]

    @logged
    def handle_missing(self, data):
        """`handle_missing` is an attempt to repair missing values or fail fast"""
        if not self.speaker_name:
            speakeroldname = next(Speech.get_info(5, data))  # speakeroldname
            self.speaker_name = speakeroldname if speakeroldname else None
        if not self.topic:
            # subtopic or subsubtopic
            if next(Speech.get_info(8, data)):
                self.topic = next(Speech.get_info(8, data))
            elif next(Speech.get_info(9, data)):
                self.topic = next(Speech.get_info(9, data))
            else:
                self.topic = None
        if not self.speech_text:
            self.speech_text = ''
        return self

    def clean(self):
        self.speech_date = create_date(self.speech_date)
        self.speaker_name = clean_name(self.speaker_name)
        self.speech_text = self.clean_text()
        return self

    def clean_text(self) -> None | str:
        if not self.speech_text:
            return None
        banned = config['SPEECH_CRITERIA']['BANNED_WORDS']
        allowed_pos = config['SPEECH_CRITERIA']['WORD_TYPES']
        doc = self.nlp(self.speech_text)
        cleaned_text = ''
        for token in doc:
            if not token.is_stop and not token.lemma_ in banned and token.pos_ in allowed_pos:
                cleaned_text += f' {token.lemma_}'
        return cleaned_text


class ElectionCandidate(Base):
    """Record of election result per candidate (unit: election x candidate)"""

    __tablename__ = "election_candidate"
    keys = config['DATA']['KEYS']["ELEC_CAND"]

    election_candidate_id: Mapped[int] = mapped_column(
        sql.Integer, primary_key=True, autoincrement=True
    )
    person_id: Mapped[int] = mapped_column(
        sql.Integer, sql.ForeignKey("personal_information.identifier"), nullable=True
    )
    election_id: Mapped[int] = mapped_column(
        sql.Integer, sql.ForeignKey("election_results.election_id"), nullable=True
    )
    constituency: Mapped[str] = mapped_column(sql.String, nullable=True)
    election_date: Mapped[date] = mapped_column(sql.Date)
    parliament: Mapped[int] = mapped_column(sql.Integer)
    type: Mapped[str] = mapped_column(sql.String, nullable=True)
    votes: Mapped[int] = mapped_column(sql.Integer)
    result: Mapped[str] = mapped_column(sql.String, nullable=True)

    identifier = -1

    def __repr__(self):
        return f"ElectionCandidate(identifier: {self.identifier!r}, election_id: {self.election_id!r} ...)"

    @staticmethod
    def get_info(key, data):
        # here data already is one entry!
        yield data.find(key).text

    def clean(self):
        self.election_date = create_date(self.election_date)
        self.identifer: str = f"{self.person_id} | {self.election_id}"
        return self


class ParliamentSession(Base):
    """Matching parliaments to time"""

    __tablename__ = 'parliament'
    keys = config['DATA']['KEYS']['SESSION']

    parl_id: Mapped[int] = mapped_column(
        sql.Integer, autoincrement=True, primary_key=True)
    parliament: Mapped[int] = mapped_column(sql.Integer)
    session: Mapped[int] = mapped_column(sql.Integer)
    start_date: Mapped[date] = mapped_column(sql.Date)
    end_date: Mapped[date] = mapped_column(sql.Date)

    def __repr__(self):
        return f"Session({self.start_date} - {self.end_date})"

    def get_info(key, data):
        yield data[key]

    def handle_missing(self):
        if not self.end_date:
            self.end_date = '2050-01-01'
        return self

    def clean(self):
        self.start_date = create_date(self.start_date.split('T')[0])
        self.end_date = create_date(self.end_date.split('T')[0])
        return self


class SpeechLink(Base):
    """Link to join Speeches and Personal data"""
    __tablename__ = 'speech_links'
    speech_link_id: Mapped[int] = mapped_column(
        sql.Integer, autoincrement=True, primary_key=True)
    identifier: Mapped[int] = mapped_column(
        sql.Integer, sql.ForeignKey('personal_information'))
    # not a primary key because we might get the same id through a full
    # and a last name match!
    name: Mapped[str] = mapped_column(sql.String, nullable=False)

    def __repr__(self):
        return f'SpeechLink(identifier: {self.identifier}, name: {self.name})'


class Sample(Base):
    __tablename__ = 'training_set'

    speech_id: Mapped[int] = mapped_column(
        sql.Integer, sql.ForeignKey('speech.speech_id'), primary_key=True)
    in_training: Mapped[bool] = mapped_column(sql.Boolean)

    def __repr__(self):
        return f'Sample(speech_id: {self.speech_id}, {self.in_training})'


class TopicPrediction(Base):
    __tablename__ = 'topic_prediction'

    speech_id: Mapped[int] = mapped_column(
        sql.Integer, sql.ForeignKey('speech.speech_id'), primary_key=True)
    topic: Mapped[int] = mapped_column(sql.Integer)

    def __repr__(self):
        return f'TopicPrediction(speech_id: {self.speech_id}, topic: {self.topic})'
