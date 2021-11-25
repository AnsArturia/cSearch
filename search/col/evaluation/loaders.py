import torch
from torch.backends import cudnn

from src.parameters import DEVICE
from src.model import ColBERT
from src.utils import print_message, load_checkpoint
import os
import pandas as pd

def load_qrels(qrels_path):
    if qrels_path is None:
        return None

    print_message("#> Loading qrels from", qrels_path, "...")

    qrels = {}
    with open(qrels_path, mode='r', encoding="utf-8") as f:
        for line in f:
            qid, x, pid, y = map(str, line.strip().split('\t'))
            assert x == str(0) and y == str(1)
            qrels[qid] = qrels.get(qid, [])
            qrels[qid].append(pid)

    assert all(len(qrels[qid]) == len(set(qrels[qid])) for qid in qrels)

    avg_positive = round(sum(len(qrels[qid]) for qid in qrels) / len(qrels), 2)

    print_message("#> Loaded qrels for", len(qrels), "unique queries with",
                  avg_positive, "positives per query on average.\n")

    return qrels


def load_topK(topK_path):
    queries = {}
    topK_docs = {}
    topK_pids = {}

    print_message("#> Loading the top-k per query from", topK_path, "...")

    with open(topK_path) as f:
        for line in f:
            qid, pid, query, passage = line.split('\t')
            qid, pid = str(qid), str(pid)

            assert (qid not in queries) or (queries[qid] == query)
            queries[qid] = query
            topK_docs[qid] = topK_docs.get(qid, [])
            topK_docs[qid].append(passage)
            topK_pids[qid] = topK_pids.get(qid, [])
            topK_pids[qid].append(pid)

    assert all(len(topK_pids[qid]) == len(set(topK_pids[qid])) for qid in topK_pids)

    Ks = [len(topK_pids[qid]) for qid in topK_pids]

    print_message("#> max(Ks) =", max(Ks), ", avg(Ks) =", round(sum(Ks) / len(Ks), 2))
    print_message("#> Loaded the top-k per query for", len(queries), "unique queries.\n")

    return queries, topK_docs, topK_pids

# 加载全文 str
def load_topK_full(topK_path):
    queries = {}
    topK_docs = {}
    topK_pids = {}

    print_message("#> Loading the top-k per query from", topK_path, "...")

    df = pd.read_csv(topK_path, sep='\t', header=None)
    for i, f in df.iterrows():
        qid, pid, query, doc = f[0], f[1], f[2], f[3]
        # psg_list = [doc.split('\n')]
        qid, pid = str(qid), str(pid)

        assert (qid not in queries) or (queries[qid] == query)
        queries[qid] = query
        topK_docs[qid] = topK_docs.get(qid, [])
        topK_docs[qid].append(doc)
        topK_pids[qid] = topK_pids.get(qid, [])
        topK_pids[qid].append(pid)

    assert all(len(topK_pids[qid]) == len(set(topK_pids[qid])) for qid in topK_pids)

    Ks = [len(topK_pids[qid]) for qid in topK_pids]

    print_message("#> max(Ks) =", max(Ks), ", avg(Ks) =", round(sum(Ks) / len(Ks), 2))
    print_message("#> Loaded the top-k per query for", len(queries), "unique queries.\n")

    return queries, topK_docs, topK_pids


def load_colbert(args):
    print_message("#> Loading model checkpoint.")
    # 'bert-base-uncased'
    # '/media/ex/wuzhao/v0.1/ColBERT/src/model_cache/bert-base-uncased'
    colbert = ColBERT.from_pretrained('/media/ex/wuzhao/v0.1/ColBERT/src/model_cache/bert-base-uncased',
                                      query_maxlen=args.query_maxlen,
                                      doc_maxlen=args.doc_maxlen,
                                      dim=args.dim,
                                      similarity_metric=args.similarity)

    colbert = colbert.to(DEVICE)
    # args.checkpoint = os.path.join(args.data_dir, args.checkpoint)
    checkpoint = load_checkpoint(args.checkpoint, colbert)
    colbert.eval()

    print('\n')

    return colbert, checkpoint
