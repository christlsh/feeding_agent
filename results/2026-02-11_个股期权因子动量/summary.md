# 个股期权因子动量

- **Date**: 2026-02-11
- **URL**: https://mp.weixin.qq.com/s/rz6r3lmG4gDG3rUdM2lzfA
- **Level**: A (Implementable)
- **Category**: factor_mining
- **Relevance**: 1.00

## Summary

这篇文章无论从理论性还是实用性来说都很有价值，文章详细剖析了个股期权市场上存在的因子动量和期权动量，并且还用实证表面了两者的关系：因子动量包含期权动量。
动量效应（过去收益延续到未来）是金融市场最显著的异象之一，已在股票、商品、债券、加密货币等市场广泛证实。2023年Heston等首次发现期权跨式组合存在动量，但用7个期权因子无法解释该现象。
本文的核心问题是：使用更完整的28个期权因子，能否构建显著的因子动量策略？这种因子动量与单个期权动量有何关系？
来源：OptionMetrics IvyDB（1996-2021），CRSP股票价格
收益计算：日度再平衡Delta对冲看涨期权收益（将方向性风险降低90%）
严格筛选：平值、近月、无股息、买卖价差<50%、执行价/现货0.8-1.2等
最终样本：379,165个期权-月度观测，平均每月1,219只标的
基于文献中具有解释力的特征构建，主要包括：
IVRV（隐含-实现波动率差）、VOV（波动率的波动率）
Goyal & Saretto (2009), Ruan (2020)

## Core Idea

本文的核心问题是：使用更完整的28个期权因子，能否构建显著的因子动量策略？这种因子动量与单个期权动量有何关系？

## Methodology

因子构建：每月按特征分10组，1996-1998年为burn-in期确定多空方向，避免前瞻偏差。
（底层是期权合约）                      （底层仍是期权组合，但按因子特征重组）

## Key Findings

- 动量效应（过去收益延续到未来）是金融市场最显著的异象之一，已在股票、商品、债券、加密货币等市场广泛证实。2023年Heston等首次发现期权跨式组合存在动量，但用7个期权因子无法解释该现象。
- 收益计算：日度再平衡Delta对冲看涨期权收益（将方向性风险降低90%）
- 过去收益好的期权 → 继续做多；收益差的期权 → 继续做空
- 做多高分组，做空低分组 → 形成一个因子收益
- 时间序列因子动量（TSFM）：因子过去收益为正 → 做多该因子；为负 → 做空

## Implementation

- **Complexity**: simple
- **Data Required**: L2 orderbook, forward returns, VWAP
- **Notes**: Article contains 1 code snippets; Implement as cross-sectional factor, evaluate with IC/IR and quintile returns
