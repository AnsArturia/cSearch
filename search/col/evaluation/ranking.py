import os
import random
import time
from multiprocessing.dummy import Pool

import torch

from src.utils import print_message, load_checkpoint, batch
from src.evaluation.metrics import Metrics


# query : 单条查询项 'how long can the coronavirus live outside the body'
# pids : pid 的 list ，length=1000
# passages : topk 的 psg 组成的 list ，length=1000
def rerank(args, query, pids, passages, index=None):
    colbert = args.colbert
    Q = colbert.query([query])
    # Q.shape = [1,38,128]
    if index is None:
        tokenized_passages = list(args.pool.map(colbert.tokenizer.tokenize, passages))
        # 修改 colbert.score 计算
        # scores = [colbert.score(Q, colbert.doc(D)).cpu() for D in batch(tokenized_passages, args.bsize)]
        scores = [colbert.score_eval(query, passages, Q, colbert.doc(D)).cpu() for D in
                  batch(tokenized_passages, args.bsize)]
        scores = torch.cat(scores).sort(descending=True)
    else:
        # index 的类型
        args.buffer[:len(pids)].zero_()

        # int 的 pid
        docs = [index[int(pid)-1] for pid in pids]
        # str 的 pid，判断 pid 是否存在
        # docs = [index[pid] for pid in pids if pid in index.keys()]

        for idx, d in enumerate(docs):
            args.buffer[idx, :len(d)] = d
        # 修改 score 计算
        # scores = colbert.score(Q, args.buffer[:len(pids)].cuda().float())
        scores = colbert.score_eval(query, passages, Q, args.buffer[:len(pids)].cuda().float())
        scores = scores.sort(descending=True)

    ranked = scores.indices.tolist()

    ranked_scores = scores.values.tolist()
    ranked_pids = [pids[position] for position in ranked]
    ranked_passages = [passages[position] for position in ranked]

    assert len(ranked_pids) == len(set(ranked_pids))

    return list(zip(ranked_scores, ranked_pids, ranked_passages))


def evaluate(args, index=None):
    qrels, queries, topK_docs, topK_pids = args.qrels, args.queries, args.topK_docs, args.topK_pids

    metrics = Metrics(mrr_depths={10}, recall_depths={10, 20, 30}, total_queries=None)

    if index:
        # int 的 pid
        # args.buffer = torch.zeros(1000, args.doc_maxlen, args.dim, dtype=index[0].dtype)
        # , dtype=index.values()[0].dtype
        # str 的 pid
        args.buffer = torch.zeros(1000, args.doc_maxlen, args.dim, dtype=list(index.values())[0].dtype)

    output_path = '.'.join([str(x) for x in [args.run_name, 'tsv', int(time.time())]])
    output_path = os.path.join(args.output_dir, output_path)

    # TODO: Save an associated metadata file with the args.input_args

    with open(output_path, 'w') as outputfile:
        with torch.no_grad():
            keys = sorted(list(queries.keys()))
            random.shuffle(keys)

            for query_idx, qid in enumerate(keys):
                query = queries[qid]
                print_message(query_idx, qid, query, '\n')

                if qrels and args.shortcircuit and len(set.intersection(set(qrels[qid]), set(topK_pids[qid]))) == 0:
                    continue

                # rerank(args, query, pids, passages, index=None)
                if args.full_text:
                    ranking = rerank_full(args, query, topK_pids[qid], topK_docs[qid], index)
                else:
                    ranking = rerank(args, query, topK_pids[qid], topK_docs[qid], index)

                for i, (score, pid, passage) in enumerate(ranking):
                    # 写出的格式修改 query-number     Q0     document-id     rank     score     Exp
                    outputfile.write('\t'.join([str(x) for x in [qid, 'Q0', pid, i + 1, score, 'exp']]) + "\n")
                    # outputfile.write('\t'.join([str(x) for x in [qid, pid, i+1]]) + "\n")

                    if i + 1 in [1, 2, 5, 10, 20, 100]:
                        print("#> " + str(i + 1) + ") ", pid, ":", score, '    ', passage)

                if qrels:
                    metrics.add(query_idx, qid, ranking, qrels[qid])

                    for i, (score, pid, passage) in enumerate(ranking):
                        if pid in qrels[qid]:
                            print("\n#> Found", pid, "at position", i + 1, "with score", score)
                            print(passage)

                    metrics.print_metrics(query_idx)

                print_message("#> checkpoint['batch'] =", args.checkpoint['batch'], '\n')
                print("output_path =", output_path)
                print("\n\n")


