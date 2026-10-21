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
