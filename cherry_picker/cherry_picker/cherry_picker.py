#!/usr/bin/env python3
#  -*- coding: utf-8 -*-

import click
import collections
import enum
import os
import subprocess
import webbrowser
import re
import sys
import requests
import toml

from gidgethub import sansio

from . import __version__

CREATE_PR_URL_TEMPLATE = ("https://api.github.com/repos/"
                          "{config[team]}/{config[repo]}/pulls")
DEFAULT_CONFIG = collections.ChainMap({
    'team': 'python',
    'repo': 'cpython',
    'check_sha': '7f777ed95a19224294949e1b4ce56bbffcb1fe9f',
    'fix_commit_msg': True,
    'default_branch': 'master',
})


class BranchCheckoutException(Exception):
    pass


class CherryPickException(Exception):
    pass


class InvalidRepoException(Exception):
    pass


class CherryPicker:

    ALLOWED_STATES = enum.Enum(
        'Allowed states',
        'BACKPORT_PAUSED UNSET',
    )
    """The list of states expected at the start of the app."""

    def __init__(self, pr_remote, commit_sha1, branches,
                 *, dry_run=False, push=True,
                 prefix_commit=True,
                 config=DEFAULT_CONFIG,
                 chosen_config_path=None,
                 ):

        self.chosen_config_path = chosen_config_path
        """The config reference used in the current runtime.

        It starts with a Git revision specifier, followed by a colon
        and a path relative to the repo root.
        """

        self.config = config
        self.check_repo()  # may raise InvalidRepoException

        self.initial_state = self.get_state_and_verify()
        """The runtime state loaded from the config.

        Used to verify that we resume the process from the valid
        previous state.
        """

        if dry_run:
            click.echo("Dry run requested, listing expected command sequence")

        self.pr_remote = pr_remote
        self.commit_sha1 = commit_sha1
        self.branches = branches
        self.dry_run = dry_run
        self.push = push
        self.prefix_commit = prefix_commit

    def set_paused_state(self):
        """Save paused progress state into Git config."""
        if self.chosen_config_path is not None:
            save_cfg_vals_to_git_cfg(config_path=self.chosen_config_path)
        set_state('BACKPORT_PAUSED')

    @property
    def upstream(self):
        """Get the remote name to use for upstream branches
        Uses "upstream" if it exists, "origin" otherwise
        """
        cmd = ['git', 'remote', 'get-url', 'upstream']
        try:
            subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            return "origin"
        return "upstream"

    @property
    def sorted_branches(self):
        """Return the branches to cherry-pick to, sorted by version."""
        return sorted(
            self.branches,
            reverse=True,
            key=version_from_branch)

    @property
    def username(self):
        cmd = ['git', 'config', '--get', f'remote.{self.pr_remote}.url']
        raw_result = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        result = raw_result.decode('utf-8')
        # implicit ssh URIs use : to separate host from user, others just use /
        username = result.replace(':', '/').split('/')[-2]
        return username

    def get_cherry_pick_branch(self, maint_branch):
        return f"backport-{self.commit_sha1[:7]}-{maint_branch}"

    def get_pr_url(self, base_branch, head_branch):
        return f"https://github.com/{self.config['team']}/{self.config['repo']}/compare/{base_branch}...{self.username}:{head_branch}?expand=1"

    def fetch_upstream(self):
        """ git fetch <upstream> """
        set_state('FETCHING_UPSTREAM')
        cmd = ['git', 'fetch', self.upstream]
        self.run_cmd(cmd)
        set_state('FETCHED_UPSTREAM')

    def run_cmd(self, cmd):
        assert not isinstance(cmd, str)
        if self.dry_run:
            click.echo(f"  dry-run: {' '.join(cmd)}")
            return
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        click.echo(output.decode('utf-8'))

    def checkout_branch(self, branch_name):
        """ git checkout -b <branch_name> """
        cmd = ['git', 'checkout', '-b', self.get_cherry_pick_branch(branch_name), f'{self.upstream}/{branch_name}']
        try:
            self.run_cmd(cmd)
        except subprocess.CalledProcessError as err:
            click.echo(f"Error checking out the branch {self.get_cherry_pick_branch(branch_name)}.")
            click.echo(err.output)
            raise BranchCheckoutException(f"Error checking out the branch {self.get_cherry_pick_branch(branch_name)}.")

    def get_commit_message(self, commit_sha):
        """
        Return the commit message for the current commit hash,
        replace #<PRID> with GH-<PRID>
        """
        cmd = ['git', 'show', '-s', '--format=%B', commit_sha]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        message = output.strip().decode('utf-8')
        if self.config['fix_commit_msg']:
            return message.replace('#', 'GH-')
        else:
            return message

    def checkout_default_branch(self):
        """ git checkout default branch """
        set_state('CHECKING_OUT_DEFAULT_BRANCH')

        cmd = 'git', 'checkout', self.config['default_branch']
        self.run_cmd(cmd)

        set_state('CHECKED_OUT_DEFAULT_BRANCH')

    def status(self):
        """
        git status
        :return:
        """
        cmd = ['git', 'status']
        self.run_cmd(cmd)

    def cherry_pick(self):
        """ git cherry-pick -x <commit_sha1> """
        cmd = ['git', 'cherry-pick', '-x', self.commit_sha1]
        try:
            self.run_cmd(cmd)
        except subprocess.CalledProcessError as err:
            click.echo(f"Error cherry-pick {self.commit_sha1}.")
            click.echo(err.output)
            raise CherryPickException(f"Error cherry-pick {self.commit_sha1}.")

    def get_exit_message(self, branch):
        return \
