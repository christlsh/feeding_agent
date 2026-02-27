# AQR Portfolio-ML——考虑交易成本的组合ML算法

- **Date**: 2026-02-23
- **URL**: https://mp.weixin.qq.com/s/5wuULHOSFZTlNvMmD49IPw
- **Level**: A (Implementable)
- **Category**: factor_mining
- **Relevance**: 1.00

## Summary

文章指出，现有金融机器学习（ML）文献存在一个关键问题：忽视交易成本。这导致：
ML预测模型过度依赖短暂的小盘股特征（如1个月反转策略）
虽然毛收益（gross returns）看起来很好，但扣除交易成本后净收益（net returns）为负
开发一个将交易成本直接纳入ML目标函数的框架，使投资策略能够：
理论贡献：可执行的有效前沿（Implementable Efficient Frontier）
作者提出用扣除交易成本后的风险-收益权衡来评估投资策略，而非传统教科书中的无摩擦有效前沿。
传统Markowitz-ML方法：毛收益夏普比率约2.0，但扣除交易成本后前沿立即跌入负收益区域
标准组合排序（Portfolio Sort）：同样不可执行，净收益为负
静态ML优化（Static-ML）：虽能产生正净夏普比率，但效用为负（风险过高）
作者提出的Portfolio-ML：显著优于所有基准方法

## Core Idea

文章指出，现有金融机器学习（ML）文献存在一个关键问题：忽视交易成本。这导致：

## Methodology

理论贡献：可执行的有效前沿（Implementable Efficient Frontier）
传统Markowitz-ML方法：毛收益夏普比率约2.0，但扣除交易成本后前沿立即跌入负收益区域
利用随机傅里叶特征（Random Fourier Features）近似aim portfolio函数

## Key Findings

- 虽然毛收益（gross returns）看起来很好，但扣除交易成本后净收益（net returns）为负
- 作者提出用扣除交易成本后的风险-收益权衡来评估投资策略，而非传统教科书中的无摩擦有效前沿。
- 传统Markowitz-ML方法：毛收益夏普比率约2.0，但扣除交易成本后前沿立即跌入负收益区域
- 标准组合排序（Portfolio Sort）：同样不可执行，净收益为负
- 静态ML优化（Static-ML）：虽能产生正净夏普比率，但效用为负（风险过高）

## Implementation

- **Complexity**: simple
- **Data Required**: forward returns, Barra risk model, index weights, VWAP
- **Notes**: Article contains 2 code snippets; Implement as cross-sectional factor, evaluate with IC/IR and quintile returns
