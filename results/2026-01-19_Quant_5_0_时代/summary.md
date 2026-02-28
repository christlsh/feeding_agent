# Quant 5.0 时代

- **Date**: 2026-01-19
- **URL**: https://mp.weixin.qq.com/s/3hRsiRCOAvfPdz57uBdo6Q
- **Level**: B (Summary Only)
- **Category**: factor_mining
- **Relevance**: 1.00

## Summary

《Quant5.0: Building AGI for Quantitative Investment – Large Investment Model》（简称LIM）由IDEA研究院撰写，提出了一种全新的量化投资研究范式——大型投资模型（LIM），旨在通过“通用基础模型+下游微调”的方式，解决传统量化研究面临的边际收益递减、人力与时间成本上升等问题。
多步骤流程（数据清洗 → 因子挖掘 → 建模 → 组合优化 → 交易执行）效率低；
借鉴GPT等通用大模型的“预训练+微调”范式；
文章提出用一个通用上游模型学习跨市场、跨品种、跨频率的“全局模式”，再微调到具体策略任务。
端到端建模（输入原始数据 → 输出仓位/订单）
1. 上游基础模型（Upstream Foundation Model）
输入：报价数据（价格、成交量、订单簿等）；
输出：未来一段时间内的价格/波动/成交量等；
使用Patching+Masking策略，提升训练效率与鲁棒性；
类似GPT的“下一token预测”，将时间序列切分为patch；

## Core Idea

《Quant5.0: Building AGI for Quantitative Investment – Large Investment Model》（简称LIM）由IDEA研究院撰写，提出了一种全新的量化投资研究范式——大型投资模型（LIM），旨在通过“通用基础模型+下游微调”的方式，解决传统量化研究面临的边际收益递减、人力与时间成本上升等问题。

## Methodology

多步骤流程（数据清洗 → 因子挖掘 → 建模 → 组合优化 → 交易执行）效率低；
使用Patching+Masking策略，提升训练效率与鲁棒性；
性能提升：相比于特定的“小模型”，LIM 基础模型在大规模数据训练下具有更高的性能上限 。

## Key Findings

- 《Quant5.0: Building AGI for Quantitative Investment – Large Investment Model》（简称LIM）由IDEA研究院撰写，提出了一种全新的量化投资研究范式——大型投资模型（LIM），旨在通过“通用基础模型+下游微调”的方式，解决传统量化研究面临的边际收益递减、人力与时间成本上升等问题。
- 使用Patching+Masking策略，提升训练效率与鲁棒性；
- 支持端到端输出：直接输出仓位、订单或alpha信号。
- 知识迁移：实验表明，利用从股票市场学习到的“全球模式（Global patterns）”可以有效提升商品期货市场的预测性能 。
- 性能提升：相比于特定的“小模型”，LIM 基础模型在大规模数据训练下具有更高的性能上限 。