f"""
Failed to cherry-pick {self.commit_sha1} into {branch} \u2639
... Stopping here.

To continue and resolve the conflict:
    $ cherry_picker --status  # to find out which files need attention
    # Fix the conflict
    $ cherry_picker --status  # should now say 'all conflict fixed'
    $ cherry_picker --continue

To abort the cherry-pick and cleanup:
    $ cherry_picker --abort
"""

    def amend_commit_message(self, cherry_pick_branch):
        """ prefix the commit message with (X.Y) """

        commit_prefix = ""
        if self.prefix_commit:
            commit_prefix = f"[{get_base_branch(cherry_pick_branch)}] "
        updated_commit_message = f"""{commit_prefix}{self.get_commit_message(self.commit_sha1)}
(cherry picked from commit {self.commit_sha1})


Co-authored-by: {get_author_info_from_short_sha(self.commit_sha1)}"""
        if self.dry_run:
            click.echo(f"  dry-run: git commit --amend -m '{updated_commit_message}'")
        else:
            cmd = ['git', 'commit', '--amend', '-m', updated_commit_message]
            try:
                subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as cpe:
                click.echo("Failed to amend the commit message \u2639")
                click.echo(cpe.output)
        return updated_commit_message


    def push_to_remote(self, base_branch, head_branch, commit_message=""):
        """ git push <origin> <branchname> """
        set_state('PUSHING_TO_REMOTE')

        cmd = ['git', 'push', self.pr_remote, f'{head_branch}:{head_branch}']
        try:
            self.run_cmd(cmd)
            set_state('PUSHED_TO_REMOTE')
        except subprocess.CalledProcessError:
            click.echo(f"Failed to push to {self.pr_remote} \u2639")
            set_state('PUSHING_TO_REMOTE_FAILED')
        else:
            gh_auth = os.getenv("GH_AUTH")
            if gh_auth:
                set_state('PR_CREATING')
                self.create_gh_pr(base_branch, head_branch,
                                  commit_message=commit_message,
                                  gh_auth=gh_auth)
            else:
                set_state('PR_OPENING')
                self.open_pr(self.get_pr_url(base_branch, head_branch))

    def create_gh_pr(self, base_branch, head_branch, *,
                     commit_message,
                     gh_auth):
        """
        Create PR in GitHub
        """
        request_headers = sansio.create_headers(
            self.username, oauth_token=gh_auth)
        title, body = normalize_commit_message(commit_message)
        if not self.prefix_commit:
            title = f"[{base_branch}] {title}"
        data = {
          "title": title,
          "body": body,
          "head": f"{self.username}:{head_branch}",
          "base": base_branch,
          "maintainer_can_modify": True
        }
        url = CREATE_PR_URL_TEMPLATE.format(config=self.config)
        response = requests.post(url, headers=request_headers, json=data)
        if response.status_code == requests.codes.created:
            click.echo(f"Backport PR created at {response.json()['html_url']}")
        else:
            click.echo(response.status_code)
            click.echo(response.text)

    def open_pr(self, url):
        """
        open url in the web browser
        """
        if self.dry_run:
            click.echo(f"  dry-run: Create new PR: {url}")
        else:
            click.echo("Backport PR URL:")
            click.echo(url)
            webbrowser.open_new_tab(url)

    def delete_branch(self, branch):
        cmd = ['git', 'branch', '-D', branch]
        self.run_cmd(cmd)

    def cleanup_branch(self, branch):
        """Remove the temporary backport branch.

        Switch to the default branch before that.
        """
        set_state('REMOVING_BACKPORT_BRANCH')
        self.checkout_default_branch()
        try:
            self.delete_branch(branch)
        except subprocess.CalledProcessError:
            click.echo(f"branch {branch} NOT deleted.")
            set_state('REMOVING_BACKPORT_BRANCH_FAILED')
        else:
            click.echo(f"branch {branch} has been deleted.")
            set_state('REMOVED_BACKPORT_BRANCH')

    def backport(self):
        if not self.branches:
            raise click.UsageError("At least one branch must be specified.")
        set_state('BACKPORT_STARTING')
        self.fetch_upstream()

        set_state('BACKPORT_LOOPING')
        for maint_branch in self.sorted_branches:
            set_state('BACKPORT_LOOP_START')
            click.echo(f"Now backporting '{self.commit_sha1}' into '{maint_branch}'")

            cherry_pick_branch = self.get_cherry_pick_branch(maint_branch)
            self.checkout_branch(maint_branch)
            commit_message = ""
            try:
                self.cherry_pick()
                commit_message = self.amend_commit_message(cherry_pick_branch)
            except subprocess.CalledProcessError as cpe:
                click.echo(cpe.output)
                click.echo(self.get_exit_message(maint_branch))
            except CherryPickException:
                click.echo(self.get_exit_message(maint_branch))
                self.set_paused_state()
                raise
            else:
                if self.push:
                    self.push_to_remote(maint_branch,
                                        cherry_pick_branch,
                                        commit_message)
                    self.cleanup_branch(cherry_pick_branch)
                else:
                    click.echo(\
f"""
Finished cherry-pick {self.commit_sha1} into {cherry_pick_branch} \U0001F600
--no-push option used.
... Stopping here.
To continue and push the changes:
    $ cherry_picker --continue

To abort the cherry-pick and cleanup:
    $ cherry_picker --abort
""")
                    self.set_paused_state()
                    return  # to preserve the correct state
            set_state('BACKPORT_LOOP_END')
        set_state('BACKPORT_COMPLETE')

    def abort_cherry_pick(self):
        """
        run `git cherry-pick --abort` and then clean up the branch
        """
        if self.initial_state != 'BACKPORT_PAUSED':
            raise ValueError('One can only abort a paused process.')

        cmd = ['git', 'cherry-pick', '--abort']
        try:
            set_state('ABORTING')
            self.run_cmd(cmd)
            set_state('ABORTED')
        except subprocess.CalledProcessError as cpe:
            click.echo(cpe.output)
            set_state('ABORTING_FAILED')
        # only delete backport branch created by cherry_picker.py
        if get_current_branch().startswith('backport-'):
            self.cleanup_branch(get_current_branch())

        reset_stored_config_ref()
        reset_state()

    def continue_cherry_pick(self):
        """
        git push origin <current_branch>
        open the PR
        clean up branch
        """
        if self.initial_state != 'BACKPORT_PAUSED':
            raise ValueError('One can only continue a paused process.')

        cherry_pick_branch = get_current_branch()
        if cherry_pick_branch.startswith('backport-'):
            set_state('CONTINUATION_STARTED')
            # amend the commit message, prefix with [X.Y]
            base = get_base_branch(cherry_pick_branch)
            short_sha = cherry_pick_branch[cherry_pick_branch.index('-')+1:cherry_pick_branch.index(base)-1]
            full_sha = get_full_sha_from_short(short_sha)
            commit_message = self.get_commit_message(short_sha)
            co_author_info = f"Co-authored-by: {get_author_info_from_short_sha(short_sha)}"
            updated_commit_message = f"""[{base}] {commit_message}.
(cherry picked from commit {full_sha})


{co_author_info}"""
            if self.dry_run:
                click.echo(f"  dry-run: git commit -a -m '{updated_commit_message}' --allow-empty")
            else:
                cmd = ['git', 'commit', '-a', '-m', updated_commit_message, '--allow-empty']
                subprocess.check_output(cmd, stderr=subprocess.STDOUT)

            self.push_to_remote(base, cherry_pick_branch)

            self.cleanup_branch(cherry_pick_branch)

            click.echo("\nBackport PR:\n")
            click.echo(updated_commit_message)
            set_state('BACKPORTING_CONTINUATION_SUCCEED')

        else:
            click.echo(f"Current branch ({cherry_pick_branch}) is not a backport branch.  Will not continue. \U0001F61B")
            set_state('CONTINUATION_FAILED')

        reset_stored_config_ref()
        reset_state()

    def check_repo(self):
        """
        Check that the repository is for the project we're configured to operate on.

        This function performs the check by making sure that the sha specified in the config
        is present in the repository that we're operating on.
        """
        try:
            validate_sha(self.config['check_sha'])
        except ValueError:
            raise InvalidRepoException()

    def get_state_and_verify(self):
        """Return the run progress state stored in the Git config.

        Raises ValueError if the retrieved state is not of a form that
                          cherry_picker would have stored in the config.
        """
        state = get_state()
        if state not in self.ALLOWED_STATES.__members__:
            raise ValueError(
                f'Run state cherry-picker.state={state} in Git config '
                'is not known.\nPerhaps it has been set by a newer '
                'version of cherry-picker. Try upgrading.\n'
                'Valid states are: '
                f'{", ".join(self.ALLOWED_STATES.__members__.keys())}. '
                'If this looks suspicious, raise an issue at '
                'https://github.com/python/core-workflow/issues/new.\n'
                'As the last resort you can reset the runtime state '
                'stored in Git config using the following command: '
                '`git config --local --remove-section cherry-picker`'
            )
        return state


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.command(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=__version__)
@click.option('--dry-run', is_flag=True,
              help="Prints out the commands, but not executed.")
