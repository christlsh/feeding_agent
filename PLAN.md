# Feeding Agent 实现计划

## 项目目标
构建一个自动化系统：从微信公众号订阅 → 文章分析 → 量化策略实现/测试 → 结果推送到钉钉 + 存入repo

## 架构设计

```
feeding_agent/
├── config.py                  # 配置（we-mp-rss地址、钉钉webhook、数据路径等）
├── run.py                     # 主入口：处理指定公众号的最近文章
├── core/
│   ├── fetcher.py             # 从we-mp-rss API拉取文章列表和内容
│   ├── parser.py              # HTML→纯文本，提取代码块、公式、关键概念
│   ├── classifier.py          # 评估文章与量化投资的相关度，分类处理方式
│   ├── analyzer.py            # 文章分析+总结（提取核心idea、方法论、可实现性）
│   ├── implementer.py         # 对可实现的策略/因子，生成代码并运行回测
│   ├── reporter.py            # 生成测试报告（markdown格式）
│   └── notifier.py            # 推送到钉钉（复用已配置的webhook+签名）
├── data/
│   └── data_loader.py         # 统一的数据加载接口（polars，封装所有数据源）
├── results/                   # 按 YYYY-MM-DD_文章简称/ 组织
│   └── 2026-02-26_Janus-Q/
│       ├── summary.md         # 文章总结
│       ├── strategy.py        # 实现的策略代码（如有）
│       ├── backtest.py        # 回测代码（如有）
│       └── report.md          # 测试报告（如有）
└── utils/
    └── wx_fetcher.py          # 备用：直接curl抓取微信文章（当API无内容时）
```

## 实现步骤

### Step 1: 基础设施
- `config.py`: 所有配置集中管理
- `data/data_loader.py`: 用polars封装数据加载（L2 OB, fwd_ret, Barra, index_weights, VWAP, limit_status, sec_info）
- `core/notifier.py`: 钉钉推送（含HMAC签名）
- `utils/wx_fetcher.py`: 直接从微信抓取文章内容（当we-mp-rss中content为空时）

### Step 2: 文章获取+解析
- `core/fetcher.py`: 调用we-mp-rss API获取文章列表，对content为空的文章用curl补充抓取
- `core/parser.py`: 清洗HTML，提取纯文本、代码块、公式、论文链接等结构化信息

### Step 3: 分类+分析
- `core/classifier.py`: 基于关键词+结构分析评估文章相关度和类型：
  - **Level A** (可实现): 有具体因子/策略/模型，且我们有对应数据可测试（非GPU依赖）
  - **Level B** (需总结): 高度相关但需GPU/无对应数据/纯理论
  - **Level C** (低相关): 新闻、广告、工具推荐等
- `core/analyzer.py`: 对Level A/B生成结构化总结

### Step 4: 策略实现+回测引擎
- `core/implementer.py`: 对Level A文章，根据提取的策略逻辑生成可运行代码
- 回测框架：基于polars的轻量级因子测试流程
  - 因子计算 → IC/IR分析 → 分组收益 → 考虑T+1和涨跌停约束

### Step 5: 报告生成+推送
- `core/reporter.py`: 生成markdown报告
- 推送到钉钉：每篇文章一条消息，Level A含回测结果摘要

### Step 6: 处理QuantML最近一周文章（8篇）

预分类（基于标题初判）：
| 日期 | 标题 | 预分类 | 说明 |
|------|------|--------|------|
| 02-27 | 199的KimiClaw到底值不值？ | C | AI工具推荐 |
| 02-26 | Janus-Q: 端到端事件驱动交易框架 | A/B | 事件驱动交易，看具体实现 |
| 02-25 | QuantML 交流群 | C | 广告 |
| 02-25 | ICLR 26: 经济学的"神经网络" | B | 决策理论，偏理论 |
| 02-24 | LUNA崩盘: Jane Street内幕抢跑 | C | 市场新闻 |
| 02-23 | AI是否适合构建交易策略？ | B | 讨论型文章 |
| 02-22 | JP Morgan: 深度强化学习资产配置 | A/B | RL资产配置，可能需GPU |
| 02-20 | 北大×正仁量化: 图神经网络Alpha因子 | A/B | Alpha因子挖掘，高度相关 |

## 扩展功能建议（第4点要求）
1. **定时自动运行**: 结合cron/systemd，每天自动处理新文章
2. **多公众号管理**: 支持批量监控多个量化相关公众号
3. **因子库积累**: 将每次实验的因子保存到统一因子库，支持增量回测
4. **历史文章对比**: 新文章的idea是否和之前的文章重复/类似
5. **实验版本管理**: 每次实验自动git commit，追踪因子演进
6. **数据质量监控**: 自动检测新数据是否到位，数据异常预警
7. **微信授权自动续期提醒**: 提前1天钉钉提醒重新扫码

## 技术约束
- 全程使用polars（不用pandas）
- A股规则：T+1, 不能做空, 涨跌停限制
- 无GPU：需要GPU训练的策略只做总结
- Python环境：/home/sihang/anaconda3/bin/python (polars已安装)
- 数据范围：2020-01至2025-12（L2/fwd_ret到2025-12, Barra到2026-02）
