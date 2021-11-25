from elasticsearch_dsl import connections, Document, Keyword, Text, Date, analyzer

connections.create_connection(hosts="127.0.0.1:9200")

# analyzer 为 token 过程
# 5种模式：standard (过滤标点符号)、simple (过滤数字和标点符号)、whitespace (不过滤，按照空格分隔)、
#       stop (过滤停顿单词及标点符号，例如is are等等)、keyword (视为一个整体不进行任何处理)

# 用于 suggest 的分词模式：粗粒度拆分
# my_analyzer = analyzer('ik_smart')


class CordDocIndex(Document):
    # Text() 支持分词、全文检索、存储长度无上限
    # Keyword() 不支持分词，存储长度有限
    cord_uid = Keyword()     # cord_uid
    title = Text(analyzer="whitespace")
    abstract = Text(analyzer="whitespace")
    content = Text(analyzer="whitespace")
    authors = Text()
    url = Keyword()

    title_keyword = Text(analyzer="stop")

    publish_time = Date()

    class Index:
        name = 'cord19_doc'


class CordPsgIndex(Document):

    cord_uid = Keyword()  # cord_uid
    title = Text(analyzer="whitespace")
    abstract = Text(analyzer="whitespace")
    content = Text(analyzer="whitespace")
    authors = Text
    url = Keyword()

    title_keyword = Text(analyzer="stop")

    publish_time = Date()

    class Index:
        name = 'cord19_psg'


if __name__ == "__main__":

    # 建立索引
    CordDocIndex.init()
    CordPsgIndex.init()
