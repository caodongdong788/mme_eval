"""medeval 测试包。

声明 ``tests`` 为可导入包，便于 ``test_hard_gate_golden.py`` 中以
``from tests.golden.schema import GoldenCase, load_golden`` 的形式
跨模块复用 golden 集加载逻辑（``tests/golden/`` 已是子包）。

不在此处放任何运行时副作用——pytest 收集逻辑由 ``conftest.py`` 负责。
"""
