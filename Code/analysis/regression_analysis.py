import pandas as pd
import sqlalchemy.orm as orm
import statsmodels.formula.api as smf

from analysis.create_dataframe import DatasetTask
from helpers import Task, logged


@logged
def get_df(i: int, session: orm.Session):
    """Create a neat dataset"""
    items = DatasetTask.setup(i, session)
    df = DatasetTask.run(items)
    return df


@logged
def create_baseline_reg(df: pd.DataFrame):
    """Simple regression for illustration purposes"""
    print(df['topic'].mean())
    print(df.groupby('close_election')['topic'].mean())
    base_reg = smf.ols(
        'topic ~ close_election', data=df)
    res = base_reg.fit()
    print(res.summary())


RegressionTask = Task(get_df, create_baseline_reg, None)
