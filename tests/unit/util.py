from unittest import mock


def _any_factory(base_class):
    """

    ToDo: I should make this a metaclass instead
    """
    class Any(base_class):
        def __eq__(self, other):
            if isinstance(other, base_class):
                return True
            return False
    return Any()

AnyInt = _any_factory(int)
AnyDict = _any_factory(dict)
AnyList = _any_factory(list)
AnyMock = _any_factory(mock.Mock)
AnyStr = _any_factory(str)

class _AnyListOfStrings(list):
    def __eq__(self, other):
        return isinstance(other, list) and all(isinstance(el, str) for el in other)

AnyListOfStrings = _AnyListOfStrings()
