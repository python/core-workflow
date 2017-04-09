#!/usr/bin/env python3
#  -*- coding: utf-8 -*-

import click
import os
import subprocess
import webbrowser


@click.command()
@click.option('--dry-run', is_flag=True,
              help="Prints out the commands, but not executed.")
@click.option('--push', 'pr_remote', metavar='REMOTE',
              help='git remote to use for PR branches', default='origin')
@click.option('--abort', 'abort', flag_value=True, default=None,
              help="Abort current cherry-pick and clean up branch")
@click.option('--continue', 'abort', flag_value=False, default=None,
              help="Continue cherry-pick, push, and clean up branch")
@click.argument('commit_sha1', 'The commit sha1 to be cherry-picked', nargs=1,
                default = "")
@click.argument('branches', 'The branches to backport to', nargs=-1)
def cherry_pick(dry_run, pr_remote, abort, commit_sha1, branches):
    click.echo("\U0001F40D \U0001F352 \u26CF ")
    if not os.path.exists('./pyconfig.h.in'):
        os.chdir('./cpython/')

    upstream = get_git_fetch_remote()
    username = get_forked_repo_name(pr_remote)

    if dry_run:
       click.echo("Dry run requested, listing expected command sequence")

    if abort is not None:
        if abort:
            abort_cherry_pick(dry_run=dry_run)
        else:
            continue_cherry_pick(username, pr_remote, dry_run=dry_run)

    else:
        backport_branches(commit_sha1, branches, username, upstream, pr_remote,
                          dry_run=dry_run)

def backport_branches(commit_sha1, branches, username, upstream, pr_remote,
                      *, dry_run=False):
    if commit_sha1 == "":
        raise ValueError("Missing the commit_sha1 argument.")
    if not branches:
        raise ValueError("At least one branch is required.")
    else:
        run_cmd(f"git fetch {upstream}", dry_run=dry_run)

        for branch in get_sorted_branch(branches):
            click.echo(f"Now backporting '{commit_sha1}' into '{branch}'")

            # git checkout -b backport-61e2bc7-3.5 upstream/3.5
            cherry_pick_branch = f"backport-{commit_sha1[:7]}-{branch}"
            pr_url = get_pr_url(username, branch, cherry_pick_branch)
            cmd = f"git checkout -b {cherry_pick_branch} {upstream}/{branch}"
            run_cmd(cmd, dry_run=dry_run)

            cmd = f"git cherry-pick -x {commit_sha1}"
            if run_cmd(cmd, dry_run=dry_run):
                push_to_remote(pr_url, pr_remote, cherry_pick_branch, dry_run=dry_run)
                cleanup_branch(cherry_pick_branch, dry_run=dry_run)
            else:
                click.echo(f"Failed to cherry-pick {commit_sha1} into {branch} \u2639")
                click.echo(" ... Stopping here. ")

                click.echo("")
                click.echo("To continue and resolve the conflict: ")
                click.echo("    $ cd cpython")
                click.echo("    $ git status # to find out which files need attention")
                click.echo("    # Fix the conflict")
                click.echo("    $ git status # should now say `all conflicts fixed`")
                click.echo("    $ cd ..")
                click.echo("    $ python -m cherry_picker --continue")

                click.echo("")
                click.echo("To abort the cherry-pick and cleanup: ")
                click.echo("    $ python -m cherry_picker --abort")


def abort_cherry_pick(*, dry_run=False):
    """
    run `git cherry-pick --abort` and then clean up the branch
    """
    if run_cmd("git cherry-pick --abort", dry_run=dry_run):
        cleanup_branch(get_current_branch(), dry_run=dry_run)


def continue_cherry_pick(username, pr_remote, *, dry_run=False):
    """
    git push origin <current_branch>
    open the PR
    clean up branch

    """
    cherry_pick_branch = get_current_branch()
    if cherry_pick_branch != 'master':

        # this has the same effect as `git cherry-pick --continue`
        cmd = f"git commit -am 'Resolved.' --allow-empty"
        run_cmd(cmd, dry_run=dry_run)

        base_branch = get_base_branch(cherry_pick_branch)
        pr_url = get_pr_url(username, base_branch, cherry_pick_branch)
        push_to_remote(pr_url, pr_remote, cherry_pick_branch, dry_run=dry_run)

        cleanup_branch(cherry_pick_branch, dry_run=dry_run)
    else:
        click.echo(u"Refuse to push to master \U0001F61B")


def get_base_branch(cherry_pick_branch):
    """
    return '2.7' from 'backport-sha-2.7'
    """
    return cherry_pick_branch[cherry_pick_branch.rfind('-')+1:]


def cleanup_branch(cherry_pick_branch, *, dry_run=False):
    """
    git checkout master
    git branch -D <branch to delete>
    """
    cmd = "git checkout master"
    run_cmd(cmd, dry_run=dry_run)

    cmd = f"git branch -D {cherry_pick_branch}"
    if run_cmd(cmd, dry_run=dry_run):
        if not dry_run:
            click.echo(f"branch {cherry_pick_branch} has been deleted.")
    else:
        click.echo(f"branch {cherry_pick_branch} NOT deleted.")

def push_to_remote(pr_url, pr_remote, cherry_pick_branch, *, dry_run=False):
    cmd = f"git push {pr_remote} {cherry_pick_branch}"
    if not run_cmd(cmd, dry_run=dry_run):
        click.echo(f"Failed to push to {pr_remote} \u2639")
    else:
        open_pr(pr_url, dry_run=dry_run)

def get_git_fetch_remote():
    """Get the remote name to use for upstream branches
    Uses "upstream" if it exists, "origin" otherwise
    """
    cmd = "git remote get-url upstream"
    try:
        subprocess.check_output(cmd.split(), stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return "origin"
    return "upstream"


def get_forked_repo_name(pr_remote):
    """
    Return 'myusername' out of https://github.com/myusername/cpython
    """
    cmd = f"git config --get remote.{pr_remote}.url"
    raw_result = subprocess.check_output(cmd.split(), stderr=subprocess.STDOUT)
    result = raw_result.decode('utf-8')
    username_end = result.index('/cpython.git')
    if result.startswith("https"):
        username = result[len("https://github.com/"):username_end]
    else:
        username = result[len("git@github.com:"):username_end]
    return username


def run_cmd(cmd, *, dry_run=False):
    if dry_run:
        click.echo(f"  dry-run: {cmd}")
        return True
    try:
        subprocess.check_output(cmd.split())
    except subprocess.CalledProcessError:
        return False
    return True


def get_pr_url(forked_repo, base_branch, cherry_pick_branch):
    """
    construct the url for the pull request
    """
    return f"https://github.com/python/cpython/compare/{base_branch}...{forked_repo}:{cherry_pick_branch}?expand=1"


def open_pr(url, *, dry_run=False):
    """
    open url in the web browser
    """
    if dry_run:
        click.echo(f"  dry-run: Create new PR: {url}")
        return
    webbrowser.open_new_tab(url)


def get_current_branch():
    """
    Return the current branch
    """
    cmd = "git symbolic-ref HEAD | sed 's!refs\/heads\/!!'"
    output = subprocess.check_output(cmd, shell=True)
    return output.strip().decode()


def get_sorted_branch(branches):
    return sorted(
        branches,
        reverse=True,
        key=lambda v: tuple(map(int, v.split('.'))))


if __name__ == '__main__':
    cherry_pick()
