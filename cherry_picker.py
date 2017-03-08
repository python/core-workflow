import click
import os
import subprocess
import webbrowser


@click.command()
@click.argument('commit_sha1', 'The commit sha1 to be cherry-picked')
@click.argument('branches', 'The branches to backport to', nargs=-1)
def cherry_pick(commit_sha1, branches):
    os.chdir('./cpython/')
    upstream = get_git_upstream_remote()
    username = get_forked_repo_name()

    click.echo("fetchin upstream")
    run_cmd(f"git fetch {upstream}")

    if not branches:
        raise ValueError("at least one branch is required")

    for branch in branches:
        click.echo(f"Now backporting '{commit_sha1}' into '{branch}'")

        # git checkout -b 61e2bc7-3.5 upstream/3.5
        cherry_pick_branch = f"{commit_sha1[:7]}-{branch}"
        cmd = f"git checkout -b {cherry_pick_branch} {upstream}/{branch}"
        run_cmd(cmd)

        cmd = f"git cherry-pick -x {commit_sha1}"
        if run_cmd(cmd):
            cmd = f"git push origin {cherry_pick_branch}"
            if not run_cmd(cmd):
                click.echo(f"Failed to push to origin :(")
            else:
                open_pr(username, branch, cherry_pick_branch)
        else:
            click.echo(f"Failed to cherry-pick {commit_sha1} into {branch} :(")

        cmd = "git checkout master"
        run_cmd(cmd)

        cmd = f"git branch -D {cherry_pick_branch}"
        if run_cmd(cmd):
            click.echo(f"branch {cherry_pick_branch} has been deleted.")
        else:
            click.echo(f"branch {cherry_pick_branch} NOT deleted.")


def get_git_upstream_remote():
    """Get the remote name to use for upstream branches
    Uses "upstream" if it exists, "origin" otherwise
    """
    cmd = "git remote get-url upstream"
    if run_cmd(cmd):
        return "upstream"
    else:
        return "origin"


def get_forked_repo_name():
    """
    Return 'myusername' out of https://github.com/myusername/cpython
    :return:
    """
    cmd = "git config --get remote.origin.url"
    result = subprocess.check_output(cmd.split(), stderr=subprocess.STDOUT).decode('utf-8')
    username = result[len("https://github.com/"):result.index('/cpython.git')]
    return username


def run_cmd(cmd):
    try:
        subprocess.check_output(cmd.split())
    except subprocess.CalledProcessError:
        return False
    return True


def open_pr(forked_repo, base_branch, cherry_pick_branch):
    """
    construct the url for pull request and open it in the web browser
    """
    url = f"https://github.com/python/cpython/compare/{base_branch}...{forked_repo}:{cherry_pick_branch}?expand=1"
    webbrowser.open_new_tab(url)


if __name__ == '__main__':
    cherry_pick()