@click.option('--pr-remote', 'pr_remote', metavar='REMOTE',
              help='git remote to use for PR branches', default='origin')
@click.option('--abort', 'abort', flag_value=True, default=None,
              help="Abort current cherry-pick and clean up branch")
@click.option('--continue', 'abort', flag_value=False, default=None,
              help="Continue cherry-pick, push, and clean up branch")
@click.option('--status', 'status', flag_value=True, default=None,
              help="Get the status of cherry-pick")
@click.option('--push/--no-push', 'push', is_flag=True, default=True,
              help="Changes won't be pushed to remote")
@click.option('--config-path', 'config_path', metavar='CONFIG-PATH',
              help=("Path to config file, .cherry_picker.toml "
                    "from project root by default. You can prepend "
                    "a colon-separated Git 'commitish' reference."),
              default=None)
@click.argument('commit_sha1', nargs=1, default="")
@click.argument('branches', nargs=-1)
@click.pass_context
def cherry_pick_cli(ctx,
                    dry_run, pr_remote, abort, status, push, config_path,
                    commit_sha1, branches):
    """cherry-pick COMMIT_SHA1 into target BRANCHES."""

    click.echo("\U0001F40D \U0001F352 \u26CF")

    chosen_config_path, config = load_config(config_path)

    try:
        cherry_picker = CherryPicker(pr_remote, commit_sha1, branches,
                                     dry_run=dry_run,
                                     push=push, config=config,
                                     chosen_config_path=chosen_config_path)
    except InvalidRepoException:
        click.echo(f"You're not inside a {config['repo']} repo right now! \U0001F645")
        sys.exit(-1)
    except ValueError as exc:
        ctx.fail(exc)

    if abort is not None:
        if abort:
            cherry_picker.abort_cherry_pick()
        else:
            cherry_picker.continue_cherry_pick()

    elif status:
        click.echo(cherry_picker.status())
    else:
        try:
            cherry_picker.backport()
        except BranchCheckoutException:
            sys.exit(-1)
        except CherryPickException:
            sys.exit(-1)


