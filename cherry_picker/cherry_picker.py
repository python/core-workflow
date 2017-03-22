import click
import os
import subprocess
import webbrowser
import sys


@click.command()
@click.option('--dry-run', is_flag=True)
@click.option('--push', 'pr_remote', metavar='REMOTE',
              help='git remote to use for PR branches', default='origin')
@click.argument('commit_sha1', 'The commit sha1 to be cherry-picked')
@click.argument('branches', 'The branches to backport to', nargs=-1)
def cherry_pick(dry_run, pr_remote, commit_sha1, branches):
    if not os.path.exists('./pyconfig.h.in'):
        os.chdir('./cpython/')

    upstream = get_git_fetch_remote()
    username = get_forked_repo_name(pr_remote)

    if dry_run:
       click.echo("Dry run requested, listing expected command sequence")


    click.echo("fetching upstream ...")
    run_cmd(f"git fetch {upstream}", dry_run=dry_run)

    if not branches:
        raise ValueError("at least one branch is required")

    for branch in branches:
        click.echo(f"Now backporting '{commit_sha1}' into '{branch}'")

        # git checkout -b 61e2bc7-3.5 upstream/3.5
        cherry_pick_branch = f"backport-{commit_sha1[:7]}-{branch}"
        pr_url = get_pr_url(username, branch, cherry_pick_branch)
        cmd = f"git checkout -b {cherry_pick_branch} {upstream}/{branch}"
        run_cmd(cmd, dry_run=dry_run)

        cmd = f"git cherry-pick -x {commit_sha1}"
        if run_cmd(cmd, dry_run=dry_run):
            cmd = f"git push {pr_remote} {cherry_pick_branch}"
            if not run_cmd(cmd, dry_run=dry_run):
                click.echo(f"Failed to push to {pr_remote} :(")
            else:
                open_pr(pr_url, dry_run=dry_run)
            click.echo(f"Success to cherry-pick {commit_sha1}")
            cleanup_branch(cherry_pick_branch, dry_run)
        else:
            click.echo(f"Failed to cherry-pick {commit_sha1} into {branch} :(")
            if not handle_failed_cherry_pick(cherry_pick_branch, dry_run):
                click.echo(" ... ")
                click.echo("To continue manually: ")
                click.echo("    $ cd cpython")
                click.echo("    Fix the conflict, and commit.")
                click.echo(f"    $ git push origin {pr_remote} {cherry_pick_branch}")
                click.echo(f"    Go to {pr_url}")
                click.echo("    $ git checkout master")
                click.echo(f"    $ git branch -D {cherry_pick_branch}")
                click.echo("To cancel (from cpython directory):")
                click.echo("    $ git cherry-pick --abort")
                click.echo("    $ git checkout master")
                click.echo(f"    $ git branch -D {cherry_pick_branch}")
                sys.exit(-1)


def cleanup_branch(cherry_pick_branch, dry_run):
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


def handle_failed_cherry_pick(cherry_pick_branch, dry_run):
    """

    """
    click.echo("")
    click.echo("1.  Stop now, and resolve this manually.")
    click.echo("2.  Skip, and continue cherry-picking the next branch.")
    value = click.prompt('What should we do?', type=int, default=1)
    if value == 1:
        # User want to finish cherry-picking themselves
        return False
    else:
        # continue with the next branch
        click.echo("Aborting ... ")
        run_cmd("git cherry-pick --abort")
        cleanup_branch(cherry_pick_branch, dry_run)
        return True


def run_cmd(cmd, *, dry_run=False):
    if dry_run:
        click.echo(f"  dry-run: {cmd}")
        return True
    try:
        subprocess.check_output(cmd.split())
    except subprocess.CalledProcessError as err_message:
        click.echo(f"error is {err_message}")
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


if __name__ == '__main__':
    cherry_pick()
