from sysdata.data_blob import dataBlob
from syscore.constants import arg_not_supplied
from syscore.cache import Cache


class productionDataLayerGeneric(object):
    def __init__(self, data: dataBlob = arg_not_supplied):
        if data is arg_not_supplied:
            data = dataBlob()

        data = self._add_required_classes_to_data(data)
        self._data = data
        self._cache = Cache(self)

    @property
    def cache(self) -> Cache:
        return self._cache

    @property
    def data(self) -> dataBlob:
        return self._data

    @property
    def log(self):
        return self.data.log

    def read_through(self, key, calculate):
        """
        Return calculate() but memoise the result on the data blob when its
        read cache is enabled (see dataBlob.enable_read_cache).

        :param key: hashable cache key
        :param calculate: callable that returns the value if not cached
        """
        read_cache = self.data.read_cache
        if read_cache is None:
            return calculate()

        if key not in read_cache:
            read_cache[key] = calculate()

        return read_cache[key]

    def _add_required_classes_to_data(self, data) -> dataBlob:
        return data