def get_base_branch(cherry_pick_branch):
    """
    return '2.7' from 'backport-sha-2.7'

    raises ValueError if the specified branch name is not of a form that
        cherry_picker would have created
    """
    prefix, sha, base_branch = cherry_pick_branch.split('-', 2)

    if prefix != 'backport':
        raise ValueError('branch name is not prefixed with "backport-".  Is this a cherry_picker branch?')

    if not re.match('[0-9a-f]{7,40}', sha):
        raise ValueError(f'branch name has an invalid sha: {sha}')

    # Validate that the sha refers to a valid commit within the repo
    # Throws a ValueError if the sha is not present in the repo
    validate_sha(sha)

    # Subject the parsed base_branch to the same tests as when we generated it
    # This throws a ValueError if the base_branch doesn't meet our requirements
    version_from_branch(base_branch)

    return base_branch


def validate_sha(sha):
    """
    Validate that a hexdigest sha is a valid commit in the repo

    raises ValueError if the sha does not reference a commit within the repo
    """
    cmd = ['git', 'log', '-r', sha]
    try:
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.SubprocessError:
        raise ValueError(f'The sha listed in the branch name, {sha}, is not present in the repository')


def version_from_branch(branch):
    """
    return version information from a git branch name
    """
    try:
        return tuple(map(int, re.match(r'^.*(?P<version>\d+(\.\d+)+).*$', branch).groupdict()['version'].split('.')))
    except AttributeError as attr_err:
        raise ValueError(f'Branch {branch} seems to not have a version in its name.') from attr_err


