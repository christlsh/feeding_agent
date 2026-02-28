# 多资产、宏微观、多任务的金融LLM框架

- **Date**: 2026-02-09
- **URL**: https://mp.weixin.qq.com/s/P5TSdX-rcJ66qxI_TTNghg
- **Level**: A (Implementable)
- **Category**: factor_mining
- **Relevance**: 1.00

## Summary

之前和私募的朋友聊天，聊到真有机构是LLM驱动宏观交易的，前期的投入不可谓不大。今天看了这篇文章感觉大概也就如此了吧。
现代金融市场日益复杂、相互关联且波动剧烈，金融机构和监管机构迫切需要能够处理多粒度金融决策的智能系统：
微观层面：个股预测、资产定价、短期交易信号（影响投资组合优化）
宏观层面：系统性风险监测、金融危机早期预警（影响金融稳定与国家安全）
传统方法多为单模态（仅时间序列或仅文本）或单任务（微观与宏观分离）
现有LLM金融系统（如FinGPT、BloombergGPT）虽能处理文本，但缺乏统一架构来同时建模微观交易行为和宏观系统性风险
无法捕捉跨尺度依赖关系（市场微观结构与系统性压力形成之间的反馈循环）
首个配备模块化任务头的统一多模态LLM，同时处理微观股票预测和宏观系统性风险评估
整合文本、数值和视觉金融信号，捕获多层金融依赖关系
连接微观市场波动与宏观风险动态，提升预测准确性和可解释性

## Core Idea

传统方法多为单模态（仅时间序列或仅文本）或单任务（微观与宏观分离）

## Methodology

传统方法多为单模态（仅时间序列或仅文本）或单任务（微观与宏观分离）
现有LLM金融系统（如FinGPT、BloombergGPT）虽能处理文本，但缺乏统一架构来同时建模微观交易行为和宏观系统性风险
多模态融合优势：统一架构捕获跨模态依赖（市场数据+文本信号），显著提升微观预测准确性

## Key Findings

- 连接微观市场波动与宏观风险动态，提升预测准确性和可解释性
- 股票收益     风险警报      监管建议
- 关键提升：相比最强基线Llama-Fin，方向准确率提升5.7个百分点，MAPE降低**17.4%**。
- 关键提升：ROC-AUC达到0.892，显著优于所有基线，证明多模态融合在处理类别不平衡时的优势。
- 关键提升：早期预警准确率**82.3%，危机F1分数79.8%**，显著超越领先的GNN基线。

## Implementation

- **Complexity**: simple
- **Data Required**: forward returns
- **Notes**: Article contains 1 code snippets; Implement as cross-sectional factor, evaluate with IC/IR and quintile returns
