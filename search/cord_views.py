import pickle

from django.contrib.auth import get_user_model
from django.shortcuts import render
import json

from FunPySearch.settings.local import ES_HOST, REDIS_HOST, REDIS_PASSWORD
from .tasks import gen_word2vec_save_to_mysql
from django.utils.datastructures import OrderedSet
from django.views.generic.base import View
from search.cord_models import CordDocIndex, CordPsgIndex
from django.http import HttpResponse
from datetime import datetime
import redis
from elasticsearch import Elasticsearch
from django.views.generic.base import RedirectView

from user.models import KeyWord2Vec, UserProfile

User = get_user_model()
# # # # # elasticsearch port = 9200
client = Elasticsearch(hosts=[ES_HOST], scheme="http", port=9200,)

# 使用redis实现top-n排行榜
redis_cli = redis.Redis(host=REDIS_HOST, password=REDIS_PASSWORD)


class IndexView(View):
    """首页get请求top-n排行榜"""

    @staticmethod
    def get(request):
        topn_search_clean = []
        topn_search = redis_cli.zrevrangebyscore(
            "search_keywords_set", "+inf", "-inf", start=0, num=5)

        for topn_key in topn_search:
            topn_key = str(topn_key, encoding="utf-8")
            topn_search_clean.append(topn_key)
        topn_search = topn_search_clean

        return render(request, "index.html", {"topn_search": topn_search})


