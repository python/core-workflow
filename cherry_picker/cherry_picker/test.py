import os
import pathlib
import subprocess
from collections import ChainMap
from unittest import mock

import pytest

from .cherry_picker import get_base_branch, get_current_branch, \
    get_full_sha_from_short, get_author_info_from_short_sha, \
    CherryPicker, InvalidRepoException, CherryPickException, \
    normalize_commit_message, DEFAULT_CONFIG, \
    get_sha1_from, find_config, load_config, validate_sha, \
    from_git_rev_read, \
    reset_state, set_state, get_state, \
    load_val_from_git_cfg, reset_stored_config_ref


@pytest.fixture
def config():
    check_sha = 'dc896437c8efe5a4a5dfa50218b7a6dc0cbe2598'
    return ChainMap(DEFAULT_CONFIG).new_child({'check_sha': check_sha})


@pytest.fixture
def cd():
    cwd = os.getcwd()

    def changedir(d):
        os.chdir(d)

    yield changedir

    # restore CWD back
    os.chdir(cwd)


@pytest.fixture
def git_init():
    git_init_cmd = 'git', 'init', '.'
    return lambda: subprocess.run(git_init_cmd, check=True)


@pytest.fixture
def git_add():
    git_add_cmd = 'git', 'add'
    return lambda *extra_args: (
        subprocess.run(git_add_cmd + extra_args, check=True)
    )


@pytest.fixture
def git_checkout():
    git_checkout_cmd = 'git', 'checkout'
    return lambda *extra_args: (
        subprocess.run(git_checkout_cmd + extra_args, check=True)
    )


@pytest.fixture
def git_branch():
    git_branch_cmd = 'git', 'branch'
    return lambda *extra_args: (
        subprocess.run(git_branch_cmd + extra_args, check=True)
    )


@pytest.fixture
def git_commit():
    git_commit_cmd = 'git', 'commit', '-m'
    return lambda msg, *extra_args: (
        subprocess.run(git_commit_cmd + (msg, ) + extra_args, check=True)
    )


@pytest.fixture
def tmp_git_repo_dir(tmpdir, cd, git_init, git_commit):
    cd(tmpdir)
    git_init()
    git_commit('Initial commit', '--allow-empty')
    yield tmpdir


@mock.patch('subprocess.check_output')
def test_get_base_branch(subprocess_check_output):
    # The format of cherry-pick branches we create are::
    #     backport-{SHA}-{base_branch}
    subprocess_check_output.return_value = b'22a594a0047d7706537ff2ac676cdc0f1dcb329c'
    cherry_pick_branch = 'backport-22a594a-2.7'
    result = get_base_branch(cherry_pick_branch)
    assert result == '2.7'


@mock.patch('subprocess.check_output')
def test_get_base_branch_which_has_dashes(subprocess_check_output):
    subprocess_check_output.return_value = b'22a594a0047d7706537ff2ac676cdc0f1dcb329c'
    cherry_pick_branch = 'backport-22a594a-baseprefix-2.7-basesuffix'
    result = get_base_branch(cherry_pick_branch)
    assert result == 'baseprefix-2.7-basesuffix'


@pytest.mark.parametrize('cherry_pick_branch', ['backport-22a594a',  # Not enough fields
                                                'prefix-22a594a-2.7',  # Not the prefix we were expecting
                                                'backport-22a594a-base',  # No version info in the base branch
                                                ]
                         )
@mock.patch('subprocess.check_output')
def test_get_base_branch_invalid(subprocess_check_output, cherry_pick_branch):
    subprocess_check_output.return_value = b'22a594a0047d7706537ff2ac676cdc0f1dcb329c'
    with pytest.raises(ValueError):
        get_base_branch(cherry_pick_branch)


@mock.patch('subprocess.check_output')
def test_get_current_branch(subprocess_check_output):
    subprocess_check_output.return_value = b'master'
    assert get_current_branch() == 'master'


