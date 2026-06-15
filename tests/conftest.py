"""pytest 配置 —— 防止把领域模型 `TestCase` 当成 pytest 测试类。"""

collect_ignore_glob = []


def pytest_collection_modifyitems(config, items):
    # 不需要做任何事，TestCase 不在 tests/ 目录下就不会被收集
    pass
