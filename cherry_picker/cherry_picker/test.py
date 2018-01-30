from unittest import mock

import pytest

from .cherry_picker import get_base_branch, get_current_branch, \
    get_full_sha_from_short, get_author_info_from_short_sha, \
    is_cpython_repo, CherryPicker, \
    normalize_commit_message


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


@mock.patch('subprocess.check_output')
def test_get_full_sha_from_short(subprocess_check_output):
    mock_output = b"""commit 22a594a0047d7706537ff2ac676cdc0f1dcb329c
tree 14ab2ea85e7a28adb9d40f185006308d87a67f47
parent 5908300e4b0891fc5ab8bd24fba8fac72012eaa7
author Armin Rigo <armin.rigo@gmail.com> 1492106895 +0200
committer Mariatta <Mariatta@users.noreply.github.com> 1492106895 -0700

    bpo-29694: race condition in pathlib mkdir with flags parents=True (GH-1089)

diff --git a/Lib/pathlib.py b/Lib/pathlib.py
index fc7ce5e..1914229 100644
--- a/Lib/pathlib.py
+++ b/Lib/pathlib.py
"""
    subprocess_check_output.return_value = mock_output
    assert get_full_sha_from_short('22a594a') == '22a594a0047d7706537ff2ac676cdc0f1dcb329c'


@mock.patch('subprocess.check_output')
def test_get_author_info_from_short_sha(subprocess_check_output):
    mock_output = b"Armin Rigo <armin.rigo@gmail.com>"
    subprocess_check_output.return_value = mock_output
    assert get_author_info_from_short_sha('22a594a') == 'Armin Rigo <armin.rigo@gmail.com>'


@mock.patch('os.path.exists')
def test_sorted_branch(os_path_exists):
    os_path_exists.return_value = True
    branches = ["3.1", "2.7", "3.10", "3.6"]
    cp = CherryPicker('origin', '22a594a0047d7706537ff2ac676cdc0f1dcb329c', branches)
    assert cp.sorted_branches == ["3.10", "3.6", "3.1", "2.7"]


@mock.patch('os.path.exists')
def test_get_cherry_pick_branch(os_path_exists):
    os_path_exists.return_value = True
    branches = ["3.6"]
    cp = CherryPicker('origin', '22a594a0047d7706537ff2ac676cdc0f1dcb329c', branches)
    assert cp.get_cherry_pick_branch("3.6") == "backport-22a594a-3.6"


@mock.patch('os.path.exists')
@mock.patch('subprocess.check_output')
def test_get_pr_url(subprocess_check_output, os_path_exists):
    os_path_exists.return_value = True
    subprocess_check_output.return_value = b'https://github.com/mock_user/cpython.git'
    branches = ["3.6"]
    cp = CherryPicker('origin', '22a594a0047d7706537ff2ac676cdc0f1dcb329c',
                      branches)
    assert cp.get_pr_url("3.6", cp.get_cherry_pick_branch("3.6")) \
           == "https://github.com/python/cpython/compare/3.6...mock_user:backport-22a594a-3.6?expand=1"


@pytest.mark.parametrize('url', [
    b'git@github.com:mock_user/cpython.git',
    b'git@github.com:mock_user/cpython',
    b'ssh://git@github.com/mock_user/cpython.git',
    b'ssh://git@github.com/mock_user/cpython',
    b'https://github.com/mock_user/cpython.git',
    b'https://github.com/mock_user/cpython',
    ])
def test_username(url):
    with mock.patch('subprocess.check_output', return_value=url):
        branches = ["3.6"]
        cp = CherryPicker('origin', '22a594a0047d7706537ff2ac676cdc0f1dcb329c',
                          branches)
        assert cp.username == 'mock_user'


@mock.patch('os.path.exists')
@mock.patch('subprocess.check_output')
def test_get_updated_commit_message(subprocess_check_output, os_path_exists):
    os_path_exists.return_value = True
    subprocess_check_output.return_value = b'bpo-123: Fix Spam Module (#113)'
    branches = ["3.6"]
    cp = CherryPicker('origin', '22a594a0047d7706537ff2ac676cdc0f1dcb329c',
                      branches)
    assert cp.get_commit_message('22a594a0047d7706537ff2ac676cdc0f1dcb329c') \
           == 'bpo-123: Fix Spam Module (GH-113)'

@mock.patch('subprocess.check_output')
def test_is_cpython_repo(subprocess_check_output):
    subprocess_check_output.return_value = """commit 7f777ed95a19224294949e1b4ce56bbffcb1fe9f
Author: Guido van Rossum <guido@python.org>
Date:   Thu Aug 9 14:25:15 1990 +0000

    Initial revision

"""
    assert is_cpython_repo() == True

def test_is_not_cpython_repo():
    assert is_cpython_repo() == False

def test_normalize_long_commit_message():
    commit_message = """[3.6] Fix broken `Show Source` links on documentation pages (GH-3113)

The `Show Source` was broken because of a change made in sphinx 1.5.1
In Sphinx 1.4.9, the sourcename was "index.txt".
In Sphinx 1.5.1+, it is now "index.rst.txt".
(cherry picked from commit b9ff498793611d1c6a9b99df464812931a1e2d69)

Co-authored-by: Elmar Ritsch <35851+elritsch@users.noreply.github.com>"""
    title, body = normalize_commit_message(commit_message)
    assert title == "[3.6] Fix broken `Show Source` links on documentation pages (GH-3113)"
    assert body == """The `Show Source` was broken because of a change made in sphinx 1.5.1
In Sphinx 1.4.9, the sourcename was "index.txt".
In Sphinx 1.5.1+, it is now "index.rst.txt".
(cherry picked from commit b9ff498793611d1c6a9b99df464812931a1e2d69)

Co-authored-by: Elmar Ritsch <35851+elritsch@users.noreply.github.com>"""

def test_normalize_short_commit_message():
    commit_message = """[3.6] Fix broken `Show Source` links on documentation pages (GH-3113)

(cherry picked from commit b9ff498793611d1c6a9b99df464812931a1e2d69)

Co-authored-by: Elmar Ritsch <35851+elritsch@users.noreply.github.com>"""
    title, body = normalize_commit_message(commit_message)
    assert title == "[3.6] Fix broken `Show Source` links on documentation pages (GH-3113)"
    assert body == """(cherry picked from commit b9ff498793611d1c6a9b99df464812931a1e2d69)

Co-authored-by: Elmar Ritsch <35851+elritsch@users.noreply.github.com>"""