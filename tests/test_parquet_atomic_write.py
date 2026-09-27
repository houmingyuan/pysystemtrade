"""
parquet 写入原子化的回归测试（FIR-160）。

写入走「同目录临时文件 → os.replace」，中途失败不能动到目标文件、也不能留下临时文件。
"""

from pathlib import Path

import pandas as pd
import pytest

from sysdata.parquet.parquet_access import (
    ParquetAccess,
    write_parquet_atomically,
)

DATA_TYPE = "multiple_prices"
IDENTIFIER = "TEST"


def _store_dir(tmp_path) -> Path:
    store = tmp_path / "store"
    store.mkdir()
    return store


def _leftover_temp_files(directory: Path):
    return sorted(path.name for path in directory.rglob("*.tmp"))


def _prices(values, dates=("2026-09-25", "2026-09-26")):
    return pd.DataFrame(
        dict(FINAL=[float(value) for value in values]),
        index=pd.to_datetime(list(dates)),
    )


def test_write_through_access_class_is_complete_and_leaves_no_temp_file(tmp_path):
    access = ParquetAccess(_store_dir(tmp_path))
    data = _prices([1.0, 2.0])

    access.write_data_given_data_type_and_identifier(data, DATA_TYPE, IDENTIFIER)

    stored = access.read_data_given_data_type_and_identifier(DATA_TYPE, IDENTIFIER)
    assert stored["FINAL"].tolist() == [1.0, 2.0]
    assert _leftover_temp_files(tmp_path) == []


def test_atomic_write_replaces_existing_file(tmp_path):
    target = _store_dir(tmp_path) / "prices.parquet"
    write_parquet_atomically(_prices([1.0, 2.0]), target)

    write_parquet_atomically(_prices([9.0, 8.0]), target)

    assert pd.read_parquet(target)["FINAL"].tolist() == [9.0, 8.0]
    assert _leftover_temp_files(tmp_path) == []


def test_interrupted_write_keeps_previous_file_and_cleans_temp(tmp_path, monkeypatch):
    target = _store_dir(tmp_path) / "prices.parquet"
    write_parquet_atomically(_prices([1.0, 2.0]), target)

    def half_written_then_crash(self, path, **kwargs):
        Path(path).write_bytes(b"partial garbage")  # 模拟写到一半被打断
        raise IOError("device not configured")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", half_written_then_crash)

    with pytest.raises(IOError):
        write_parquet_atomically(_prices([9.0, 8.0]), target)

    # 目标文件仍是旧的完整数据，损坏的临时文件已清理
    assert pd.read_parquet(target)["FINAL"].tolist() == [1.0, 2.0]
    assert _leftover_temp_files(tmp_path) == []