class Proc(object):
    def __init__(self, args, query):
        self.args = args
        self.query = query

    @staticmethod
    def evaluate_doc(args, query, doc):
        colbert = args.colbert
        Q = colbert.query([query])
        passages_token = list(colbert.tokenizer.tokenize(psg) for psg in doc)
        # 查看 scores 的数据类型
        with torch.no_grad():
            scores = [colbert.score(Q, colbert.doc(D)).cpu() for D in batch(passages_token, args.bsize)]
        scores = torch.cat(scores).tolist()

        # 全文 score 方式，效果hen差
        # if len(scores) > 2:
        #     return scores[0] + scores[1] + max(scores[2:])
        # else:
        #     return sum(scores)
        if len(scores) >= 2:
            return scores[0] + scores[1]
        else:
            return scores


    def process(self, docs):
        pool = Pool(2)
        scores = list(
            pool.starmap(self.evaluate_doc, [(self.args, self.query, doc.split('\n')) for doc in docs]))
        pool.close()
        return scores

    # def __getstate__(self):
    #     self_dict = self.__dict__.copy()
    #     del self_dict['pool']
    #     return self_dict
    #
    # def __setstate__(self, state):
    #     self.__dict__.update(state)

# 封装 对每个文章的各个段落进行 token 和 score 的函数；返回：score_list
    # 传参：Colbert, each doc (list),
    # 返回：当前 doc 的 score
# def evaluate_doc(args, query, doc):
#     colbert = args.colbert
#     Q = colbert.query([query])
#     passages_token = list(colbert.tokenizer.tokenize(psg) for psg in doc)
#     # 查看 scores 的数据类型
#     scores = [colbert.score(Q, colbert.doc(D)).cpu() for D in batch(passages_token, args.bsize)]
#     scores = torch.cat(scores).tolist()
#
#     if len(scores) > 2:
#         return scores[0] + scores[1] + max(scores[2:])
#     else:
#         return sum(scores)

def not_empty(s):
    return s and s.strip()
# 重写成 full text 的重排
# evaluate 中添加判断 args 传参即可
# docs 读取出来应该是 list 格式，bm25 中保存用'\n'隔开，读取的时候再 split
def rerank_full(args, query, pids, docs, index=None):
    colbert = args.colbert
    Q = colbert.query([query])

    if index is None:
        p = Proc(args, query)
        scores = p.process(docs)

        # 修改 pool 写法，已注释部分为废物
        # scores = list(args.pool.starmap(evaluate_doc, (args, query, [list(filter(not_empty, doc.split('\n'))) for doc in docs])))
        # for doc in docs:
        #     # psgs of each doc
        #     passages = list(filter(not_empty, doc.split('\n')))
        #     tokenized_passages = list(args.pool.map(colbert.tokenizer.tokenize, passages))
        # # 修改 colbert.score 计算
        #     each_scores = [colbert.score_eval(query, passages, Q, colbert.doc(D)).cpu() for D in batch(tokenized_passages, args.bsize)]
        #     # list(tensor)  一个psg一个score（score是tensor） 最多128个？
        #     each_scores = torch.cat(each_scores).tolist()
        #     if len(each_scores) > 2:
        #         scores.append(each_scores[0] + each_scores[1] + max(each_scores[2:]))
        #     else:
        #         scores.append(sum(each_scores))

        scores = torch.tensor(scores).sort(descending=True)

    # # # index 的情况还没改！！！！必须改
    else:
        # index 的类型
        args.buffer[:len(pids)].zero_()
        docs = [index[pid] for pid in pids]
        for idx, d in enumerate(docs):
            args.buffer[idx, :len(d)] = d
        # 修改 score 计算
        scores = colbert.score(Q, args.buffer[:len(pids)].cuda().float())

        # 问题：index的时候是按全文来index的，现在eval如何拆开计算？
        # 重新 index？
        # scores = colbert.score_eval(query, docs, Q, args.buffer[:len(pids)].cuda().float())
        scores = scores.sort(descending=True)

    ranked = scores.indices.tolist()

    ranked_scores = scores.values.tolist()
    ranked_pids = [pids[position] for position in ranked]
    ranked_passages = [docs[position] for position in ranked]

    assert len(ranked_pids) == len(set(ranked_pids))

    return list(zip(ranked_scores, ranked_pids, ranked_passages))


