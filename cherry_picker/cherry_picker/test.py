import os
import pathlib
import subprocess
from collections import ChainMap
from unittest import mock

import pytest
import click

from .cherry_picker import (
    get_base_branch,
    get_current_branch,
    get_full_sha_from_short,
    get_author_info_from_short_sha,
    CherryPicker,
    InvalidRepoException,
    CherryPickException,
    normalize_commit_message,
    DEFAULT_CONFIG,
    get_sha1_from,
    find_config,
    load_config,
    validate_sha,
    from_git_rev_read,
    reset_state,
    set_state,
    get_state,
    load_val_from_git_cfg,
    reset_stored_config_ref,
    WORKFLOW_STATES,
)


@pytest.fixture
def config():
    check_sha = "dc896437c8efe5a4a5dfa50218b7a6dc0cbe2598"
    return ChainMap(DEFAULT_CONFIG).new_child({"check_sha": check_sha})


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
    git_init_cmd = "git", "init", "."
    return lambda: subprocess.run(git_init_cmd, check=True)


@pytest.fixture
def git_add():
    git_add_cmd = "git", "add"
    return lambda *extra_args: (subprocess.run(git_add_cmd + extra_args, check=True))


@pytest.fixture
def git_checkout():
    git_checkout_cmd = "git", "checkout"
    return lambda *extra_args: (
        subprocess.run(git_checkout_cmd + extra_args, check=True)
    )


@pytest.fixture
def git_branch():
    git_branch_cmd = "git", "branch"
    return lambda *extra_args: (subprocess.run(git_branch_cmd + extra_args, check=True))


@pytest.fixture
def git_commit():
    git_commit_cmd = "git", "commit", "-m"
    return lambda msg, *extra_args: (
        subprocess.run(git_commit_cmd + (msg,) + extra_args, check=True)
    )


@pytest.fixture
def git_cherry_pick():
    git_cherry_pick_cmd = "git", "cherry-pick"
    return lambda *extra_args: (
        subprocess.run(git_cherry_pick_cmd + extra_args, check=True)
    )


@pytest.fixture
def git_config():
    git_config_cmd = "git", "config"
    return lambda *extra_args: (subprocess.run(git_config_cmd + extra_args, check=True))


@pytest.fixture
def tmp_git_repo_dir(tmpdir, cd, git_init, git_commit, git_config):
    cd(tmpdir)
    git_init()
    git_config("--local", "user.name", "Monty Python")
    git_config("--local", "user.email", "bot@python.org")
    git_commit("Initial commit", "--allow-empty")
    yield tmpdir


@mock.patch("subprocess.check_output")
def test_get_base_branch(subprocess_check_output):
    # The format of cherry-pick branches we create are::
    #     backport-{SHA}-{base_branch}
    subprocess_check_output.return_value = b"22a594a0047d7706537ff2ac676cdc0f1dcb329c"
    cherry_pick_branch = "backport-22a594a-2.7"
    result = get_base_branch(cherry_pick_branch)
    assert result == "2.7"


@mock.patch("subprocess.check_output")
def test_get_base_branch_which_has_dashes(subprocess_check_output):
    subprocess_check_output.return_value = b"22a594a0047d7706537ff2ac676cdc0f1dcb329c"
    cherry_pick_branch = "backport-22a594a-baseprefix-2.7-basesuffix"
    result = get_base_branch(cherry_pick_branch)
    assert result == "baseprefix-2.7-basesuffix"


@pytest.mark.parametrize(
    "cherry_pick_branch",
    [
        "backport-22a594a",  # Not enough fields
        "prefix-22a594a-2.7",  # Not the prefix we were expecting
        "backport-22a594a-base",  # No version info in the base branch
    ],
)
@mock.patch("subprocess.check_output")
def test_get_base_branch_invalid(subprocess_check_output, cherry_pick_branch):
    subprocess_check_output.return_value = b"22a594a0047d7706537ff2ac676cdc0f1dcb329c"
    with pytest.raises(ValueError):
        get_base_branch(cherry_pick_branch)


