import os
import tempfile
from pathlib import Path
import pandas as pd
from syscore.exceptions import missingFile
from syscore.fileutils import (
    files_with_extension_in_resolved_pathname,
    resolve_path_and_filename_for_package,
    get_resolved_pathname,
)

PARQUET_WRITE_OPTIONS = dict(
    coerce_timestamps="us", allow_truncated_timestamps=True
)
TEMP_FILE_SUFFIX = ".tmp"


class ParquetAccess(object):
    def __init__(self, parquet_store_path: str):
        """
        Initialises an instance of the ParquetAccess class responsible for handling
        the location of a Parquet data store

        :param parquet_store_path: path to the Parquet data store
        :type parquet_store_path: str
        """
        self.accessor = LocalAccessor(parquet_store_path)

    def get_all_identifiers_with_data_type(self, data_type: str):
        return self.accessor.identifiers_for_type(data_type)

    def does_identifier_with_data_type_exist(
        self, data_type: str, identifier: str
    ) -> bool:
        filename = self.accessor.get_filename_given_data_type_and_identifier(
            data_type=data_type, identifier=identifier
        )
        return Path(filename).exists()

    def delete_data_given_data_type_and_identifier(
        self, data_type: str, identifier: str
    ):
        filename = self.accessor.get_filename_given_data_type_and_identifier(
            data_type=data_type, identifier=identifier
        )
        try:
            Path(filename).unlink()
        except FileNotFoundError:
            raise missingFile(f"File '{filename}' does not exist")

    def write_data_given_data_type_and_identifier(
        self, data_to_write: pd.DataFrame, data_type: str, identifier: str
    ):
        filename = self.accessor.get_filename_given_data_type_and_identifier(
            data_type=data_type, identifier=identifier
        )
        write_parquet_atomically(data_to_write, filename)

    def read_data_given_data_type_and_identifier(
        self, data_type: str, identifier: str
    ) -> pd.DataFrame:
        filename = self.accessor.get_filename_given_data_type_and_identifier(
            data_type=data_type, identifier=identifier
        )
        return pd.read_parquet(filename)


def write_parquet_atomically(data_to_write: pd.DataFrame, filename) -> None:
    """
    原子写 parquet：先写同目录下的临时文件，写完再 os.replace 覆盖目标文件。

    直接 to_parquet(目标文件) 时，写入过程中断（Ctrl-C、进程被杀、外置卷掉线）会留下
    损坏的半个文件；FIR-137 事故伤到的正是这类单文件。临时文件与目标同目录，
    保证 os.replace 是同文件系统内的原子 rename。任何异常都会清理临时文件。
    """
    target = Path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)

    handle, temp_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=target.name + ".", suffix=TEMP_FILE_SUFFIX
    )
    os.close(handle)
    temp_path = Path(temp_name)

    try:
        data_to_write.to_parquet(str(temp_path), **PARQUET_WRITE_OPTIONS)
        os.replace(temp_path, target)
    except BaseException:
        _remove_temp_file(temp_path)
        raise


def _remove_temp_file(temp_path: Path) -> None:
    try:
        temp_path.unlink()
    except FileNotFoundError:
        pass


class LocalAccessor:
    EXTENSION = "parquet"

    def __init__(self, parquet_path: str):
        self._base_path = get_resolved_pathname(parquet_path)

    def identifiers_for_type(self, data_type: str):
        path = self.get_pathname_given_data_type(data_type)
        return files_with_extension_in_resolved_pathname(path, extension=self.EXTENSION)

    def get_filename_given_data_type_and_identifier(
        self, data_type: str, identifier: str
    ):
        path = self.get_pathname_given_data_type(data_type)
        filename = resolve_path_and_filename_for_package(
            path, separate_filename=f"{identifier}.{self.EXTENSION}"
        )
        return filename

    def get_pathname_given_data_type(self, data_type: str):
        path = Path(self._base_path, data_type)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
