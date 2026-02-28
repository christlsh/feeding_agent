# LLM代码生成新SOTA：如何让AI写出超越人类专家的算法？

- **Date**: 2026-02-14
- **URL**: https://mp.weixin.qq.com/s/Uka_wsjiu8WXMZpZk5Wm3w
- **Level**: A (Implementable)
- **Category**: factor_mining
- **Relevance**: 1.00

## Summary

本文由QuantML联合南京大学，北京大学，美的AI研究院，QuantaAlpha等机构共同发表。
论文地址：https://arxiv.org/pdf/2601.07348
代码地址：https://github.com/QuantaAlpha/EvoControl
在代码生成领域，现有的自进化方法（Self-evolution methods）通过“生成-验证-修正”的迭代循环来提升代码质量。然而，这些方法普遍面临探索效率低下的瓶颈，难以在有限的计算预算（Budget）内发现具有更优时间与空间复杂度的解决方案。这种低效性主要源于三个核心限制：
初始化偏差（Initialization Bias）：初始解往往陷入较差的局部最优区域。
不可控的随机进化（Uncontrolled Stochastic Evolution）：缺乏反馈引导的随机操作导致搜索方向迷失。
进化经验利用不足（Insufficient Experience Utilization）：跨任务或任务内的成功/失败经验未能被有效复用。
针对上述痛点，本文提出了受控自进化（Controlled Self-Evolution, CSE）框架。该框架包含三大核心组件：
多样化规划初始化（Diversified Planning Initialization）：生成结构上截然不同的算法策略，以覆盖广泛的解空间。
遗传进化（Genetic Evolution）：用基于反馈引导的机制替代随机操作，包括定向变异（Targeted Mutation）和组合交叉（Compositional Crossover）。

## Core Idea

本文由QuantML联合南京大学，北京大学，美的AI研究院，QuantaAlpha等机构共同发表。

## Methodology

在代码生成领域，现有的自进化方法（Self-evolution methods）通过“生成-验证-修正”的迭代循环来提升代码质量。然而，这些方法普遍面临探索效率低下的瓶颈，难以在有限的计算预算（Budget）内发现具有更优时间与空间复杂度的解决方案。这种低效性主要源于三个核心限制：
代码生成已成为大语言模型（LLM）的关键应用。尽管现有模型在生成功能正确的代码方面表现出色，但在处理复杂算法问题时，生成的代码往往“正确但效率低下”（correct yet inefficient）。为了解决这一问题，自进化方法应运而生，试图通过迭代搜索来优化代码。
现有的自进化方法（如AlphaEvolve, SE-Agent等）存在严重的效率缺陷。随机变异和交叉操作缺乏来自执行反馈（如测试失败、性能瓶颈）的明确指导，导致生成了大量无效变体。此外，模型无法从历史错误中学习，导致在同一任务中重复犯错，或无法将某一任务的优化模式迁移至新任务。CSE框架的设计初衷即是为了在保证高代码质量的同时，大幅提升探索效率。

## Key Findings

- 本文由QuantML联合南京大学，北京大学，美的AI研究院，QuantaAlpha等机构共同发表。
- 代码地址：https://github.com/QuantaAlpha/EvoControl
- 在代码生成领域，现有的自进化方法（Self-evolution methods）通过“生成-验证-修正”的迭代循环来提升代码质量。然而，这些方法普遍面临探索效率低下的瓶颈，难以在有限的计算预算（Budget）内发现具有更优时间与空间复杂度的解决方案。这种低效性主要源于三个核心限制：
- 在EffiBench-X基准测试上的实验表明，CSE在多种LLM骨干网络（如GPT-4o, DeepSeek-V3, Qwen3等）上均显著优于现有基准（包括AlphaEvolve和SE-Agent），展现出更高的早期探索效率以及持续的进化能力。
- 代码生成已成为大语言模型（LLM）的关键应用。尽管现有模型在生成功能正确的代码方面表现出色，但在处理复杂算法问题时，生成的代码往往“正确但效率低下”（correct yet inefficient）。为了解决这一问题，自进化方法应运而生，试图通过迭代搜索来优化代码。

## Implementation

- **Complexity**: complex
- **Data Required**: L2 orderbook, forward returns, VWAP
- **Notes**: Implement as cross-sectional factor, evaluate with IC/IR and quintile returns