@mock.patch("subprocess.check_output")
def test_get_current_branch(subprocess_check_output):
    subprocess_check_output.return_value = b"master"
    assert get_current_branch() == "master"


@mock.patch("subprocess.check_output")
def test_get_full_sha_from_short(subprocess_check_output):
    mock_output = b"""22a594a0047d7706537ff2ac676cdc0f1dcb329c"""
    subprocess_check_output.return_value = mock_output
    assert (
        get_full_sha_from_short("22a594a") == "22a594a0047d7706537ff2ac676cdc0f1dcb329c"
    )


@mock.patch("subprocess.check_output")
def test_get_author_info_from_short_sha(subprocess_check_output):
    mock_output = b"Armin Rigo <armin.rigo@gmail.com>"
    subprocess_check_output.return_value = mock_output
    assert (
        get_author_info_from_short_sha("22a594a") == "Armin Rigo <armin.rigo@gmail.com>"
    )


@pytest.mark.parametrize(
    "input_branches,sorted_branches",
    [
        (["3.1", "2.7", "3.10", "3.6"], ["3.10", "3.6", "3.1", "2.7"]),
        (
            ["stable-3.1", "lts-2.7", "3.10-other", "smth3.6else"],
            ["3.10-other", "smth3.6else", "stable-3.1", "lts-2.7"],
        ),
    ],
)
@mock.patch("os.path.exists")
@mock.patch("cherry_picker.cherry_picker.validate_sha")
def test_sorted_branch(os_path_exists, config, input_branches, sorted_branches):
    os_path_exists.return_value = True
    cp = CherryPicker(
        "origin",
        "22a594a0047d7706537ff2ac676cdc0f1dcb329c",
        input_branches,
        config=config,
    )
    assert cp.sorted_branches == sorted_branches


@pytest.mark.parametrize(
    "input_branches",
    [
        (["3.1", "2.7", "3.x10", "3.6", ""]),
        (["stable-3.1", "lts-2.7", "3.10-other", "smth3.6else", "invalid"]),
    ],
)
@mock.patch("os.path.exists")
def test_invalid_branches(os_path_exists, config, input_branches):
    os_path_exists.return_value = True
    cp = CherryPicker(
        "origin",
        "22a594a0047d7706537ff2ac676cdc0f1dcb329c",
        input_branches,
        config=config,
    )
    with pytest.raises(ValueError):
        cp.sorted_branches


@mock.patch("os.path.exists")
def test_get_cherry_pick_branch(os_path_exists, config):
    os_path_exists.return_value = True
    branches = ["3.6"]
    cp = CherryPicker(
        "origin", "22a594a0047d7706537ff2ac676cdc0f1dcb329c", branches, config=config
    )
    assert cp.get_cherry_pick_branch("3.6") == "backport-22a594a-3.6"


def test_get_pr_url(config):
    branches = ["3.6"]
    cp = CherryPicker(
        "origin", "22a594a0047d7706537ff2ac676cdc0f1dcb329c", branches, config=config
    )
    backport_target_branch = cp.get_cherry_pick_branch("3.6")
    expected_pr_url = (
        "https://github.com/python/cpython/compare/"
        "3.6...mock_user:backport-22a594a-3.6?expand=1"
    )
    with mock.patch(
        "subprocess.check_output",
        return_value=b"https://github.com/mock_user/cpython.git",
    ):
        actual_pr_url = cp.get_pr_url("3.6", backport_target_branch)

    assert actual_pr_url == expected_pr_url


