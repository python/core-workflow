import unittest.mock as mock


class AsyncContextManagerMock(mock.MagicMock):
    def __init__(self, return_item, *args, **kwargs):
        self.__dict__["return_item"] = return_item
        super().__init__(*args, **kwargs)

    async def __aenter__(self):
        return self.__dict__["return_item"]

    async def __aexit__(self, *args):
        pass


async def generate(iterable):
    for item in iterable:
        yield item


async def get_back(item):
    return item
