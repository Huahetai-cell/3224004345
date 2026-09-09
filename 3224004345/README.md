# 论文查重（3224004345）

一个面向中文论文增删改场景的命令行查重程序。程序使用 Python 3 标准库实现，运行时无第三方依赖、无网络访问，只读写命令行指定的文件。

## 运行环境

- Python 3.10 或更高版本
- Windows、macOS 或 Linux

安装运行依赖（文件为空是正常情况）：

```powershell
python -m pip install -r requirements.txt
```

## 使用方法

```powershell
python main.py C:\tests\orig.txt C:\tests\orig_add.txt C:\tests\ans.txt
```

三个参数依次是原文文件、抄袭版文件和答案文件。输入支持 UTF-8、带 BOM 的 UTF-8 和 GB18030。成功后答案文件只包含 `0.00` 到 `1.00` 范围内的两位小数。

需求文档中的示例输出为：

```text
0.64
```

退出码：成功为 0，文件或编码错误为 1，参数数量错误为 2。

## 算法概述

程序先统一字符宽度和英文大小写，并移除空白、标点、符号。随后分别计算字符一元组和二元组的多重集 Sørensen–Dice 系数，按 20% 和 80% 加权。最终版本使用 `collections.Counter` 求多重集交集，时间复杂度为 O(n)，空间复杂度为 O(n)。

详细接口、数据流和异常策略见 [docs/设计说明.md](docs/设计说明.md)。

## 测试与质量检查

安装开发依赖：

```powershell
python -m pip install -r requirements-dev.txt
```

执行全部检查：

```powershell
python -m unittest discover -v
python -m coverage run --branch -m unittest discover
python -m coverage report -m
python -m ruff check .
python -m compileall -q .
```

当前共有 20 个自动化测试；核心模块语句覆盖率和分支覆盖率均为 100%。测试说明见 [docs/测试报告.md](docs/测试报告.md)。

## 性能分析

```powershell
python -m tools.generate_evidence
```

在本机 Python 3.13 环境中，15,400 字符分析样本从朴素列表匹配的 1.109 秒降至 `Counter` 实现的 0.147 秒，结果完全一致，提速约 7.55 倍。1 MiB 文本正常运行耗时约 0.890 秒，诊断得到的峰值内存约 117.15 MiB。

完整数据和截图见 [docs/性能分析.md](docs/性能分析.md)。

## 项目结构

```text
3224004345/
├── main.py                    # 评测入口
├── paper_checker.py           # 计算模块
├── tests/                     # unittest 自动化测试
├── tools/generate_evidence.py # 性能证据生成脚本
├── reports/evidence/          # cProfile、覆盖率数据和截图
├── docs/                      # 需求、设计、PSP、报告、博客草稿
├── requirements.txt           # 运行依赖
└── requirements-dev.txt       # 开发工具依赖
```

## 限制

题目没有规定唯一的重复率算法，也没有提供18个隐藏测试点的期望结果。本项目选择确定、可解释的字符 n-gram 方法；现有验收结论来自需求样例、自建测试和本地性能基准。