@pytest.mark.parametrize(
    "url",
    [
        b"git@github.com:mock_user/cpython.git",
        b"git@github.com:mock_user/cpython",
        b"ssh://git@github.com/mock_user/cpython.git",
        b"ssh://git@github.com/mock_user/cpython",
        b"https://github.com/mock_user/cpython.git",
        b"https://github.com/mock_user/cpython",
    ],
)
def test_username(url, config):
    branches = ["3.6"]
    cp = CherryPicker(
        "origin", "22a594a0047d7706537ff2ac676cdc0f1dcb329c", branches, config=config
    )
    with mock.patch("subprocess.check_output", return_value=url):
        assert cp.username == "mock_user"


def test_get_updated_commit_message(config):
    branches = ["3.6"]
    cp = CherryPicker(
        "origin", "22a594a0047d7706537ff2ac676cdc0f1dcb329c", branches, config=config
    )
    with mock.patch(
        "subprocess.check_output", return_value=b"bpo-123: Fix Spam Module (#113)"
    ):
        actual_commit_message = cp.get_commit_message(
            "22a594a0047d7706537ff2ac676cdc0f1dcb329c"
        )
    assert actual_commit_message == "bpo-123: Fix Spam Module (GH-113)"


def test_get_updated_commit_message_without_links_replacement(config):
    config["fix_commit_msg"] = False
    branches = ["3.6"]
    cp = CherryPicker(
        "origin", "22a594a0047d7706537ff2ac676cdc0f1dcb329c", branches, config=config
    )
    with mock.patch(
        "subprocess.check_output", return_value=b"bpo-123: Fix Spam Module (#113)"
    ):
        actual_commit_message = cp.get_commit_message(
            "22a594a0047d7706537ff2ac676cdc0f1dcb329c"
        )
    assert actual_commit_message == "bpo-123: Fix Spam Module (#113)"


@mock.patch("subprocess.check_output")
def test_is_cpython_repo(subprocess_check_output):
    subprocess_check_output.return_value = """commit 7f777ed95a19224294949e1b4ce56bbffcb1fe9f
Author: Guido van Rossum <guido@python.org>
Date:   Thu Aug 9 14:25:15 1990 +0000

    Initial revision

"""
    # should not raise an exception
    validate_sha("22a594a0047d7706537ff2ac676cdc0f1dcb329c")


def test_is_not_cpython_repo():
    # use default CPython sha to fail on this repo
    with pytest.raises(InvalidRepoException):
        CherryPicker("origin", "22a594a0047d7706537ff2ac676cdc0f1dcb329c", ["3.6"])


def test_find_config(tmp_git_repo_dir, git_add, git_commit):
    relative_config_path = ".cherry_picker.toml"
    tmp_git_repo_dir.join(relative_config_path).write("param = 1")
    git_add(relative_config_path)
    git_commit("Add config")
    scm_revision = get_sha1_from("HEAD")
    assert find_config(scm_revision) == f"{scm_revision}:{relative_config_path}"


def test_find_config_not_found(tmp_git_repo_dir):
    scm_revision = get_sha1_from("HEAD")
    assert find_config(scm_revision) is None


def test_find_config_not_git(tmpdir, cd):
    cd(tmpdir)
    assert find_config(None) is None


def test_load_full_config(tmp_git_repo_dir, git_add, git_commit):
    relative_config_path = ".cherry_picker.toml"
    tmp_git_repo_dir.join(relative_config_path).write(
        """\
    team = "python"
    repo = "core-workfolow"
    check_sha = "5f007046b5d4766f971272a0cc99f8461215c1ec"
    default_branch = "devel"
    """
    )
    git_add(relative_config_path)
    git_commit("Add config")
    scm_revision = get_sha1_from("HEAD")
    cfg = load_config(None)
    assert cfg == (
        scm_revision + ":" + relative_config_path,
        {
            "check_sha": "5f007046b5d4766f971272a0cc99f8461215c1ec",
            "repo": "core-workfolow",
            "team": "python",
            "fix_commit_msg": True,
            "default_branch": "devel",
        },
    )


