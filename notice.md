* python3 manage.py migrate --settings=FunPySearch.settings.local

1. pip 安装各种( redis 在 /usr/local/bin; elasticsearch 在 ~/)

2. 修改 mysql 配置 && redis 配置(注意 redis6.x 采用 ACL 模式)

3. celery 注册

4. elasticsearch 访问端口 9200，port 9200 已经被占用

` ps aux | grep -i manage 查看当前进程并 sudo kill -9 PID `


#### 目录
##### FunPySearch
* 配置文件

##### search
* ./trained_models : 训练模型
* ./models : 连接 ES + 创建索引类（格式）
* ./tasks : 加载模型的方法
* ./views : 检索


#### 更改
##### search / doc_models.py
* elasticsearch 建立索引
##### search / index 
* 批量导入数据
##### search / trained_models
##### 

##### user / models.py
* 对应 mysql 中 user_keyword2vec 表