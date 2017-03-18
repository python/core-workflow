Usage::
   
   python -m cherry_picker [--push REMOTE] [--dry-run] <commit_sha1> <branches>
   


.. contents::

About
=====

Use this to backport cpython changes from ``master`` into one or more of the maintenance
branches (``3.6``, ``3.5``, ``2.7``).  

This script will become obsolete once the cherry-picking bot is implemented.

There is no unit tests :sob: .... I tested this in production :sweat_smile:


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

    (venv) $ python -m cherry_picker <commit_sha1> <branches>

The commit sha1 is obtained from the merged pull request on ``master``. 

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

In case of merge conflicts or errors, then... the script will fail :stuck_out_tongue:

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

Creating Pull Requests
======================

When a cherry-pick was applied successfully, this script will open up a browser
tab that points to the pull request creation page.

The url of the pull request page looks similar to the following::

   https://github.com/python/cpython/compare/3.5...<username>:backport-6de2b78-3.5?expand=1


1. Prefix the pull request description with the branch ``[X.Y]``, e.g.::

     [3.6] bpo-xxxxx: Fix this and that

2. Apply the appropriate ``cherry-pick for ...`` label

3. Press the ``Create Pull Request`` button.

4. Remove the ``needs backport to ...`` label from the original pull request
   against ``master``.
