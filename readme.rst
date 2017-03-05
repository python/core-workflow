Setup Info
==========

Requires Python 3.6 and virtualenv.

::

    $ git clone https://github.com/Mariatta/chic_a_cherry_picker.git
    $ cd chic_a_cherry_picker
    $ virtualenv venv
    $ source venv/bin/activate
    (venv) $ pip install -r requirements.txt
    (venv) $ git clone https://github.com/Mariatta/cpython.git  #or your own cpython fork
    (venv) $ cd cpython
    (venv) $ git remote add upstream https://github.com/python/cpython.git
    (venv) $ cd ../


Cherry-picking
==============

(Setup first! See prev section)

::

    (venv) $ python -m cherry_picker <commit_sha1> <branches>

The commit sha1 is obtained from the merged pull request on master. 

For example, to cherry-pick `6de2b7817f-some-commit-sha1-d064` into
`3.5` and `3.6`:

::

    (venv) $ python -m cherry_picker 6de2b7817f-some-commit-sha1-d064 3.5 3.6


What this will do:

::

    (venv) $ cd cpython
    
    (venv) $ git fetch upstream
    
    (venv) $ git checkout -b 6de2b78-3.5 upstream/3.5
    (venv) $ git cherry-pick -x 6de2b7817f-some-commit-sha1-d064 
    (venv) $ git push origin 6de2b78-3.5
    (venv) $ git checkout master
    (venv) $ git branch -D 6de2b78-3.5
    
    (venv) $ git checkout -b 6de2b78-3.6 upstream/3.6
    (venv) $ git cherry-pick -x 6de2b7817f-some-commit-sha1-d064 
    (venv) $ git push origin 6de2b78-3.6
    (venv) $ git checkout master
    (venv) $ git branch -D 6de2b78-3.6
    


Then go to https://github.com/python/cpython to create the pull requests.

In case of merge conflicts or errors, then... the script will fail :P