class CordSearchView(View):

    def get(self, request):
        # 获取查询项
        query = request.GET.get("q", "")
        try:
            # TODO：1。tasks func 加载模型
            gen_word2vec_save_to_mysql.delay("small", query)
        except:
            print("异步添加word2vec失败,检查是否开启celery: celery -A ContentSearch worker -l debug")

        # 历史搜索记录
        try:
            history_text = request.user.history
            history_list = history_text.split(",")

            upper_score_list = []
            for history_one in history_list:
                try:
                    upper_score_list.append(history_one)
                    try:
                        # 每个 历史搜索记录 的最大相似度关键词
                        key_words_vec_text = KeyWord2Vec.objects.get(keyword=history_one).keyword_word2vec
                        key_words_vec_list = key_words_vec_text.split(",")
                        for key_words_one in key_words_vec_list:
                            upper_score_list.append(key_words_one)
                    except:
                        pass
                except:
                    pass
            upper_score_set = set(upper_score_list)
            upper_score_set_list = list(upper_score_set)
            upper_score_set_list = [x for x in upper_score_set_list if x != '']
            # upper score set 涨分列表
            print(upper_score_set_list)

            # 更新 历史搜索记录
            history_list.append(query)
            history_new_set = set(history_list)
            history_new_set_list = list(history_new_set)
            history_new_txt = ",".join(history_new_set_list)
            # user
            user = UserProfile.objects.get(id=request.user.id)
            user.history = history_new_txt
            user.save()
        except:
            history_new_set_list = []
            upper_score_set_list = []

        print("*********"*30)
        history_new_set_list = [one for one in history_new_set_list if one.strip()]
        upper_score_set_list = [one for one in upper_score_set_list if one.strip()]
        print("*********"*30)

        # 通用部分
        # 实现搜索关键词keyword加1操作
        print(query)
        redis_cli.zincrby("search_keywords_set", 1, query)

        # 获取topn个搜索词
        topn_search_clean = []
        topn_search = redis_cli.zrevrangebyscore(
            "search_keywords_set", "+inf", "-inf", start=0, num=5)
        for topn_key in topn_search:
            topn_key = str(topn_key, encoding="utf-8")
            topn_search_clean.append(topn_key)
        topn_search = topn_search_clean

        # 获取文章数量
        cord_doc_count = redis_cli.get("cord_doc_count")
        if cord_doc_count:
            cord_doc_count = pickle.loads(cord_doc_count)
        else:
            cord_doc_count = 0

        # 当前要获取第几页的数据
        page = request.GET.get("p", "1")
        try:
            page = int(page)
        except BaseException:
            page = 1

        response = []
        start_time = datetime.now()
        s_type = request.GET.get("s_type", "")

        # 检索方式为 doc
        if s_type == "doc":
            body = {
                "query": {
                    "function_score": {
                        "query": {
                            "multi_match": {
                                "query": query,
                                "fields": ["title", "abstract", "content"]
                            },
                        },
                        "script_score": {

                            "script": {
                                "params": {
                                    "title_keyword": upper_score_set_list
                                },
                                "source": "double final_score=_score;"
                                          "int count=0;"
                                          "int total = params.title_keyword.size();"
                                          "while(count < total) { "
                                          "String upper_score_title = params.title_keyword[count]; "
                                          "if(doc['title_keyword'].value.contains(upper_score_title)){"
                                          "final_score = final_score+_score;}"
                                          "count++;"
                                          "}"
                                          "return final_score;"
                            }
                        }
                    }
                },
                "from": (page - 1) * 10,
                "size": 10,
                "highlight": {
                    "pre_tags": ['<span class="keyWord">'],
                    "post_tags": ['</span>'],
                    "fields": {
                        "title": {},
                        "abstract": {},
                        "content": {},
                        # "topics": {},
                    }}}
            print(json.dumps(body, ensure_ascii=False))

            response_dict = {"doc": client.search(
                index="cord19_doc",
                request_timeout=60,
                body={
                    "query": {
                        "function_score": {
                            "query": {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["title", "abstract", "content"]
                                },
                            },
                            "script_score": {

                                "script": {
                                    "params": {
                                        "title_keyword": upper_score_set_list
                                    },
                                    "source": "double final_score=_score;int count=0;int total = params.title_keyword.size();while(count < total) { String upper_score_title = params.title_keyword[count]; if(doc['title_keyword'].value.contains(upper_score_title)){final_score = final_score+_score;}count++;}return final_score;"
                                }
                            }
                        }
                    },
                    "from": (page - 1) * 10,
                    "size": 10,
                    "highlight": {
                        "pre_tags": ['<span class="keyWord">'],
                        "post_tags": ['</span>'],
                        "fields": {
                            "title": {},
                            "abstract": {},
                            "content": {},
                            # "topics": {},
                        }}}),
            }

        if s_type == "question":
            body = {
                "query": {
                    "function_score": {
                        "query": {
                            "multi_match": {
                                "query": query,
                                "fields": ["title", "content"]
                            },
                        },
                        "script_score": {

                            "script": {
                                "params": {
                                    "title_keyword": upper_score_set_list
                                },
                                "source": "double final_score=_score;int count=0;int total = params.title_keyword.size();while(count < total) { String upper_score_title = params.title_keyword[count]; if(doc['title_keyword'].value.contains(upper_score_title)){final_score = final_score+_score;}count++;}return final_score;"
                            }
                        }
                    }
                },
                "from": (page - 1) * 10,
                "size": 10,
                "highlight": {
                    "pre_tags": ['<span class="keyWord">'],
                    "post_tags": ['</span>'],
                    "fields": {
                        "title": {},
                        "content": {},
                        "topics": {},
                    }}}
            print(json.dumps(body, ensure_ascii=False))

            response_dict = {"question": client.search(
                index="zhihu_question",
                request_timeout=60,
                body={
                    "query": {
                        "function_score": {
                            "query": {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["title", "content"]
                                },
                            },
                            "script_score": {

                                "script": {
                                    "params": {
                                        "title_keyword": upper_score_set_list
                                    },
                                    "source": "double final_score=_score;int count=0;int total = params.title_keyword.size();while(count < total) { String upper_score_title = params.title_keyword[count]; if(doc['title_keyword'].value.contains(upper_score_title)){final_score = final_score+_score;}count++;}return final_score;"
                                }
                            }
                        }
                    },
                    "from": (page - 1) * 10,
                    "size": 10,
                    "highlight": {
                        "pre_tags": ['<span class="keyWord">'],
                        "post_tags": ['</span>'],
                        "fields": {
                            "title": {},
                            "content": {},
                            "topics": {},
                        }}}),

                "answer": client.search(
                    index="zhihu_answer",
                    request_timeout=60,
                    body={
                        "query": {
                            "function_score": {
                                "query": {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["author_name", "content"]
                                    },
                                },
                                "script_score": {

                                    "script": {
                                        "params": {
                                            "title_keyword": upper_score_set_list
                                        },
                                        "source": "double final_score=_score;int count=0;int total = params.title_keyword.size();while(count < total) { String upper_score_title = params.title_keyword[count]; if(doc['author_name'].value.contains(upper_score_title)){final_score = final_score+_score;}count++;}return final_score;"
                                    }
                                }
                            }
                        },
                        "from": (
                                        page - 1) * 10,
                        "size": 10,
                        "highlight": {
                            "pre_tags": ['<span class="keyWord">'],
                            "post_tags": ['</span>'],
                            "fields": {
                                "content": {},
                                "author_name": {},
                            }}})}

        end_time = datetime.now()
        last_seconds = (end_time - start_time).total_seconds()

        # 伯乐在线 / 知乎问答 具体的信息
        hit_list = []
        if s_type == "question":
            for hit in response_dict["question"]["hits"]["hits"]:
                """问题"""
                hit_dict_question = {}
                if "title" in hit["highlight"]:
                    hit_dict_question["title"] = "".join(hit["highlight"]["title"])
                else:
                    hit_dict_question["title"] = hit["_source"]["title"]
                if "content" in hit["highlight"]:
                    hit_dict_question["content"] = "".join(hit["highlight"]["content"])
                else:
                    hit_dict_question["content"] = hit["_source"]["content"]
                hit_dict_question["create_date"] = hit["_source"]["crawl_time"]
                hit_dict_question["url"] = hit["_source"]["url"]
                hit_dict_question["score"] = hit["_score"]
                hit_dict_question["source_site"] = "知乎问题"
                hit_list.append(hit_dict_question)
            for hit in response_dict["answer"]["hits"]["hits"]:
                hit_dict_answer = {}
                if "author_name" in hit["highlight"]:
                    hit_dict_answer["title"] = "".join(hit["highlight"]["author_name"])
                else:
                    hit_dict_answer["title"] = hit["_source"]["author_name"]
                if "content" in hit["highlight"]:
                    hit_dict_answer["content"] = "".join(hit["highlight"]["content"])
                else:
                    hit_dict_answer["content"] = hit["_source"]["content"]
                hit_dict_answer["create_date"] = hit["_source"]["update_time"]
                hit_dict_answer["score"] = hit["_score"]
                hit_dict_answer["url"] = hit["_source"]["url"]
                hit_dict_answer["source_site"] = "知乎回答"
                hit_list.append(hit_dict_answer)
            response_dict["question"]["hits"]["total"]["value"] = response_dict["question"]["hits"]["total"]["value"] + \
                                                                  response_dict["answer"]["hits"]["total"]["value"]
            response = response_dict["question"]

        if s_type == "doc":
            for hit in response_dict["doc"]["hits"]["hits"]:
                """问题"""
                hit_dict_doc = {}
                if "title" in hit["highlight"]:
                    hit_dict_doc["title"] = "".join(hit["highlight"]["title"])
                else:
                    hit_dict_doc["title"] = hit["_source"]["title"]
                if "content" in hit["highlight"]:
                    hit_dict_doc["content"] = "".join(hit["highlight"]["content"])
                else:
                    hit_dict_doc["content"] = hit["_source"]["content"]
                hit_dict_doc["abstract"] = hit["_source"]["abstract"]
                hit_dict_doc["publish_time"] = hit["_source"]["publish_time"]
                hit_dict_doc["url"] = hit["_source"]["url"]
                hit_dict_doc["score"] = hit["_score"]
                hit_dict_doc["source_site"] = "全文"
                hit_list.append(hit_dict_doc)

            response_dict["doc"]["hits"]["total"]["value"] = response_dict["doc"]["hits"]["total"]["value"]
            response = response_dict["doc"]

        total_nums = int(response["hits"]["total"]["value"])

        # 计算出总页数
        if (page % 10) > 0:
            page_nums = int(total_nums / 10) + 1
        else:
            page_nums = int(total_nums / 10)

        return render(request, "result.html", {"page": page,
                                               "all_hits": hit_list,
                                               "key_words": query,
                                               "total_nums": total_nums,
                                               "page_nums": page_nums,
                                               "last_seconds": last_seconds,
                                               "topn_search": topn_search,
                                               "s_type": s_type,
                                               "doc_count": cord_doc_count,
                                               "history_list": history_new_set_list,
                                               })


favicon_view = RedirectView.as_view(
    url='http://searchstatic.mtianyan.cn/favicon.ico', permanent=True)
