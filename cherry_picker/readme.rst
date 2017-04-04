Usage::
   
   python -m cherry_picker [--push REMOTE] [--dry-run] [--status] [--abort/--continue] <commit_sha1> <branches>
   


.. contents::

About
=====

Use this to backport cpython changes from ``master`` into one or more of the
maintenance branches (``3.6``, ``3.5``, ``2.7``).

It will prefix the commit message with the branch, e.g. ``[3.6]``, and then
opens up the pull request page.

This script will become obsolete once the cherry-picking bot is implemented.

Tests are to be written using pytest.


Setup Info
==========

Requires Python 3.6.

::

    $ git clone https://github.com/python/core-workflow.git
    $ cd core-workflow/cherry_picker
    $ python -m venv venv
    $ source venv/bin/activate
    (venv) $ python -m pip install -r requirements.txt
    (venv) $ git clone https://github.com/<username>/cpython.git  # your own cpython fork
    (venv) $ cd cpython
    (venv) $ git remote add upstream https://github.com/python/cpython.git
    (venv) $ cd ../

The cherry picking script assumes that if an `upstream` remote is defined, then
it should be used as the source of upstream changes and as the base for
cherry-pick branches. Otherwise, `origin` is used for that purpose.

By default, the PR branches used to submit pull requests back to the main
repository are pushed to `origin`. If this is incorrect, then the correct
remote will need be specified using the ``--push`` option (e.g.
``--push pr`` to use a remote named ``pr``).


Cherry-picking :snake: :cherries: :pick:
==============

(Setup first! See prev section)

::

    (venv) $ python -m cherry_picker [--dry-run] [--abort/--continue] [--status] <commit_sha1> <branches>

The commit sha1 is obtained from the merged pull request on ``master``.


Options
-------

::

    -- dry-run      Dry Run Mode.  Prints out the commands, but not executed.
    -- push REMOTE  Specify the branch to push into.  Default is 'origin'.
    -- status       Do `git status` in cpython directory.


Additional options::

    -- abort        Abort current cherry-pick and clean up branch
    -- continue     Continue cherry-pick, push, and clean up branch


Demo
----

https://asciinema.org/a/dtayqmjvd5hy5389oubkdk323


Example
-------

For example, to cherry-pick ``6de2b7817f-some-commit-sha1-d064`` into
``3.5`` and ``3.6``:

::

    (venv) $ python -m cherry_picker 6de2b7817f-some-commit-sha1-d064 3.5 3.6


What this will do:

::

    (venv) $ cd cpython
    
    (venv) $ git fetch upstream
    
    (venv) $ git checkout -b backport-6de2b78-3.5 upstream/3.5
    (venv) $ git cherry-pick -x 6de2b7817f-some-commit-sha1-d064 
    (venv) $ git push origin backport-6de2b78-3.5
    (venv) $ git checkout master
    (venv) $ git branch -D backport-6de2b78-3.5
    
    (venv) $ git checkout -b backport-6de2b78-3.6 upstream/3.6
    (venv) $ git cherry-pick -x 6de2b7817f-some-commit-sha1-d064 
    (venv) $ git push origin backport-6de2b78-3.6
    (venv) $ git checkout master
    (venv) $ git branch -D backport-6de2b78-3.6

In case of merge conflicts or errors, the following message will be displayed::

    Failed to cherry-pick 554626ada769abf82a5dabe6966afa4265acb6a6 into 2.7 :frowning_face:
    ... Stopping here.

    To continue and resolve the conflict:
        $ python -m cherry_picker --status  # to find out which files need attention
        $ cd cpython
        # Fix the conflict
        $ cd ..
        $ python -m cherry_picker --status  # should now say 'all conflict fixed'
        $ python -m cherry_picker --continue

    To abort the cherry-pick and cleanup:
        $ python -m cherry_picker --abort


Passing the `--dry-run` option will cause the script to print out all the
steps it would execute without actually executing any of them. For example::

    $ python -m cherry_picker --dry-run --push pr 1e32a1be4a1705e34011770026cb64ada2d340b5 3.6 3.5
    Dry run requested, listing expected command sequence
    fetching upstream ...
    dry_run: git fetch origin
    Now backporting '1e32a1be4a1705e34011770026cb64ada2d340b5' into '3.6'
    dry_run: git checkout -b backport-1e32a1b-3.6 origin/3.6
    dry_run: git cherry-pick -x 1e32a1be4a1705e34011770026cb64ada2d340b5
    dry_run: git push pr backport-1e32a1b-3.6
    dry_run: Create new PR: https://github.com/python/cpython/compare/3.6...ncoghlan:backport-1e32a1b-3.6?expand=1
    dry_run: git checkout master
    dry_run: git branch -D backport-1e32a1b-3.6
    Now backporting '1e32a1be4a1705e34011770026cb64ada2d340b5' into '3.5'
    dry_run: git checkout -b backport-1e32a1b-3.5 origin/3.5
    dry_run: git cherry-pick -x 1e32a1be4a1705e34011770026cb64ada2d340b5
    dry_run: git push pr backport-1e32a1b-3.5
    dry_run: Create new PR: https://github.com/python/cpython/compare/3.5...ncoghlan:backport-1e32a1b-3.5?expand=1
    dry_run: git checkout master
    dry_run: git branch -D backport-1e32a1b-3.5


`--status` option
-----------------

This will do `git status` for the CPython directory.

`--abort` option
----------------

Cancels the current cherry-pick and cleans up the cherry-pick branch.

`--continue` option
-------------------

Continues the current cherry-pick, commits, pushes the current branch to origin,
opens the PR page, and cleans up the branch.

Creating Pull Requests
======================

When a cherry-pick was applied successfully, this script will open up a browser
tab that points to the pull request creation page.

The url of the pull request page looks similar to the following::

   https://github.com/python/cpython/compare/3.5...<username>:backport-6de2b78-3.5?expand=1


1. Apply the appropriate ``cherry-pick for ...`` label

2. Press the ``Create Pull Request`` button.

3. Remove the ``needs backport to ...`` label from the original pull request
   against ``master``.


Running Tests
=============

Install pytest: ``pip install -U pytest``

::

    $ pytest test.py
