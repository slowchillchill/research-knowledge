# 主题分类索引

本页按主题链接正式知识卡；卡片及来源原文仍是唯一研究内容源。分类表示阅读与检索方向，不表示方法已实际采用、效果获验证或生命周期变为 active。每篇的适用条件、限制和证据以完整 K/S 卡为准。

<a id="agent-efficiency-self-evolution"></a>

## 开发与研究 Agent：效率与自进化

通用方法类别，关注开发与研究智能体的效率、探索、上下文与记忆管理、反馈评估及自进化方法。该类别名称不等于已经实现或验证自进化。

| 知识卡 | 来源 | 当前状态 |
| --- | --- | --- |
| [K-000033 · Fork-and-Flush](../knowledge/K-000033.md) | [S-000034 · arXiv:2610.07447v1](../sources/S-000034.md) | draft / reported / not_attempted |

### 检索入口

在仓库根目录按类别检索，显式纳入待审卡，再读取完整卡片和来源：

```bash
python3 -B scripts/kb.py search '开发与研究 Agent：效率与自进化' --include-inactive
python3 -B scripts/kb.py read K-000033
python3 -B scripts/kb.py sources K-000033
```

也可搜索 `自进化`。MCP 对应 `search_knowledge` 的 `include_inactive=true`；随后调用 `read_card` 和 `trace_sources`。保持默认搜索规则：只有 active、非样例、未过审阅期限的卡进入默认有效知识，类别入口不提升草稿状态。

<a id="prediction-market-making"></a>

## 预测市场：订单簿做市与执行证据

本入口关注预测市场订单簿的报价、库存风险、信用分配与执行仿真边界。作者报告的历史回放结果与拟议实验须分别阅读，不能将模拟 PV 当作实盘业绩。

| 知识卡 | 来源 | 当前状态 |
| --- | --- | --- |
| [K-000034 · 协作多智能体做市与 markout 信用分配](../knowledge/K-000034.md) | [S-000035 · arXiv:2610.26789v1](../sources/S-000035.md) | draft / reported / not_attempted |

### 检索入口

```bash
python3 -B scripts/kb.py search '预测市场' --include-inactive
python3 -B scripts/kb.py read K-000034
python3 -B scripts/kb.py sources K-000034
```

读取完整卡片中的统计口径、数据与执行限制；本卡未执行科研实验或独立复现，保持草稿状态，不进入默认有效检索。

<a id="prediction-market-contracts"></a>

## 预测市场：合约信息、成交量与争议风险

关注上线文本的预测证据、时间漂移、稀有争议及样本边界；静态代码风险尚未量化，不表示全部结果无效。

| 知识卡 | 来源 | 当前状态 |
| --- | --- | --- |
| [K-000040 · 上线信息、成交量漂移与稀有争议](../knowledge/K-000040.md) | [S-000041 · arXiv:2610.29578v1](../sources/S-000041.md)；[S-000042 · Zenodo 1.0.0](../sources/S-000042.md) | draft / reported / not_attempted |

```bash
python3 -B scripts/kb.py search '预测市场上线信息' --include-inactive
python3 -B scripts/kb.py read K-000040
python3 -B scripts/kb.py sources K-000040
```

<a id="competitive-market-making"></a>

## 市场微观结构：报价竞争与学习均衡

理论条件、时间平均口径和现实执行机制须分开阅读；均衡存在与无内部遗憾结果不提供PPO或盈利保证。

| 知识卡 | 来源 | 当前状态 |
| --- | --- | --- |
| [K-000041 · 竞争做市均衡与时间平均报价包络](../knowledge/K-000041.md) | [S-000043 · arXiv:2610.30891v1](../sources/S-000043.md) | draft / reported / not_attempted |

```bash
python3 -B scripts/kb.py search '竞争做市均衡' --include-inactive
python3 -B scripts/kb.py read K-000041
python3 -B scripts/kb.py sources K-000041
```

<a id="meta-rl-memory-adaptation"></a>

## 元强化学习：记忆语义与测试时适应

区分episode内快记忆、跨episode摘要、PPO当前参数因果重建和旧策略概率；任务族泛化不表示金融非平稳适应已验证。

| 知识卡 | 来源 | 当前状态 |
| --- | --- | --- |
| [K-000042 · METTA双层记忆与任务相关的在线适应](../knowledge/K-000042.md) | [S-000044 · arXiv:2610.31656v1](../sources/S-000044.md) | draft / reported / not_attempted |

```bash
python3 -B scripts/kb.py search 'METTA' --include-inactive
python3 -B scripts/kb.py read K-000042
python3 -B scripts/kb.py sources K-000042
```

<a id="institutional-flow-execution"></a>

## 市场微观结构：机构订单流与可执行性

关注身份可观察订单流、短样本年化、信号到达后的成交价和流动性供给关联；均价稳健性与实际执行验证分别阅读。

| 知识卡 | 来源 | 当前状态 |
| --- | --- | --- |
| [K-000043 · 机构订单流预测力与可执行性边界](../knowledge/K-000043.md) | [S-000045 · arXiv:2610.31141v1](../sources/S-000045.md) | draft / reported / not_attempted |

<a id="selective-auditing"></a>

## 人工智能可靠性：选择性审计与预算分配

区分期望之比、比例的期望和逐路径控制；主定理中的完美审计器、未截顶算法与实验设置不能互相替代。

| 知识卡 | 来源 | 当前状态 |
| --- | --- | --- |
| [K-000044 · 选择性审计与期望误差比](../knowledge/K-000044.md) | [S-000046 · arXiv:2610.31662v1](../sources/S-000046.md) | draft / reported / not_attempted |
