# 不确定性排序预测 | 模型夏普提升27%

- **Date**: 2026-01-20
- **URL**: https://mp.weixin.qq.com/s/HHVl_0Ap3anTvKKWHltMdg
- **Level**: A (Implementable)
- **Category**: factor_mining
- **Relevance**: 1.00

## Summary

这篇文章提出了一种新的资产定价框架——不确定性调整排序（Uncertainty-Adjusted Sorting），核心思想是：
在构建投资组合时，不只是使用机器学习模型的点预测（point prediction），而是将预测的不确定性（uncertainty）也纳入排序规则，从而提升投资组合的风险调整后收益（Sharpe比率）。
在资产定价中，机器学习（ML）模型通常用于预测未来收益（点预测）。
然后，根据预测值排序，构建多空组合（long-short portfolio）。
但这种方法忽略了预测的不确定性，即不同资产、不同时间的预测可靠性是不同的。
不改变ML模型的训练过程（即不改变预测模型本身）。
用预测区间（prediction interval）代替点预测进行排序。
2.1 预测区间（Prediction Interval）
对每个资产i，在时间t，ML模型给出一个点预测：
然后，基于历史预测误差（残差），构造一个对称的预测区间：

## Core Idea

这篇文章提出了一种新的资产定价框架——不确定性调整排序（Uncertainty-Adjusted Sorting），核心思想是：

## Methodology

但这种方法忽略了预测的不确定性，即不同资产、不同时间的预测可靠性是不同的。
训练集：25年（如1967–1991），验证集：5年，测试集：1年。

## Key Findings

- 在构建投资组合时，不只是使用机器学习模型的点预测（point prediction），而是将预测的不确定性（uncertainty）也纳入排序规则，从而提升投资组合的风险调整后收益（Sharpe比率）。
- 在资产定价中，机器学习（ML）模型通常用于预测未来收益（点预测）。
- Sharpe比率提升：尽管收益略降，但波动率下降更多，Sharpe比率提升。
- 对稳定模型效果有限：如XGBoost本身已较稳定，提升有限。
- 资产级置换：打乱资产与不确定性的对应关系 → 性能提升消失。

## Implementation

- **Complexity**: complex
- **Data Required**: forward returns
- **Notes**: Implement as cross-sectional factor, evaluate with IC/IR and quintile returns