def get_current_branch():
    """
    Return the current branch
    """
    cmd = ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
    output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    return output.strip().decode('utf-8')


def get_full_sha_from_short(short_sha):
    cmd = ['git', 'log', '-1', '--format=%H', short_sha]
    output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    full_sha = output.strip().decode('utf-8')
    return full_sha


def get_author_info_from_short_sha(short_sha):
    cmd = ['git', 'log', '-1', '--format=%aN <%ae>', short_sha]
    output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    author = output.strip().decode('utf-8')
    return author


def normalize_commit_message(commit_message):
    """
    Return a tuple of title and body from the commit message
    """
    split_commit_message = commit_message.split("\n")
    title = split_commit_message[0]
    body = "\n".join(split_commit_message[1:])
    return title, body.lstrip("\n")


def is_git_repo():
    """Check whether the current folder is a Git repo."""
    cmd = 'git', 'rev-parse', '--git-dir'
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def find_config(revision):
    """Locate and return the default config for current revison."""
    if not is_git_repo():
        return None

    cfg_path = f'{revision}:.cherry_picker.toml'
    cmd = 'git', 'cat-file', '-t', cfg_path

    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        path_type = output.strip().decode('utf-8')
        return cfg_path if path_type == 'blob' else None
    except subprocess.CalledProcessError:
        return None


def load_config(path=None):
    """Choose and return the config path and it's contents as dict."""
    # NOTE: Initially I wanted to inherit Path to encapsulate Git access
    # there but there's no easy way to subclass pathlib.Path :(
    head_sha = get_sha1_from('HEAD')
    revision = head_sha
    saved_config_path = load_val_from_git_cfg('config_path')
    if not path and saved_config_path is not None:
        path = saved_config_path

    if path is None:
        path = find_config(revision=revision)
    else:
        if ':' not in path:
            path = f'{head_sha}:{path}'

            revision, _col, _path = path.partition(':')
            if not revision:
                revision = head_sha

    config = DEFAULT_CONFIG

    if path is not None:
        config_text = from_git_rev_read(path)
        d = toml.loads(config_text)
        config = config.new_child(d)

    return path, config


def get_sha1_from(commitish):
    """Turn 'commitish' into its sha1 hash."""
    cmd = ['git', 'rev-parse', commitish]
    return subprocess.check_output(cmd).strip().decode('utf-8')


def reset_stored_config_ref():
    """Remove the config path option from Git config."""
    try:
        wipe_cfg_vals_from_git_cfg('config_path')
    except subprocess.CalledProcessError:
        """Config file pointer is not stored in Git config."""


def reset_state():
    """Remove the progress state from Git config."""
    wipe_cfg_vals_from_git_cfg('state')


def set_state(state):
    """Save progress state into Git config."""
    save_cfg_vals_to_git_cfg(state=state)


def get_state():
    """Retrieve the progress state from Git config."""
    return load_val_from_git_cfg('state') or 'UNSET'


def save_cfg_vals_to_git_cfg(**cfg_map):
    """Save a set of options into Git config."""
    for cfg_key_suffix, cfg_val in cfg_map.items():
        cfg_key = f'cherry-picker.{cfg_key_suffix.replace("_", "-")}'
        cmd = 'git', 'config', '--local', cfg_key, cfg_val
        subprocess.check_call(cmd, stderr=subprocess.STDOUT)


def wipe_cfg_vals_from_git_cfg(*cfg_opts):
    """Remove a set of options from Git config."""
    for cfg_key_suffix in cfg_opts:
        cfg_key = f'cherry-picker.{cfg_key_suffix.replace("_", "-")}'
        cmd = 'git', 'config', '--local', '--unset-all', cfg_key
        subprocess.check_call(cmd, stderr=subprocess.STDOUT)


def load_val_from_git_cfg(cfg_key_suffix):
    """Retrieve one option from Git config."""
    cfg_key = f'cherry-picker.{cfg_key_suffix.replace("_", "-")}'
    cmd = 'git', 'config', '--local', '--get', cfg_key
    try:
        return subprocess.check_output(
            cmd, stderr=subprocess.DEVNULL,
        ).strip().decode('utf-8')
    except subprocess.CalledProcessError:
        return None


def from_git_rev_read(path):
    """Retrieve given file path contents of certain Git revision."""
    if ':' not in path:
        raise ValueError('Path identifier must start with a revision hash.')

    cmd = 'git', 'show', '-t', path
    try:
        return subprocess.check_output(cmd).rstrip().decode('utf-8')
    except subprocess.CalledProcessError:
        raise ValueError


if __name__ == '__main__':
    cherry_pick_cli()