@mock.patch('subprocess.check_output')
def test_get_full_sha_from_short(subprocess_check_output):
    mock_output = b"""22a594a0047d7706537ff2ac676cdc0f1dcb329c"""
    subprocess_check_output.return_value = mock_output
    assert get_full_sha_from_short('22a594a') == '22a594a0047d7706537ff2ac676cdc0f1dcb329c'


@mock.patch('subprocess.check_output')
def test_get_author_info_from_short_sha(subprocess_check_output):
    mock_output = b"Armin Rigo <armin.rigo@gmail.com>"
    subprocess_check_output.return_value = mock_output
    assert get_author_info_from_short_sha('22a594a') == 'Armin Rigo <armin.rigo@gmail.com>'


@pytest.mark.parametrize('input_branches,sorted_branches', [
    (['3.1', '2.7', '3.10', '3.6'], ['3.10', '3.6', '3.1', '2.7']),
    (['stable-3.1', 'lts-2.7', '3.10-other', 'smth3.6else'], ['3.10-other', 'smth3.6else', 'stable-3.1', 'lts-2.7']),
])
@mock.patch('os.path.exists')
def test_sorted_branch(os_path_exists, config, input_branches, sorted_branches):
    os_path_exists.return_value = True
    cp = CherryPicker('origin', '22a594a0047d7706537ff2ac676cdc0f1dcb329c',
                      input_branches, config=config)
    assert cp.sorted_branches == sorted_branches


@pytest.mark.parametrize('input_branches', [
    (['3.1', '2.7', '3.x10', '3.6', '']),
    (['stable-3.1', 'lts-2.7', '3.10-other', 'smth3.6else', 'invalid']),
])
@mock.patch('os.path.exists')
def test_invalid_branches(os_path_exists, config, input_branches):
    os_path_exists.return_value = True
    cp = CherryPicker('origin', '22a594a0047d7706537ff2ac676cdc0f1dcb329c',
                      input_branches, config=config)
    with pytest.raises(ValueError):
        cp.sorted_branches


@mock.patch('os.path.exists')
def test_get_cherry_pick_branch(os_path_exists, config):
    os_path_exists.return_value = True
    branches = ["3.6"]
    cp = CherryPicker('origin', '22a594a0047d7706537ff2ac676cdc0f1dcb329c',
                      branches, config=config)
    assert cp.get_cherry_pick_branch("3.6") == "backport-22a594a-3.6"


def test_get_pr_url(config):
    branches = ["3.6"]
    cp = CherryPicker('origin', '22a594a0047d7706537ff2ac676cdc0f1dcb329c',
                      branches, config=config)
    backport_target_branch = cp.get_cherry_pick_branch("3.6")
    expected_pr_url = (
        'https://github.com/python/cpython/compare/'
        '3.6...mock_user:backport-22a594a-3.6?expand=1'
    )
    with mock.patch(
            'subprocess.check_output',
            return_value=b'https://github.com/mock_user/cpython.git',
    ):
        actual_pr_url = cp.get_pr_url("3.6", backport_target_branch)

    assert actual_pr_url == expected_pr_url


@pytest.mark.parametrize('url', [
    b'git@github.com:mock_user/cpython.git',
    b'git@github.com:mock_user/cpython',
    b'ssh://git@github.com/mock_user/cpython.git',
    b'ssh://git@github.com/mock_user/cpython',
    b'https://github.com/mock_user/cpython.git',
    b'https://github.com/mock_user/cpython',
    ])
def test_username(url, config):
    branches = ["3.6"]
    cp = CherryPicker('origin', '22a594a0047d7706537ff2ac676cdc0f1dcb329c',
                      branches, config=config)
    with mock.patch('subprocess.check_output', return_value=url):
        assert cp.username == 'mock_user'


def test_get_updated_commit_message(config):
    branches = ["3.6"]
    cp = CherryPicker('origin', '22a594a0047d7706537ff2ac676cdc0f1dcb329c',
                      branches, config=config)
    with mock.patch(
            'subprocess.check_output',
            return_value=b'bpo-123: Fix Spam Module (#113)',
    ):
        actual_commit_message = (
            cp.get_commit_message('22a594a0047d7706537ff2ac676cdc0f1dcb329c')
        )
    assert actual_commit_message == 'bpo-123: Fix Spam Module (GH-113)'


