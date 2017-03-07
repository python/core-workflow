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

    for branch in branches:
        click.echo(f"Now backporting '{commit_sha1}' into '{branch}'")

        # git checkout -b 61e2bc7-3.5 upstream/3.5
        cmd = f"git checkout -b {commit_sha1[:7]}-{branch} {upstream}/{branch}"
        run_cmd(cmd)

        cmd = f"git cherry-pick -x {commit_sha1}"
        if run_cmd(cmd):
            cmd = f"git push origin {commit_sha1[:7]}-{branch}"
            if not run_cmd(cmd):
                click.echo(f"Failed to push to origin :(")
        else:
            click.echo(f"Failed to cherry-pick {commit_sha1} into {branch} :(")

        cmd = "git checkout master"
        run_cmd(cmd)

        cmd = f"git branch -D {commit_sha1[:7]}-{branch}"
        run_cmd(cmd)
        click.echo(f"branch {commit_sha1[:7]}-{branch} has been deleted.")


def get_git_upstream_remote():
    """Get the remote name to use for upstream branches
    Uses "upstream" if it exists, "origin" otherwise
    """
    cmd = "git remote get-url upstream"
    if run_cmd(cmd):
        return "origin"
    else:
        return "upstream"


def run_cmd(cmd):
    try:
        subprocess.check_output(cmd.split())
    except subprocess.CalledProcessError:
        return False
    return True


if __name__ == '__main__':
    cherry_pick()
