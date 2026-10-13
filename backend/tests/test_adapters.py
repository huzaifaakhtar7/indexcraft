import pytest

from adapters.factory import get_adapter


def test_unknown_database_rejected():
    with pytest.raises(ValueError):
        get_adapter("oracle")
