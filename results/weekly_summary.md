# QuantML 本周文章分析报告

**处理时间**: 2026-02-20 至 2026-02-27 | **共8篇文章**

## 分类统计
- **Level A (Implementable)**: 0 (所有可实现的论文均需GPU，已实现传统baseline)
- **Level B (Summary + Baseline)**: 5
- **Level C (Low Relevance)**: 3

## 文章列表

### Level B - 高相关度文章

| 日期 | 标题 | 类别 | 回测 |
|------|------|------|------|
| 02-20 | 北大×正仁量化: GNN+LLM Alpha因子挖掘 | factor_mining | ✅ 基线因子测试 |
| 02-22 | JP Morgan: DRL vs MVO资产配置 | portfolio_optimization | ✅ MVO回测 |
| 02-23 | AI是否适合构建交易策略？ | risk_management | 讨论型 |
| 02-25 | ICLR 26: 可分层最优决策系统 | ml_strategy | 理论型 |
| 02-26 | 港科大×IDEA: Janus-Q事件驱动交易框架 | factor_mining | 需GPU |

### Level C - 低相关度文章

| 日期 | 标题 | 原因 |
|------|------|------|
| 02-24 | LUNA崩盘: Jane Street内幕抢跑 | 市场新闻 |
| 02-25 | QuantML 交流群 | 广告 |
| 02-27 | 199的KimiClaw到底值不值？ | 工具推荐 |

## 回测结果摘要

### MVO Portfolio Backtest (JP Morgan论文baseline)
- **Universe**: CSI300 | **Period**: 2024-01-02 to 2025-12-18
- **年化收益**: 23.54% | **Sharpe**: 0.95 | **Max DD**: -21.66%
- **Alpha over equal-weight**: 5.55% | **IR**: 0.36
- **Setup**: 20日动量 + Barra GYCNE5逆方差, long-only, max 5%/stock

### Baseline Alpha Factors (北大论文baseline)
- **Universe**: 全A ~5000股 | **Period**: 2024-01-02 to 2025-12-18

| 因子 | IC Mean | IR | LS Sharpe | 结论 |
|------|---------|-----|-----------|------|
| Momentum_20d | -0.038 | -0.21 | -1.00 | A股动量反转，与美股相反 |
| Reversal_5d | +0.026 | +0.15 | +0.35 | 短期均值回归有效 |
| Volatility_20d | +0.041 | +0.18 | +0.62 | 低波动异常最强 |

## 关键洞察
1. A股20日动量因子显著为负（IC=-3.8%），说明中期存在明显的反转效应
2. 低波动因子在A股市场表现最好（IC=4.1%），低波动溢价稳定
3. MVO在CSI300上可以获得5.5%年化alpha，但Information Ratio较低（0.36）
4. 本周多篇论文涉及GNN/LLM/DRL等需GPU训练的方法，仅做了总结和传统baseline测试
