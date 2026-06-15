"""飞书电子表格 → TestCase YAML 导入脚本。

用法:
  python scripts/import_benchmark_from_feishu.py \\
    --sheet-url "https://xxx.feishu.cn/sheets/shtcn..." \\
    --out cases/imported/from_sheet.yaml

等价于: medeval import-feishu ...
"""

from medeval.import_feishu.cli import import_feishu_cmd

if __name__ == "__main__":
    import_feishu_cmd()