def test_get_updated_commit_message_without_links_replacement(config):
    config['fix_commit_msg'] = False
    branches = ["3.6"]
    cp = CherryPicker('origin', '22a594a0047d7706537ff2ac676cdc0f1dcb329c',
                      branches, config=config)
    with mock.patch(
            'subprocess.check_output',
            return_value=b'bpo-123: Fix Spam Module (#113)',
    ):
        actual_commit_message = (
            cp.get_commit_message('22a594a0047d7706537ff2ac676cdc0f1dcb329c')
        )
    assert actual_commit_message == 'bpo-123: Fix Spam Module (#113)'


@mock.patch('subprocess.check_output')
def test_is_cpython_repo(subprocess_check_output):
    subprocess_check_output.return_value = """commit 7f777ed95a19224294949e1b4ce56bbffcb1fe9f
Author: Guido van Rossum <guido@python.org>
Date:   Thu Aug 9 14:25:15 1990 +0000

    Initial revision

"""
    # should not raise an exception
    validate_sha('22a594a0047d7706537ff2ac676cdc0f1dcb329c')


def test_is_not_cpython_repo():
    # use default CPython sha to fail on this repo
    with pytest.raises(InvalidRepoException):
        CherryPicker('origin', '22a594a0047d7706537ff2ac676cdc0f1dcb329c',
                     ["3.6"])


def test_find_config(tmpdir, cd):
    cd(tmpdir)
    subprocess.run('git init .'.split(), check=True)
    relative_config_path = '.cherry_picker.toml'
    cfg = tmpdir.join(relative_config_path)
    cfg.write('param = 1')
    subprocess.run('git add .'.split(), check=True)
    subprocess.run(('git', 'commit', '-m', 'Initial commit'), check=True)
    scm_revision = get_sha1_from('HEAD')
    assert find_config(scm_revision) == scm_revision + ':' + relative_config_path


def test_find_config_not_found(tmpdir, cd):
    cd(tmpdir)
    subprocess.run('git init .'.split(), check=True)
    subprocess.run(('git', 'commit', '-m', 'Initial commit', '--allow-empty'), check=True)
    scm_revision = get_sha1_from('HEAD')
    assert find_config(scm_revision) is None


def test_find_config_not_git(tmpdir, cd):
    cd(tmpdir)
    assert find_config(None) is None


def test_load_full_config(tmpdir, cd):
    cd(tmpdir)
    subprocess.run('git init .'.split(), check=True)
    relative_config_path = '.cherry_picker.toml'
    cfg = tmpdir.join(relative_config_path)
    cfg.write('''\
    team = "python"
    repo = "core-workfolow"
    check_sha = "5f007046b5d4766f971272a0cc99f8461215c1ec"
    default_branch = "devel"
    ''')
    subprocess.run('git add .'.split(), check=True)
    subprocess.run(('git', 'commit', '-m', 'Initial commit'), check=True)
    scm_revision = get_sha1_from('HEAD')
    cfg = load_config(None)
    assert cfg == (
        scm_revision + ':' + relative_config_path,
        {
            'check_sha': '5f007046b5d4766f971272a0cc99f8461215c1ec',
            'repo': 'core-workfolow',
            'team': 'python',
            'fix_commit_msg': True,
            'default_branch': 'devel',
        },
    )


def test_load_partial_config(tmpdir, cd):
    cd(tmpdir)
    subprocess.run('git init .'.split(), check=True)
    relative_config_path = '.cherry_picker.toml'
    cfg = tmpdir.join(relative_config_path)
    cfg.write('''\
    repo = "core-workfolow"
    ''')
    subprocess.run('git add .'.split(), check=True)
    subprocess.run(('git', 'commit', '-m', 'Initial commit'), check=True)
    scm_revision = get_sha1_from('HEAD')
    cfg = load_config(relative_config_path)
    assert cfg == (
        scm_revision + ':' + relative_config_path,
        {
            'check_sha': '7f777ed95a19224294949e1b4ce56bbffcb1fe9f',
            'repo': 'core-workfolow',
            'team': 'python',
            'fix_commit_msg': True,
            'default_branch': 'master',
        },
    )


