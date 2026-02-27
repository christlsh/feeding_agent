在这个项目里， 我想让你帮我写一个自动通过微信公众号订阅的目标账号里的量化idea 来进行分析以及运用我现有的数据进行自动化测试。 现在看起来，我们可以通过we mp rss service 进行公众号的订阅了， 所以 这个项目就是用来实现公众号里相关文章的。 需要实现的功能如下：
1. 对于每一个推文，评价和量化投资应用的相关程度。 有一些是非常high level 的内容，简单进行总结就可以。 有一些是hands on 的experiment， 如果我们有现成的数据和算力（有不少新的内容需要GPU进行训练，但是我们目前没有， 所以对于这类就进行总结就好），就直接implement 然后进行测试。 
2. 对于相关度比较高的推文， 只要有更新， 然后进行测试和分析之后， 就进行总结然后推送到钉钉群（刚才已经设置好）
3. 这个repo 底下， 按照不同的推文形成可以直接使用的代码和测试报告（测试的总结发到dingding， 代码和详细结果，就放到这个repo底下）。
4. 你帮我顺着我的这个思路，继续拓展一些可能的需求和可以让整个这个feeding， 阅读， 实现，测试， 总结 的流程更加完善的方式。


我们现成的数据有A股的：
/data/a_share/sihang/l2_ob_full_universe_with_info/ orderbook level 2 的数据
/data/a_share/sihang/GYCNE5_syn Barra risk model 数据
/data/a_share/sihang/index_weights 主要指数成分信息
/data/a_share/sihang/fwd_ret_with_open_intra forward return 数据， 一般用来当作训练和evaluation 的targets
/data/a_share/sihang/limit_status/ · limit_status_subsampled_5min 涨跌停状态数据， 一个是tick 级别的一个是5min subsample 的
/data/a_share/sihang/sec_info/ 股票的信息。
/data/a_share/sihang/all_trade_days.npy 所有交易日期
/data/a_share/sihang/vwap_5m.parquet 每5min 的vwap， 一般用来estimate 执行的slippage

注意A股的各种规则， T+1， 不能short， 涨跌停之类。

生成一个新的git repo 来更近每一次的更新和每一次新的实验结果。 

然后，你就用现在quantML 这个公众号，当作例子，来做一下吧。 你就做最近一周这个公众号的文章。 注意， 在repo里面建立结果的时候， 标注文章日期和简要标题（可以以folder 来包括同一个文章里的信息）