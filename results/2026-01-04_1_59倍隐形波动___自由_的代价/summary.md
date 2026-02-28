# 1.59倍隐形波动——“自由”的代价

- **Date**: 2026-01-04
- **URL**: https://mp.weixin.qq.com/s/HEmTjMmiWD_evDBcpUriuQ
- **Level**: A (Implementable)
- **Category**: factor_mining
- **Relevance**: 1.00

## Summary

近年来，机器学习（ML）在资产定价领域的应用迅速普及，大量研究表明非线性模型（如神经网络、树模型）在预测股票收益方面优于传统线性模型。然而，不同研究在模型设计上的选择差异巨大，导致结果难以比较、复现性差，且缺乏统一标准。
本文首次系统评估了7类关键设计选择对机器学习模型预测股票收益的影响，构建了1,056个不同组合的模型，全面衡量其样本外表现，并引入“非标准误差”（nonstandard error）概念，量化设计选择带来的不确定性。
样本：1957年1月至2021年12月，美国NYSE、AMEX、NASDAQ上市普通股（剔除市值最小的20%微型股）
特征：使用Chen & Zimmermann (2022) 提供的开源因子库，共207个特征。
组合构建：每月按模型预测值排序，构建十分位多空组合（long top decile, short bottom decile），采用NYSE市值加权
2. 设计选择（7类 × 多种选项 = 1,056种组合）
OLS、ENET、RF、GB、NN1~NN5、ENS NN、ENS ML
超额收益（RET-RF）、市场调整收益（RET-MKT）、CAPM alpha（RET-CAPM）
是否剔除“未发表因子”（Post-Publication）
是否特征预筛选（Feature Selection）

## Core Idea

近年来，机器学习（ML）在资产定价领域的应用迅速普及，大量研究表明非线性模型（如神经网络、树模型）在预测股票收益方面优于传统线性模型。然而，不同研究在模型设计上的选择差异巨大，导致结果难以比较、复现性差，且缺乏统一标准。

## Methodology

特征：使用Chen & Zimmermann (2022) 提供的开源因子库，共207个特征。
✅ 结论：Post-Publication、Training Window、Target Transformation、Target Variable、Algorithm 是最关键的设计选择。

## Key Findings

- 近年来，机器学习（ML）在资产定价领域的应用迅速普及，大量研究表明非线性模型（如神经网络、树模型）在预测股票收益方面优于传统线性模型。然而，不同研究在模型设计上的选择差异巨大，导致结果难以比较、复现性差，且缺乏统一标准。
- 本文首次系统评估了7类关键设计选择对机器学习模型预测股票收益的影响，构建了1,056个不同组合的模型，全面衡量其样本外表现，并引入“非标准误差”（nonstandard error）概念，量化设计选择带来的不确定性。
- 超额收益（RET-RF）、市场调整收益（RET-MKT）、CAPM alpha（RET-CAPM）
- 月频多空组合收益：0.13% ~ 1.98%
- 进一步分析ENS ML（非线性集成）vs OLS（线性）的相对表现，发现非线性模型仅在以下条件下显著优于线性模型：

## Implementation

- **Complexity**: complex
- **Data Required**: forward returns
- **Notes**: Implement as cross-sectional factor, evaluate with IC/IR and quintile returns
