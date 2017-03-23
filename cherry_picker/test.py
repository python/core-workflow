from . import cherry_picker


def test_sorted_branch():
    branches = ["3.1", "2.7", "3.10", "3.6"]
    result = cherry_picker.get_sorted_branch(branches)
    assert result == ["3.10", "3.6", "3.1", "2.7"]
