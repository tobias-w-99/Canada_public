# Canadian Parliament Project

This project is the result of an assignment during the summer 2022 at the LMU.
Its purpose was to download data on Canadian members of parliament in the time
around WWII, as well as their speeches. The idea was to find inherent topic 
clusters one of which was expected to be the war. The goal was to conduct some
regression analysis on the correlation of different determinants, e.g. whether
the last election was close, with the likelihood that a member of parliament 
would talk about the war. 

Unfortunately, I can only publish the most recent version after an extensive 
review and rework as earlier versions of the repository might have contained 
minor code sections that were not mine or data that I am not sure whether I am 
allowed to share.

## Setup

This project assumes that there is the following folder structure within the 
base directory:

```
.
\-Code
\-Data
  \-Raw
  \-Processing
    \-Input
    \-Output
    \-Log
\-Presentation
```

The starting file `Link_ID.csv` was provided by our instructor and is supposed 
to be placed in `Data/Raw`. As is detailed in `Code/download/get_personal.py` 
it would be quite easy to obtain the same data from the web.  


## Execution

The module is executable and runs the entire project. Be aware that this takes 
quite some time (several hours). It is structured by the use of several tasks
which consist of a setup and a worker function and an associated ORM schema.
The working directory is assumed to be the base directory and the project can
be run by `python code`. Have a look at the file `Code/config.yaml` for some
possibilities to change the configuration of the project. 

### Download

The files relevant for the download of the raw data are grouped in the 
directory `Code/download`. Those use the list of identification number of the 
members of parliament provided by `Link_ID.csv`. Those are used to construct 
the queries to the (undocumented) API of the Library of the Canadian 
Parliament (<lop.parl.ca>) and the Linked Parliamentary Data Project 
(<lipad.ca/>). Those files rely on `httpx` for the download, `lxml` for 
XML-parsing and create database entries using `sqlalchemy`. 

The information extracted from these sources consists of personal information 
on MoPs, their memberships in committees and parties, their federal experience,
election data and all the speeches in the time range 1930 - 1950. Those are 
stored in tables of a SQLite-Database.

Note that the speeches are not stored as they are, but in a reduced 
(stopwords, banned words, restriction to adverbs and nouns), normalized (lower 
case) and lemmatized form. This is done through the use of the `spacy` 
pipeline `en_core_web_sm` (<spacy.io/usage>). 


### Speech data preparation
  
In a first step, we try to link the speech data to the personal information on 
the MoPs. The problem is that there is no common identifier, which is why we 
are forced to match by name. This is done using the Jaro-Winkler distance 
measure provided by the library `jaro-winkler`. By default, matches are 
accepted if they are perfect or have a single highest score above 0.97. In 
case that there is only one name of the speaker, it is assumed to be the last 
name and matches with last names only are tried to obtained. Similarly, if 
there is no other match and there are two names, weignore second and third 
names and try to match only with first and last name.

A next step consists of creating a sample for training our cluster model. We 
use kmeans clustering for convenience as it is relatively simple and produces 
reasonable results. The data is previously vectorized by a tf-idf vectorizer. 
Both the vectorizer and the cluster model are provided by `scikit-learn`. We 
use bigrams by default to hopefully capture more meaningful phrases. The model
is then used to classify all the speeches. It provides a list of keywords for
each cluster by which its adequateness is evaluated. The user is prompted to 
choose the cluster which seems to be most related to our war topic. 


### Regression Analysis

Once all the preparation is done, it is attempted to construct a single dataset
which can then be used for regression. In particular, there are several dummy 
variables constructed, among them a dummy for whether the previous election was
close, a dummy whether the MoP was part of a committe dealing with security or 
was working in a security-related profession. Another dummy variable `topic` 
will serve as the endogenous variable and indicates whether the topic is 
related to war according to the prediction of the kmeans-clustering and the
user's evaluation of the clusters. This step heavily relies on `sqlalchemy` and
the well-known `pandas` DataFrame. 

The regression is only there for illustration as there is no obvious real-life 
interest in any of the variables and their correlation with war-related 
speeches and there is little room for a causal analysis. 