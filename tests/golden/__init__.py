"""HardGate 启发式回归测试黄金集。

每条用例都是手工 review 过的正/反例（包含一段 bot 回复 + 该回复期望的 HardGate
verdict）。修改 hard_gate.py 关键词表后必须确保本黄金集仍然全部通过；新增 / 改动
关键词表时应同步补充黄金集中的边界用例。

详见 ``docs/heuristics-changelog.md`` 与 ``govern-hard-gate-heuristics`` 提案。
"""
