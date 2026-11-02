"""
仓库根目录的 pytest 配置，对所有测试生效，包括 --doctest-modules 收集的上游 doctest。
"""

import numpy as np


def pytest_configure(config):
    # numpy 2 把标量显示成 np.int64(2)、np.True_；上游 doctest 是按 numpy 1.x 的写法写的
    np.set_printoptions(legacy="1.25")