def test_load_config_no_head_sha(tmp_git_repo_dir, git_add, git_commit):
    relative_config_path = '.cherry_picker.toml'
    tmp_git_repo_dir.join(relative_config_path).write('''\
    team = "python"
    repo = "core-workfolow"
    check_sha = "5f007046b5d4766f971272a0cc99f8461215c1ec"
    default_branch = "devel"
    ''')
    git_add(relative_config_path)
    git_commit(f'Add {relative_config_path}')
    scm_revision = get_sha1_from('HEAD')

    with mock.patch(
            'cherry_picker.cherry_picker.get_sha1_from',
            return_value='',
    ):
        cfg = load_config(relative_config_path)

    assert cfg == (
        ':' + relative_config_path,
        {
            'check_sha': '5f007046b5d4766f971272a0cc99f8461215c1ec',
            'repo': 'core-workfolow',
            'team': 'python',
            'fix_commit_msg': True,
            'default_branch': 'devel',
        },
    )


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


@pytest.mark.parametrize(
    'input_path',
    (
        '/some/path/without/revision',
        'HEAD:some/non-existent/path',
    ),
)
def test_from_git_rev_read_negative(
    input_path, tmp_git_repo_dir,
):
    with pytest.raises(ValueError):
        from_git_rev_read(input_path)


def test_from_git_rev_read_uncommitted(tmp_git_repo_dir, git_add, git_commit):
    some_text = 'blah blah 🤖'
    relative_file_path = '.some.file'
    tmp_git_repo_dir.join(relative_file_path).write(some_text)
    git_add('.')
    with pytest.raises(ValueError):
        from_git_rev_read('HEAD:' + relative_file_path) == some_text


def test_from_git_rev_read(tmp_git_repo_dir, git_add, git_commit):
    some_text = 'blah blah 🤖'
    relative_file_path = '.some.file'
    tmp_git_repo_dir.join(relative_file_path).write(some_text)
    git_add('.')
    git_commit('Add some file')
    assert from_git_rev_read('HEAD:' + relative_file_path) == some_text


def test_states(tmp_git_repo_dir):
    state_val = 'somerandomwords'

    # First, verify that there's nothing there initially
    assert get_state() == 'UNSET'

    # Now, set some val
    set_state(state_val)
    assert get_state() == state_val

    # Wipe it again
    reset_state()
    assert get_state() == 'UNSET'


def test_paused_flow(tmp_git_repo_dir, git_add, git_commit):
    assert load_val_from_git_cfg('config_path') is None
    initial_scm_revision = get_sha1_from('HEAD')

    relative_file_path = 'some.toml'
    tmp_git_repo_dir.join(relative_file_path).write(f'''\
    check_sha = "{initial_scm_revision}"
    repo = "core-workfolow"
    ''')
    git_add(relative_file_path)
    git_commit('Add a config')
    config_scm_revision = get_sha1_from('HEAD')

    config_path_rev = config_scm_revision + ':' + relative_file_path
    chosen_config_path, config = load_config(config_path_rev)

    cherry_picker = CherryPicker(
        'origin', config_scm_revision, [], config=config,
        chosen_config_path=chosen_config_path,
    )
    assert get_state() == 'UNSET'

    cherry_picker.set_paused_state()
    assert load_val_from_git_cfg('config_path') == config_path_rev
    assert get_state() == 'BACKPORT_PAUSED'

    chosen_config_path, config = load_config(None)
    assert chosen_config_path == config_path_rev

    reset_stored_config_ref()
    assert load_val_from_git_cfg('config_path') is None


