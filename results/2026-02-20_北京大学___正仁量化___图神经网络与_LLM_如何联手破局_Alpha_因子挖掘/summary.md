# 北京大学 × 正仁量化 | 图神经网络与 LLM 如何联手破局 Alpha 因子挖掘？

- **Date**: 2026-02-20
- **URL**: https://mp.weixin.qq.com/s/la9g8vlC2w-FmZb6AvOWcA
- **Level**: B (Summary Only)
- **Category**: factor_mining
- **Relevance**: 1.00

## Summary

论文链接：https://arxiv.org/pdf/2602.11917v1
代码链接：https://github.com/gta0804/AlphaPROBE
在量化金融领域，从高维且充满噪音的市场数据中提取预测性信号（即 Alpha 因子挖掘）是核心痛点。当前主流的自动化因子挖掘方法受限于两大范式：解耦因子生成（Decoupled Factor Generation, DFG）与迭代因子演化（Iterative Factor Evolution, IFE）。这两种范式均缺乏全局结构化视野。DFG 范式将因子池视为松散无序的集合，导致冗余的搜索空间；IFE 范式则管中窥豹，仅关注单一的父子节点局部优化，忽略了整个因子演化网络的拓扑价值。
针对上述结构性缺陷，AlphaPROBE（Alpha Mining via Principled Retrieval and On-graph Biased Evolution）框架重构了因子挖掘的底层逻辑，将其转化为在有向无环图（Directed Acyclic Graph, DAG）上的战略性导航与节点生成问题。该框架利用贝叶斯因子检索器（Bayesian Factor Retriever）平衡探索与利用（Exploration-Exploitation trade-off），并结合感知 DAG 拓扑结构的因子生成器（DAG-aware Factor Generator）执行上下文感知的非冗余优化，在预测精度、收益稳定性及模型训练效率上实现了显著的阶跃式提升。
在量化交易中，Alpha 因子是一种将各类数据源转化为未来资产收益预测信号的数学表达式。在系统实现层面，因子通常被表征为抽象语法树（Abstract Syntax Tree, AST）。在该树状结构中，叶子节点代表原始输入特征（如开盘价
等价量数据，以及基本面或另类数据），内部节点则代表数学算子（如截面排序 Rank、时序均值 TsMean、加减乘除等）。

## Core Idea

在量化金融领域，从高维且充满噪音的市场数据中提取预测性信号（即 Alpha 因子挖掘）是核心痛点。当前主流的自动化因子挖掘方法受限于两大范式：解耦因子生成（Decoupled Factor Generation, DFG）与迭代因子演化（Iterative Factor Evolution, IFE）。这两种范式均缺乏全局结构化视野。DFG 范式将因子池视为松散无序的集合，导致冗余的搜索空间；IFE 范式则管中窥豹，仅关注单一的父子节点局部优化，忽略了整个因子演化网络的拓扑价值。

## Methodology

在量化金融领域，从高维且充满噪音的市场数据中提取预测性信号（即 Alpha 因子挖掘）是核心痛点。当前主流的自动化因子挖掘方法受限于两大范式：解耦因子生成（Decoupled Factor Generation, DFG）与迭代因子演化（Iterative Factor Evolution, IFE）。这两种范式均缺乏全局结构化视野。DFG 范式将因子池视为松散无序的集合，导致冗余的搜索空间；IF
针对上述结构性缺陷，AlphaPROBE（Alpha Mining via Principled Retrieval and On-graph Biased Evolution）框架重构了因子挖掘的底层逻辑，将其转化为在有向无环图（Directed Acyclic Graph, DAG）上的战略性导航与节点生成问题。该框架利用贝叶斯因子检索器（Bayesian Factor Retriever）平
在量化交易中，Alpha 因子是一种将各类数据源转化为未来资产收益预测信号的数学表达式。在系统实现层面，因子通常被表征为抽象语法树（Abstract Syntax Tree, AST）。在该树状结构中，叶子节点代表原始输入特征（如开盘价

## Key Findings

- 代码链接：https://github.com/gta0804/AlphaPROBE
- 在量化金融领域，从高维且充满噪音的市场数据中提取预测性信号（即 Alpha 因子挖掘）是核心痛点。当前主流的自动化因子挖掘方法受限于两大范式：解耦因子生成（Decoupled Factor Generation, DFG）与迭代因子演化（Iterative Factor Evolution, IFE）。这两种范式均缺乏全局结构化视野。DFG 范式将因子池视为松散无序的集合，导致冗余的搜索空间；IF
- 针对上述结构性缺陷，AlphaPROBE（Alpha Mining via Principled Retrieval and On-graph Biased Evolution）框架重构了因子挖掘的底层逻辑，将其转化为在有向无环图（Directed Acyclic Graph, DAG）上的战略性导航与节点生成问题。该框架利用贝叶斯因子检索器（Bayesian Factor Retriever）平
- 在量化交易中，Alpha 因子是一种将各类数据源转化为未来资产收益预测信号的数学表达式。在系统实现层面，因子通常被表征为抽象语法树（Abstract Syntax Tree, AST）。在该树状结构中，叶子节点代表原始输入特征（如开盘价
- 映射具体的金融目标，例如组合的夏普比率（Sharpe Ratio），或结合信息系数（Information Coefficient, IC）与因子间低相关性惩罚项的综合评价指标，旨在构建兼具高预测能力与低共线性的正交因子矩阵。
