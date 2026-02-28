# QuantaAlpha：基于轨迹进化的可控Alpha挖掘框架

- **Date**: 2026-02-12
- **URL**: https://mp.weixin.qq.com/s/qPazA7ttGk56cmZkPutCog
- **Level**: A (Implementable)
- **Category**: factor_mining
- **Relevance**: 1.00

## Summary

QuantaAlpha 团队成立于 2025年，我们的核心团队成员来自顶尖对冲基金、领先的人工智能公司（如字节跳动、阿里巴巴等）以及清华大学、北京大学、中国科学院、CMU等知名学府。团队使命是探索智能的 "量子 (Quantum)" 本质，开拓 Agent 研究的 "Alpha" 前沿——从 CodeAgent 到自进化智能，再到AI4Science(金融及生物信息等)，致力于重新定义 AI 的边界。
团队主页：https://quantaalpha.com/
论文链接：https://arxiv.org/pdf/2602.07085
代码仓库：https://github.com/QuantaAlpha/QuantaAlpha
金融市场具有高噪声和非平稳性，导致Alpha挖掘对回测噪声极度敏感，且难以应对突发的市场风格转换。尽管近期的Agent框架提高了挖掘自动化程度，但往往缺乏可控的多轮搜索机制以及对已验证经验的可靠复用。QuantaAlpha作为一个进化式Alpha挖掘框架，将每一次端到端的挖掘过程视为一条轨迹（Trajectory），并通过轨迹级的变异（Mutation）和交叉（Crossover）操作来持续优化因子。
QuantaAlpha能够定位轨迹中的次优步骤进行针对性修正，并重组高回报轨迹中的互补片段以复用有效模式，从而在挖掘迭代中实现结构化的探索与细化。在因子生成阶段，系统强制要求假设（Hypothesis）、因子表达式（Factor Expression）和可执行代码（Code）之间的语义一致性，同时约束生成因子的复杂度和冗余度以缓解拥挤效应。在沪深300（CSI 300）上的大量实验表明，QuantaAlpha显著优于强基线模型和现有的Agent系统。在使用GPT-5.2时，其实现了0.1501的IC（Information Coefficient），年化收益率（ARR）达27.75%，最大回撤（MDD）控制在7.98%。此外，挖掘出的因子在CSI 500和S&P 500上展现出极强的迁移能力，证实了该框架在市场分布偏移下的鲁棒性。

## Core Idea

QuantaAlpha 团队成立于 2025年，我们的核心团队成员来自顶尖对冲基金、领先的人工智能公司（如字节跳动、阿里巴巴等）以及清华大学、北京大学、中国科学院、CMU等知名学府。团队使命是探索智能的 "量子 (Quantum)" 本质，开拓 Agent 研究的 "Alpha" 前沿——从 CodeAgent 到自进化智能，再到AI4Science(金融及生物信息等)，致力于重新定义 AI 的边界。

## Methodology

QuantaAlpha能够定位轨迹中的次优步骤进行针对性修正，并重组高回报轨迹中的互补片段以复用有效模式，从而在挖掘迭代中实现结构化的探索与细化。在因子生成阶段，系统强制要求假设（Hypothesis）、因子表达式（Factor Expression）和可执行代码（Code）之间的语义一致性，同时约束生成因子的复杂度和冗余度以缓解拥挤效应。在沪深300（CSI 300）上的大量实验表明，Quant
金融市场是高维、非平稳的随机系统，具有厚尾、时变波动率和截面相关性等特征。量化投资依赖于从噪声中提取预测信号（Alpha）。近期，LLM及其Agent框架被引入因子研究工作流，利用其推理和代码生成能力自动化因子构建与回测反馈闭环。
可信度有限（Limited Trustworthiness）： 许多方法依赖于基于瞬时上下文的随机重生成，未能显式继承跨迭代的验证逻辑，导致缺乏可追溯的谱系，生成的因子难以审计和信任。

## Key Findings

- QuantaAlpha 团队成立于 2025年，我们的核心团队成员来自顶尖对冲基金、领先的人工智能公司（如字节跳动、阿里巴巴等）以及清华大学、北京大学、中国科学院、CMU等知名学府。团队使命是探索智能的 "量子 (Quantum)" 本质，开拓 Agent 研究的 "Alpha" 前沿——从 CodeAgent 到自进化智能，再到AI4Science(金融及生物信息等)，致力于重新定义 AI 的边
- 团队主页：https://quantaalpha.com/
- 代码仓库：https://github.com/QuantaAlpha/QuantaAlpha
- 金融市场具有高噪声和非平稳性，导致Alpha挖掘对回测噪声极度敏感，且难以应对突发的市场风格转换。尽管近期的Agent框架提高了挖掘自动化程度，但往往缺乏可控的多轮搜索机制以及对已验证经验的可靠复用。QuantaAlpha作为一个进化式Alpha挖掘框架，将每一次端到端的挖掘过程视为一条轨迹（Trajectory），并通过轨迹级的变异（Mutation）和交叉（Crossover）操作来持续优化因
- QuantaAlpha能够定位轨迹中的次优步骤进行针对性修正，并重组高回报轨迹中的互补片段以复用有效模式，从而在挖掘迭代中实现结构化的探索与细化。在因子生成阶段，系统强制要求假设（Hypothesis）、因子表达式（Factor Expression）和可执行代码（Code）之间的语义一致性，同时约束生成因子的复杂度和冗余度以缓解拥挤效应。在沪深300（CSI 300）上的大量实验表明，Quant

## Implementation

- **Complexity**: complex
- **Data Required**: forward returns, index weights, VWAP, limit status
- **Notes**: Implement as cross-sectional factor, evaluate with IC/IR and quintile returns
