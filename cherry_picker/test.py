from unittest import mock

from .cherry_picker import get_base_branch, get_current_branch

def test_get_base_branch():
    cherry_pick_branch = 'backport-afc23f4-2.7'
    result = get_base_branch(cherry_pick_branch)
    assert result == '2.7'

def test_get_base_branch_without_dash():
    cherry_pick_branch ='master'
    result = get_base_branch(cherry_pick_branch)
    assert result == 'master'

@mock.patch('subprocess.check_output')
def test_get_current_branch(subprocess_check_output):
    subprocess_check_output.return_value = b'master'
    assert get_current_branch() == 'master'

