# 因子魔法：行业市值中性化

- **Date**: 2026-01-06
- **URL**: https://mp.weixin.qq.com/s/zAkrSxLAc8NOb0_Rl7WYjg
- **Level**: A (Implementable)
- **Category**: factor_mining
- **Relevance**: 0.68

## Summary

对因子进行中性化，是一个常规的做法，正好星球有用户问到，我干脆详细讲讲这个东西。
机构通常通过采购或者自己复现来实现Barra风格中性，Barra-CNE5有10个以上的风格因子，如果没有条件进行这么复杂的中性化，可以参Fama-French 五因子进行简单的中性化即可。
1、通常的解释是Pure-alpha那一套，比如剥离掉风格之后，还有没有选股的能力。那么如果一个因子剥离完后没用就真的没用吗？显然不是，星球有说过这个问题。
2、除了pure-alpha，有的时候中性化还能起到起死回生的魔法效果，从无用到有用。
我写了一个demo放到QuantSeek-V6框架里，感兴趣的用户星球自取。

## Methodology

机构通常通过采购或者自己复现来实现Barra风格中性，Barra-CNE5有10个以上的风格因子，如果没有条件进行这么复杂的中性化，可以参Fama-French 五因子进行简单的中性化即可。

## Key Findings

- 1、通常的解释是Pure-alpha那一套，比如剥离掉风格之后，还有没有选股的能力。那么如果一个因子剥离完后没用就真的没用吗？显然不是，星球有说过这个问题。
- 2、除了pure-alpha，有的时候中性化还能起到起死回生的魔法效果，从无用到有用。

## Implementation

- **Complexity**: complex
- **Data Required**: Barra risk model
- **Notes**: Implement as cross-sectional factor, evaluate with IC/IR and quintile returns