def test_load_partial_config(tmp_git_repo_dir, git_add, git_commit):
    relative_config_path = ".cherry_picker.toml"
    tmp_git_repo_dir.join(relative_config_path).write(
        """\
    repo = "core-workfolow"
    """
    )
    git_add(relative_config_path)
    git_commit("Add config")
    scm_revision = get_sha1_from("HEAD")
    cfg = load_config(relative_config_path)
    assert cfg == (
        f"{scm_revision}:{relative_config_path}",
        {
            "check_sha": "7f777ed95a19224294949e1b4ce56bbffcb1fe9f",
            "repo": "core-workfolow",
            "team": "python",
            "fix_commit_msg": True,
            "default_branch": "master",
        },
    )


def test_load_config_no_head_sha(tmp_git_repo_dir, git_add, git_commit):
    relative_config_path = ".cherry_picker.toml"
    tmp_git_repo_dir.join(relative_config_path).write(
        """\
    team = "python"
    repo = "core-workfolow"
    check_sha = "5f007046b5d4766f971272a0cc99f8461215c1ec"
    default_branch = "devel"
    """
    )
    git_add(relative_config_path)
    git_commit(f"Add {relative_config_path}")

    with mock.patch("cherry_picker.cherry_picker.get_sha1_from", return_value=""):
        cfg = load_config(relative_config_path)

    assert cfg == (
        ":" + relative_config_path,
        {
            "check_sha": "5f007046b5d4766f971272a0cc99f8461215c1ec",
            "repo": "core-workfolow",
            "team": "python",
            "fix_commit_msg": True,
            "default_branch": "devel",
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
    assert (
        title == "[3.6] Fix broken `Show Source` links on documentation pages (GH-3113)"
    )
    assert (
        body
        == """The `Show Source` was broken because of a change made in sphinx 1.5.1
In Sphinx 1.4.9, the sourcename was "index.txt".
In Sphinx 1.5.1+, it is now "index.rst.txt".
(cherry picked from commit b9ff498793611d1c6a9b99df464812931a1e2d69)


Co-authored-by: Elmar Ritsch <35851+elritsch@users.noreply.github.com>"""
    )


def test_normalize_short_commit_message():
    commit_message = """[3.6] Fix broken `Show Source` links on documentation pages (GH-3113)

(cherry picked from commit b9ff498793611d1c6a9b99df464812931a1e2d69)


Co-authored-by: Elmar Ritsch <35851+elritsch@users.noreply.github.com>"""
    title, body = normalize_commit_message(commit_message)
    assert (
        title == "[3.6] Fix broken `Show Source` links on documentation pages (GH-3113)"
    )
    assert (
        body
        == """(cherry picked from commit b9ff498793611d1c6a9b99df464812931a1e2d69)


Co-authored-by: Elmar Ritsch <35851+elritsch@users.noreply.github.com>"""
    )


@pytest.mark.parametrize(
    "input_path", ("/some/path/without/revision", "HEAD:some/non-existent/path")
)
def test_from_git_rev_read_negative(input_path, tmp_git_repo_dir):
    with pytest.raises(ValueError):
        from_git_rev_read(input_path)


def test_from_git_rev_read_uncommitted(tmp_git_repo_dir, git_add, git_commit):
    some_text = "blah blah 🤖"
    relative_file_path = ".some.file"
    (pathlib.Path(tmp_git_repo_dir) / relative_file_path).write_text(
        some_text, encoding="utf-8"
    )
    git_add(".")
    with pytest.raises(ValueError):
        from_git_rev_read("HEAD:" + relative_file_path)


def test_from_git_rev_read(tmp_git_repo_dir, git_add, git_commit):
    some_text = "blah blah 🤖"
    relative_file_path = ".some.file"
    (pathlib.Path(tmp_git_repo_dir) / relative_file_path).write_text(
        some_text, encoding="utf-8"
    )
    git_add(".")
    git_commit("Add some file")
    assert from_git_rev_read("HEAD:" + relative_file_path) == some_text


def test_states(tmp_git_repo_dir):
    class state_val:
        name = "somerandomwords"

    # First, verify that there's nothing there initially
    assert get_state() == WORKFLOW_STATES.UNSET

    # Now, set some val
    set_state(state_val)
    with pytest.raises(KeyError, match=state_val.name):
        get_state()

    # Wipe it again
    reset_state()
    assert get_state() == WORKFLOW_STATES.UNSET


def test_paused_flow(tmp_git_repo_dir, git_add, git_commit):
    assert load_val_from_git_cfg("config_path") is None
    initial_scm_revision = get_sha1_from("HEAD")

    relative_file_path = "some.toml"
    tmp_git_repo_dir.join(relative_file_path).write(
        f"""\
    check_sha = "{initial_scm_revision}"
    repo = "core-workfolow"
    """
    )
    git_add(relative_file_path)
    git_commit("Add a config")
    config_scm_revision = get_sha1_from("HEAD")

    config_path_rev = config_scm_revision + ":" + relative_file_path
    chosen_config_path, config = load_config(config_path_rev)

    cherry_picker = CherryPicker(
        "origin",
        config_scm_revision,
        [],
        config=config,
        chosen_config_path=chosen_config_path,
    )
    assert get_state() == WORKFLOW_STATES.UNSET

    cherry_picker.set_paused_state()
    assert load_val_from_git_cfg("config_path") == config_path_rev
    assert get_state() == WORKFLOW_STATES.BACKPORT_PAUSED

    chosen_config_path, config = load_config(None)
    assert chosen_config_path == config_path_rev

    reset_stored_config_ref()
    assert load_val_from_git_cfg("config_path") is None


@pytest.mark.parametrize(
    "method_name,start_state,end_state",
    (
        (
            "fetch_upstream",
            WORKFLOW_STATES.FETCHING_UPSTREAM,
            WORKFLOW_STATES.FETCHED_UPSTREAM,
        ),
        (
            "checkout_default_branch",
            WORKFLOW_STATES.CHECKING_OUT_DEFAULT_BRANCH,
            WORKFLOW_STATES.CHECKED_OUT_DEFAULT_BRANCH,
        ),
    ),
)
def test_start_end_states(method_name, start_state, end_state, tmp_git_repo_dir):
    assert get_state() == WORKFLOW_STATES.UNSET

    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker("origin", "xxx", [])
    assert get_state() == WORKFLOW_STATES.UNSET

    def _fetch(cmd):
        assert get_state() == start_state

    with mock.patch.object(cherry_picker, "run_cmd", _fetch):
        getattr(cherry_picker, method_name)()
    assert get_state() == end_state


def test_cleanup_branch(tmp_git_repo_dir, git_checkout):
    assert get_state() == WORKFLOW_STATES.UNSET

    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker("origin", "xxx", [])
    assert get_state() == WORKFLOW_STATES.UNSET

    git_checkout("-b", "some_branch")
    cherry_picker.cleanup_branch("some_branch")
    assert get_state() == WORKFLOW_STATES.REMOVED_BACKPORT_BRANCH


def test_cleanup_branch_fail(tmp_git_repo_dir):
    assert get_state() == WORKFLOW_STATES.UNSET

    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker("origin", "xxx", [])
    assert get_state() == WORKFLOW_STATES.UNSET

    cherry_picker.cleanup_branch("some_branch")
    assert get_state() == WORKFLOW_STATES.REMOVING_BACKPORT_BRANCH_FAILED


def test_cherry_pick(tmp_git_repo_dir, git_add, git_branch, git_commit, git_checkout):
    cherry_pick_target_branches = ("3.8",)
    pr_remote = "origin"
    test_file = "some.file"
    tmp_git_repo_dir.join(test_file).write("some contents")
    git_branch(cherry_pick_target_branches[0])
    git_branch(
        f"{pr_remote}/{cherry_pick_target_branches[0]}", cherry_pick_target_branches[0]
    )
    git_add(test_file)
    git_commit("Add a test file")
    scm_revision = get_sha1_from("HEAD")

    git_checkout(cherry_pick_target_branches[0])  # simulate backport method logic

    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker(
            pr_remote, scm_revision, cherry_pick_target_branches
        )

    cherry_picker.cherry_pick()


def test_cherry_pick_fail(tmp_git_repo_dir,):
    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker("origin", "xxx", [])

    with pytest.raises(CherryPickException, match="^Error cherry-pick xxx.$"):
        cherry_picker.cherry_pick()


def test_get_state_and_verify_fail(tmp_git_repo_dir,):
    class tested_state:
        name = "invalid_state"

    set_state(tested_state)

    expected_msg_regexp = (
        fr"^Run state cherry-picker.state={tested_state.name} in Git config "
        r"is not known."
        "\n"
        r"Perhaps it has been set by a newer "
        r"version of cherry-picker\. Try upgrading\."
        "\n"
        r"Valid states are: "
        r"[\w_\s]+(, [\w_\s]+)*\. "
        r"If this looks suspicious, raise an issue at "
        r"https://github.com/python/core-workflow/issues/new\."
        "\n"
        r"As the last resort you can reset the runtime state "
        r"stored in Git config using the following command: "
        r"`git config --local --remove-section cherry-picker`"
    )
    with mock.patch(
        "cherry_picker.cherry_picker.validate_sha", return_value=True
    ), pytest.raises(ValueError, match=expected_msg_regexp):
        cherry_picker = CherryPicker("origin", "xxx", [])


def test_push_to_remote_fail(tmp_git_repo_dir):
    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker("origin", "xxx", [])

    cherry_picker.push_to_remote("master", "backport-branch-test")
    assert get_state() == WORKFLOW_STATES.PUSHING_TO_REMOTE_FAILED


def test_push_to_remote_interactive(tmp_git_repo_dir):
    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker("origin", "xxx", [])

    with mock.patch.object(cherry_picker, "run_cmd"), mock.patch.object(
        cherry_picker, "open_pr"
    ), mock.patch.object(cherry_picker, "get_pr_url", return_value="https://pr_url"):
        cherry_picker.push_to_remote("master", "backport-branch-test")
    assert get_state() == WORKFLOW_STATES.PR_OPENING


def test_push_to_remote_botflow(tmp_git_repo_dir, monkeypatch):
    monkeypatch.setenv("GH_AUTH", "True")
    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker("origin", "xxx", [])

    with mock.patch.object(cherry_picker, "run_cmd"), mock.patch.object(
        cherry_picker, "create_gh_pr"
    ):
        cherry_picker.push_to_remote("master", "backport-branch-test")
    assert get_state() == WORKFLOW_STATES.PR_CREATING


def test_backport_no_branch(tmp_git_repo_dir, monkeypatch):
    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker("origin", "xxx", [])

    with pytest.raises(
        click.UsageError, match="^At least one branch must be specified.$"
    ):
        cherry_picker.backport()


def test_backport_cherry_pick_fail(
    tmp_git_repo_dir, git_branch, git_add, git_commit, git_checkout
):
    cherry_pick_target_branches = ("3.8",)
    pr_remote = "origin"
    test_file = "some.file"
    tmp_git_repo_dir.join(test_file).write("some contents")
    git_branch(cherry_pick_target_branches[0])
    git_branch(
        f"{pr_remote}/{cherry_pick_target_branches[0]}", cherry_pick_target_branches[0]
    )
    git_add(test_file)
    git_commit("Add a test file")
    scm_revision = get_sha1_from("HEAD")

    git_checkout(cherry_pick_target_branches[0])  # simulate backport method logic

    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker(
            pr_remote, scm_revision, cherry_pick_target_branches
        )

    with pytest.raises(CherryPickException), mock.patch.object(
        cherry_picker, "checkout_branch"
    ), mock.patch.object(cherry_picker, "fetch_upstream"), mock.patch.object(
        cherry_picker, "cherry_pick", side_effect=CherryPickException
    ):
        cherry_picker.backport()

    assert get_state() == WORKFLOW_STATES.BACKPORT_PAUSED


def test_backport_cherry_pick_crash_ignored(
    tmp_git_repo_dir, git_branch, git_add, git_commit, git_checkout
):
    cherry_pick_target_branches = ("3.8",)
    pr_remote = "origin"
    test_file = "some.file"
    tmp_git_repo_dir.join(test_file).write("some contents")
    git_branch(cherry_pick_target_branches[0])
    git_branch(
        f"{pr_remote}/{cherry_pick_target_branches[0]}", cherry_pick_target_branches[0]
    )
    git_add(test_file)
    git_commit("Add a test file")
    scm_revision = get_sha1_from("HEAD")

    git_checkout(cherry_pick_target_branches[0])  # simulate backport method logic

    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker(
            pr_remote, scm_revision, cherry_pick_target_branches
        )

    with mock.patch.object(cherry_picker, "checkout_branch"), mock.patch.object(
        cherry_picker, "fetch_upstream"
    ), mock.patch.object(cherry_picker, "cherry_pick"), mock.patch.object(
        cherry_picker,
        "amend_commit_message",
        side_effect=subprocess.CalledProcessError(
            1, ("git", "commit", "-am", "new commit message")
        ),
    ):
        cherry_picker.backport()

    assert get_state() == WORKFLOW_STATES.UNSET


def test_backport_success(
    tmp_git_repo_dir, git_branch, git_add, git_commit, git_checkout
):
    cherry_pick_target_branches = ("3.8",)
    pr_remote = "origin"
    test_file = "some.file"
    tmp_git_repo_dir.join(test_file).write("some contents")
    git_branch(cherry_pick_target_branches[0])
    git_branch(
        f"{pr_remote}/{cherry_pick_target_branches[0]}", cherry_pick_target_branches[0]
    )
    git_add(test_file)
    git_commit("Add a test file")
    scm_revision = get_sha1_from("HEAD")

    git_checkout(cherry_pick_target_branches[0])  # simulate backport method logic

    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker(
            pr_remote, scm_revision, cherry_pick_target_branches
        )

    with mock.patch.object(cherry_picker, "checkout_branch"), mock.patch.object(
        cherry_picker, "fetch_upstream"
    ), mock.patch.object(
        cherry_picker, "amend_commit_message", return_value="commit message"
    ):
        cherry_picker.backport()

    assert get_state() == WORKFLOW_STATES.UNSET


def test_backport_pause_and_continue(
    tmp_git_repo_dir, git_branch, git_add, git_commit, git_checkout
):
    cherry_pick_target_branches = ("3.8",)
    pr_remote = "origin"
    test_file = "some.file"
    tmp_git_repo_dir.join(test_file).write("some contents")
    git_branch(cherry_pick_target_branches[0])
    git_branch(
        f"{pr_remote}/{cherry_pick_target_branches[0]}", cherry_pick_target_branches[0]
    )
    git_add(test_file)
    git_commit("Add a test file")
    scm_revision = get_sha1_from("HEAD")

    git_checkout(cherry_pick_target_branches[0])  # simulate backport method logic

    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker(
            pr_remote, scm_revision, cherry_pick_target_branches, push=False
        )

    with mock.patch.object(cherry_picker, "checkout_branch"), mock.patch.object(
        cherry_picker, "fetch_upstream"
    ), mock.patch.object(
        cherry_picker, "amend_commit_message", return_value="commit message"
    ):
        cherry_picker.backport()

    assert get_state() == WORKFLOW_STATES.BACKPORT_PAUSED

    cherry_picker.initial_state = get_state()
    with mock.patch(
        "cherry_picker.cherry_picker.wipe_cfg_vals_from_git_cfg"
    ), mock.patch(
        "cherry_picker.cherry_picker.get_full_sha_from_short",
        return_value="xxxxxxyyyyyy",
    ), mock.patch(
        "cherry_picker.cherry_picker.get_base_branch", return_value="3.8"
    ), mock.patch(
        "cherry_picker.cherry_picker.get_current_branch",
        return_value="backport-xxx-3.8",
    ), mock.patch(
        "cherry_picker.cherry_picker.get_author_info_from_short_sha",
        return_value="Author Name <author@name.email>",
    ), mock.patch.object(
        cherry_picker, "get_commit_message", return_value="commit message"
    ), mock.patch.object(
        cherry_picker, "checkout_branch"
    ), mock.patch.object(
        cherry_picker, "fetch_upstream"
    ):
        cherry_picker.continue_cherry_pick()

    assert get_state() == WORKFLOW_STATES.BACKPORTING_CONTINUATION_SUCCEED


def test_continue_cherry_pick_invalid_state(tmp_git_repo_dir):
    assert get_state() == WORKFLOW_STATES.UNSET

    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker("origin", "xxx", [])

    assert get_state() == WORKFLOW_STATES.UNSET

    with pytest.raises(ValueError, match=r"^One can only continue a paused process.$"):
        cherry_picker.continue_cherry_pick()

    assert get_state() == WORKFLOW_STATES.UNSET  # success


def test_continue_cherry_pick_invalid_branch(tmp_git_repo_dir):
    set_state(WORKFLOW_STATES.BACKPORT_PAUSED)

    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker("origin", "xxx", [])

    with mock.patch("cherry_picker.cherry_picker.wipe_cfg_vals_from_git_cfg"):
        cherry_picker.continue_cherry_pick()

    assert get_state() == WORKFLOW_STATES.CONTINUATION_FAILED


def test_abort_cherry_pick_invalid_state(tmp_git_repo_dir):
    assert get_state() == WORKFLOW_STATES.UNSET

    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker("origin", "xxx", [])

    assert get_state() == WORKFLOW_STATES.UNSET

    with pytest.raises(ValueError, match=r"^One can only abort a paused process.$"):
        cherry_picker.abort_cherry_pick()


def test_abort_cherry_pick_fail(tmp_git_repo_dir):
    set_state(WORKFLOW_STATES.BACKPORT_PAUSED)

    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker("origin", "xxx", [])

    with mock.patch("cherry_picker.cherry_picker.wipe_cfg_vals_from_git_cfg"):
        cherry_picker.abort_cherry_pick()

    assert get_state() == WORKFLOW_STATES.ABORTING_FAILED


def test_abort_cherry_pick_success(
    tmp_git_repo_dir, git_branch, git_add, git_commit, git_checkout, git_cherry_pick
):
    cherry_pick_target_branches = ("3.8",)
    pr_remote = "origin"
    test_file = "some.file"
    git_branch(f"backport-xxx-{cherry_pick_target_branches[0]}")

    tmp_git_repo_dir.join(test_file).write("some contents")
    git_add(test_file)
    git_commit("Add a test file")
    scm_revision = get_sha1_from("HEAD")

    git_checkout(f"backport-xxx-{cherry_pick_target_branches[0]}")
    tmp_git_repo_dir.join(test_file).write("some other contents")
    git_add(test_file)
    git_commit("Add a test file again")

    try:
        git_cherry_pick(scm_revision)  # simulate a conflict with pause
    except subprocess.CalledProcessError:
        pass

    set_state(WORKFLOW_STATES.BACKPORT_PAUSED)

    with mock.patch("cherry_picker.cherry_picker.validate_sha", return_value=True):
        cherry_picker = CherryPicker(
            pr_remote, scm_revision, cherry_pick_target_branches
        )

    with mock.patch("cherry_picker.cherry_picker.wipe_cfg_vals_from_git_cfg"):
        cherry_picker.abort_cherry_pick()

    assert get_state() == WORKFLOW_STATES.REMOVED_BACKPORT_BRANCH