@pytest.mark.parametrize(
    'method_name,start_state,end_state',
    (
        ('fetch_upstream', 'FETCHING_UPSTREAM', 'FETCHED_UPSTREAM'),
        (
            'checkout_default_branch',
            'CHECKING_OUT_DEFAULT_BRANCH', 'CHECKED_OUT_DEFAULT_BRANCH',
        ),
    ),
)
def test_start_end_states(
    method_name, start_state, end_state,
    tmp_git_repo_dir,
):
    assert get_state() == 'UNSET'

    with mock.patch(
            'cherry_picker.cherry_picker.validate_sha',
            return_value=True,
    ):
        cherry_picker = CherryPicker('origin', 'xxx', [])
    assert get_state() == 'UNSET'

    def _fetch(cmd):
        assert get_state() == start_state

    with mock.patch.object(cherry_picker, 'run_cmd', _fetch):
        getattr(cherry_picker, method_name)()
    assert get_state() == end_state


def test_cleanup_branch(
    tmp_git_repo_dir, git_checkout,
):
    assert get_state() == 'UNSET'

    with mock.patch(
        'cherry_picker.cherry_picker.validate_sha',
        return_value=True,
    ):
        cherry_picker = CherryPicker('origin', 'xxx', [])
    assert get_state() == 'UNSET'

    git_checkout('-b', 'some_branch')
    cherry_picker.cleanup_branch('some_branch')
    assert get_state() == 'REMOVED_BACKPORT_BRANCH'


def test_cleanup_branch_fail(tmp_git_repo_dir):
    assert get_state() == 'UNSET'

    with mock.patch(
        'cherry_picker.cherry_picker.validate_sha',
        return_value=True,
    ):
        cherry_picker = CherryPicker('origin', 'xxx', [])
    assert get_state() == 'UNSET'

    cherry_picker.cleanup_branch('some_branch')
    assert get_state() == 'REMOVING_BACKPORT_BRANCH_FAILED'


def test_cherry_pick(
    tmp_git_repo_dir, git_add, git_branch, git_commit, git_checkout,
):
    cherry_pick_target_branches = '3.8',
    pr_remote = 'origin'
    test_file = 'some.file'
    tmp_git_repo_dir.join(test_file).write('some contents')
    git_branch(cherry_pick_target_branches[0])
    git_branch(
        f'{pr_remote}/{cherry_pick_target_branches[0]}',
        cherry_pick_target_branches[0],
    )
    git_add(test_file)
    git_commit('Add a test file')
    scm_revision = get_sha1_from('HEAD')

    git_checkout(  # simulate backport method logic
        cherry_pick_target_branches[0],
    )

    with mock.patch(
        'cherry_picker.cherry_picker.validate_sha',
        return_value=True,
    ):
        cherry_picker = CherryPicker(
            pr_remote,
            scm_revision,
            cherry_pick_target_branches,
        )

    cherry_picker.cherry_pick()


def test_cherry_pick_fail(
    tmp_git_repo_dir,
):
    with mock.patch(
        'cherry_picker.cherry_picker.validate_sha',
        return_value=True,
    ):
        cherry_picker = CherryPicker('origin', 'xxx', [])

    with pytest.raises(CherryPickException, message='Error cherry-pick xxx.'):
        cherry_picker.cherry_pick()


def test_get_state_and_verify_fail(
    tmp_git_repo_dir,
):
    tested_state = 'invalid_state'
    set_state(tested_state)

    expected_msg_regexp = (
        fr'^Run state cherry-picker.state={tested_state} in Git config '
        r'is not known.'
        '\n'
        r'Perhaps it has been set by a newer '
        r'version of cherry-picker\. Try upgrading\.'
        '\n'
        r'Valid states are: '
        r'[\w_\s]+(, [\w_\s]+)*\. '
        r'If this looks suspicious, raise an issue at '
        r'https://github.com/python/core-workflow/issues/new\.'
        '\n'
        r'As the last resort you can reset the runtime state '
        r'stored in Git config using the following command: '
        r'`git config --local --remove-section cherry-picker`'
    )
    with \
            mock.patch(
                'cherry_picker.cherry_picker.validate_sha',
                return_value=True,
            ), \
            pytest.raises(ValueError, match=expected_msg_regexp):
        cherry_picker = CherryPicker('origin', 'xxx', [])
