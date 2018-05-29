#!/usr/bin/env python3
#  -*- coding: utf-8 -*-

import click
import collections
import os
import pathlib
import subprocess
import webbrowser
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
    'fix_commit_msg': True
})


class BranchCheckoutException(Exception):
    pass


class CherryPickException(Exception):
    pass


class InvalidRepoException(Exception):
    pass


class CherryPicker:

    def __init__(self, pr_remote, commit_sha1, branches,
                 *, dry_run=False, push=True,
                 prefix_commit=True,
                 config=DEFAULT_CONFIG,
                 ):

        self.config = config
        self.check_repo()  # may raise InvalidRepoException

        if dry_run:
            click.echo("Dry run requested, listing expected command sequence")

        self.memorized_branch = get_current_branch() or 'master'

        self.pr_remote = pr_remote
        self.commit_sha1 = commit_sha1
        self.branches = branches
        self.dry_run = dry_run
        self.push = push
        self.prefix_commit = prefix_commit

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
        return sorted(
            self.branches,
            reverse=True,
            key=lambda v: tuple(map(int, v.split('.'))))

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
        cmd = ['git', 'fetch', self.upstream]
        self.run_cmd(cmd)

    def run_cmd(self, cmd):
        assert not isinstance(cmd, str)
        if self.dry_run:
            click.echo(f"  dry-run: {' '.join(cmd)}")
            return
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        click.echo(output.decode('utf-8'))
        return output

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

        cmd = 'git', 'checkout', self.memorized_branch
        self.run_cmd(cmd)

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

        cmd = ['git', 'push', self.pr_remote, head_branch]
        try:
            self.run_cmd(cmd)
        except subprocess.CalledProcessError:
            click.echo(f"Failed to push to {self.pr_remote} \u2639")
        else:
            gh_auth = os.getenv("GH_AUTH")
            if gh_auth:
                self.create_gh_pr(base_branch, head_branch,
                                  commit_message=commit_message,
                                  gh_auth=gh_auth)
            else:
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
        self.checkout_default_branch()
        try:
            self.delete_branch(branch)
        except subprocess.CalledProcessError:
            click.echo(f"branch {branch} NOT deleted.")
        else:
            click.echo(f"branch {branch} has been deleted.")

    def backport(self):
        if not self.branches:
            raise click.UsageError("At least one branch must be specified.")
        self.fetch_upstream()

        for maint_branch in self.sorted_branches:
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

    def abort_cherry_pick(self):
        """
        run `git cherry-pick --abort` and then clean up the branch
        """
        cmd = ['git', 'cherry-pick', '--abort']
        try:
            self.run_cmd(cmd)
        except subprocess.CalledProcessError as cpe:
            click.echo(cpe.output)
        # only delete backport branch created by cherry_picker.py
        if get_current_branch().startswith('backport-'):
            self.cleanup_branch(get_current_branch())

    def continue_cherry_pick(self):
        """
        git push origin <current_branch>
        open the PR
        clean up branch
        """
        cherry_pick_branch = get_current_branch()
        if cherry_pick_branch.startswith('backport-'):
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

        else:
            click.echo(f"Current branch ({cherry_pick_branch}) is not a backport branch.  Will not continue. \U0001F61B")

    def check_repo(self):
        # CPython repo has a commit with
        # SHA=7f777ed95a19224294949e1b4ce56bbffcb1fe9f
        cmd = ['git', 'log', '-r', self.config['check_sha']]
        try:
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.SubprocessError:
            raise InvalidRepoException()


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
                    "from project root by default"),
              default=None)
@click.argument('commit_sha1', 'The commit sha1 to be cherry-picked', nargs=1,
                default = "")
@click.argument('branches', 'The branches to backport to', nargs=-1)
def cherry_pick_cli(dry_run, pr_remote, abort, status, push, config_path,
                    commit_sha1, branches):

    click.echo("\U0001F40D \U0001F352 \u26CF")

    config = load_config(config_path)

    try:
        cherry_picker = CherryPicker(pr_remote, commit_sha1, branches,
                                     dry_run=dry_run,
                                     push=push, config=config)
    except InvalidRepoException:
        click.echo(f"You're not inside a {config['repo']} repo right now! \U0001F645")
        sys.exit(-1)

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
    """
    prefix, sep, base_branch = cherry_pick_branch.rpartition('-')
    return base_branch


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


def find_project_root():
    cmd = ['git', 'rev-parse', '--show-toplevel']
    output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    return pathlib.Path(output.decode('utf-8').strip())


def find_config():
    root = find_project_root()
    if root is not None:
        child = root / '.cherry_picker.toml'
        if child.exists() and not child.is_dir():
            return child
    return None


def load_config(path):
    if path is None:
        path = find_config()
    if path is None:
        return DEFAULT_CONFIG
    else:
        path = pathlib.Path(path)  # enforce a cast to pathlib datatype
        with path.open() as f:
            d = toml.load(f)
            return DEFAULT_CONFIG.new_child(d)


if __name__ == '__main__':
    cherry_pick_cli()
