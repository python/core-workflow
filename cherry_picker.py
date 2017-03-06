import click
import os
import subprocess


@click.command()
@click.argument('commit_sha1', 'The commit sha1 to cherry-pick')
@click.argument('branches', 'The branches to backport', nargs=-1)
def cherry_pick(commit_sha1, branches):
    os.chdir('./cpython/')
    upstream = get_git_upstream_remote()
    run_cmd(f"git fetch {upstream}")

    if not branches:
        raise ValueError("at least one branch is required")

    for b in branches:
        click.echo(f"branch to backport: '{b}'")
        click.echo(f"checkout the branch sha {commit_sha1[:7]}")

        # git checkout -b 61e2bc7-3.5 upstream/3.5
        cmd = f"git checkout -b {commit_sha1[:7]}-{b} {upstream}/{b}"
        run_cmd(cmd)

        cmd = f"git cherry-pick -x {commit_sha1}"
        run_cmd(cmd)

        cmd = f"git push origin {commit_sha1[:7]}-{b}"
        run_cmd(cmd)

        cmd = "git checkout master"
        run_cmd(cmd)

        cmd = f"git branch -D {commit_sha1[:7]}-{b}"
        run_cmd(cmd)


def get_git_upstream_remote():
    """Get the remote name to use for upstream branches
    Uses "upstream" if it exists, "origin" otherwise
    """
    cmd = "git remote get-url upstream"
    try:
        run_cmd(cmd)
    except subprocess.CalledProcessError:
        return "origin"
    return "upstream"


def run_cmd(cmd):
    subprocess.check_output(cmd.split())


if __name__ == '__main__':
    cherry_pick()
