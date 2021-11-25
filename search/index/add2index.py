import time
import pandas as pd
import redis
import pickle
from elasticsearch import Elasticsearch
from elasticsearch import helpers
from FunPySearch.settings.local import ES_HOST, REDIS_HOST, REDIS_PASSWORD

es = Elasticsearch(['127.0.0.1'], port=9200)


def timer(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        res = func(*args, **kwargs)
        print('共耗时约 {:.2f} 秒'.format(time.time() - start))
        return res

    return wrapper


@timer
def gen(df):
    """ 使用生成器批量写入数据 """
    action = ({
        "_index": "cord19_doc",
        "_type": "_doc",
        "_source": {
            # "cord_uid": "" if pd.isnull(df.loc[i, 'cord_uid']) else df.loc[i, 'cord_uid'],
            # "title": "" if pd.isnull(df.loc[i, 'title']) else df.loc[i, 'title'],
            # "abstract": "" if pd.isnull(df.loc[i, 'abstract']) else df.loc[i, 'abstract'],
            # "content": "" if pd.isnull(df.loc[i, 'body_text']) else df.loc[i, 'body_text'],
            # "authors": "" if pd.isnull(df.loc[i, 'authors']) else df.loc[i, 'authors'],
            # "url": "" if pd.isnull(df.loc[i, 'url']) else df.loc[i, 'url'],
            # "publish_time": "1970-01-01" if pd.isnull(df.loc[i, 'publish_time']) else df.loc[i, 'publish_time'],
            # "title_keyword": "" if pd.isnull(df.loc[i, 'title']) else df.loc[i, 'title']
            "cord_uid": "" if pd.isnull(df.iloc[i, 0]) else df.iloc[i, 0],
            "title": "" if pd.isnull(df.iloc[i, 1]) else df.iloc[i, 1],
            "abstract": "" if pd.isnull(df.iloc[i, 2]) else df.iloc[i, 2],
            "content": "" if pd.isnull(df.iloc[i, 4]) else df.iloc[i, 4],
            "authors": "" if pd.isnull(df.iloc[i, 3]) else df.iloc[i, 3],
            "url": "" if pd.isnull(df.iloc[i, 6]) else df.iloc[i, 6],
            "publish_time": "1970-01-01" if pd.isnull(df.iloc[i, 7]) else df.iloc[i, 7],
            "title_keyword": "" if pd.isnull(df.iloc[i, 1]) else df.iloc[i, 1]
        }
    } for i in range(len(df)))

    helpers.bulk(es, action)


# doc 总数存储到 redis
def save_to_redis(key, init):
    redis_cli = redis.Redis(host=REDIS_HOST, password=REDIS_PASSWORD)
    if redis_cli.get(key):
        count = pickle.loads(redis_cli.get(key))
        count = count + 1
        count = pickle.dumps(count)
        redis_cli.set(key, count)
    else:
        count = pickle.dumps(init)
        redis_cli.set(key, count)


if __name__ == '__main__':
    # create_data()
    # batch_data()
    df_doc = pd.read_csv('rnd4_full_text.tsv', sep='\t', header=None)
    print(len(df_doc))
    df_doc.drop_duplicates(subset=[2, 4, 5], inplace=True)
    # 内容+章节 非空： 53622
    print(len(df_doc))
    df_doc.dropna(axis=0, inplace=True, how='any', subset=[2, 4, 5])
    print(len(df_doc))
    save_to_redis('cord_doc_count', len(df_doc))

    df_doc.columns = ['cord_uid', 'title', 'abstract', 'authors', 'body_text', 'section', 'url', 'publish_time']
    #
    print(df_doc.iloc[14])
    gen(df_doc)

