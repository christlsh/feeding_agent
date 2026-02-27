# ICLR 2026 : AlphaQuant

- **Date**: 2026-02-25
- **URL**: https://mp.weixin.qq.com/s/mzi9MZnkWTOlJ0auUD0K-Q
- **Level**: A (Implementable)
- **Category**: factor_mining
- **Relevance**: 1.00

## Summary

这篇ICLR 2026的文章提出了一种将大型语言模型（LLM）与进化优化相结合的新型自动化特征工程框架，专门用于量化领域。
缺乏鲁棒性：自动化方法往往忽略领域特定细节
结合质量-多样性优化（Quality-Diversity Optimization）实现迭代精炼
使用少样本提示生成PyTorch特征提取函数
使用Python并发库为每个资产并行执行特征函数
基于FLAML框架，使用LightGBM进行超参数调优和交叉验证
少样本提示（Few-Shot Prompting）
错误感知生成（Error-Aware Generation）
动态少样本示例：初始提供基础统计函数（mean, variance, std等），随着发现更优特征而更新示例库
错误感知：提示中包含已消除函数列表和执行错误日志，避免LLM重复犯错

## Core Idea

这篇ICLR 2026的文章提出了一种将大型语言模型（LLM）与进化优化相结合的新型自动化特征工程框架，专门用于量化领域。

## Methodology

这篇ICLR 2026的文章提出了一种将大型语言模型（LLM）与进化优化相结合的新型自动化特征工程框架，专门用于量化领域。
结合质量-多样性优化（Quality-Diversity Optimization）实现迭代精炼
动态少样本示例：初始提供基础统计函数（mean, variance, std等），随着发现更优特征而更新示例库

## Key Findings

- 动态少样本示例：初始提供基础统计函数（mean, variance, std等），随着发现更优特征而更新示例库
- Spearman相关性从0.5提升至0.8+
- nDCG指标显示模型对资产未来表现的排序能力显著增强
- 在COVID-19等极端市场压力下表现稳定

## Implementation

- **Complexity**: simple
- **Data Required**: forward returns, VWAP
- **Notes**: Article contains 2 code snippets; Implement as cross-sectional factor, evaluate with IC/IR and quintile returns
