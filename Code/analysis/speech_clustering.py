"""Vectorizing speeches in order to create clusters"""


import pickle

from sqlalchemy import Select
from sqlalchemy.orm import Session
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

from models import Speech, Sample, TopicPrediction
from helpers import Task, sql_get, logged
from config import config


def inspect_model(model: KMeans, vectorizer: TfidfVectorizer):
    """Inspect the words closest to the cluster center"""
    centroids = [m.argsort()[::-1] for m in model.cluster_centers_]
    words = vectorizer.get_feature_names_out()
    cluster_words = [[words[i] for i in c[:20]] for c in centroids]
    with open(config['FILES']['CLUSTER_WORDS'], mode='w', encoding='utf-8') as file:
        file.write('Representative words for each cluster\n')
        for i, cluster in enumerate(cluster_words):
            file.write(f'\nCluster #{i}\n')
            file.writelines([f'{c}\n' for c in cluster])


@logged
def get_all_speeches(session: Session) -> list[tuple[int, str]]:
    """Obtain list of identifier, text pairs of all Speeches"""
    stmt = Select(Speech.speech_id, Speech.speech_text)
    items = sql_get(stmt, session)
    return items


@logged
def get_sample(session: Session) -> tuple[int, str]:
    """Obtain identifier, text pairs for Speeches in the sample"""
    stmt = Select(Speech.speech_text).where(
        Sample.in_training).join(Sample)
    train_set = sql_get(stmt, session)
    return [ts[0] for ts in train_set]


# Vectorizing Speeches --------------------------------------------------------

@logged
def vectorize_speeches(items: list[tuple[int, str]]) -> TfidfVectorizer:
    """Fit tf-idf vectorizer on `items`"""
    speeches = [i[1] for i in items]
    ngrams = config['SPEECH_CRITERIA']['NGRAMS']
    vectorizer = TfidfVectorizer(input='content', ngram_range=(1, ngrams))
    vectorizer.fit(speeches)
    with open(config['FILES']['VECTORIZER_PATH'], mode='wb') as file:
        pickle.dump(vectorizer, file)
    return vectorizer


VectorizeTask = Task(get_all_speeches, vectorize_speeches, None)


# Training Model --------------------------------------------------------------

@logged
def train_model(items: list[str], vectorizer: TfidfVectorizer) -> KMeans:
    """Train KMeans cluster model on `items`, using vectorizer"""
    n = config['SPEECH_CRITERIA']['CLUSTERS']
    word_scores = vectorizer.transform(items)
    model = KMeans(n_clusters=n, init='k-means++', n_init=10, random_state=1)
    model.fit(word_scores)
    with open(config['FILES']['KMEANS_PATH'], mode='wb') as file:
        pickle.dump(model, file)
    return model


TrainTask = Task(get_sample, train_model, None)


# Prediction ------------------------------------------------------------------

@logged
def assign_topics(items: tuple[int, str], session: Session):
    """Assigns a topic to every speech, executing `VectorizeTask` and
    `TrainTask` and prompts for inspection"""
    # the setup is the same for predicting and vectorizer fitting
    vectorizer = VectorizeTask.run(items)
    train_set = TrainTask.setup(session)
    model = TrainTask.run(train_set, vectorizer)
    inspect_model(model, vectorizer)
    scores = vectorizer.transform(i[1] for i in items)
    speech_topics = model.predict(scores)
    for speech_prediction in zip([i[0] for i in items], speech_topics):
        instance = TopicPrediction(
            speech_id=speech_prediction[0], topic=int(speech_prediction[1]))
        session.add(instance)
    session.commit()


ClusteringTask = Task(get_all_speeches, assign_topics, TopicPrediction)
