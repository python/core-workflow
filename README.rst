core-workflow
=============
Issue tracker and relevant tools for CPython's workflow

.. image:: https://travis-ci.org/python/core-workflow.svg?branch=master
    :target: https://travis-ci.org/python/core-workflow

.. image:: https://img.shields.io/badge/zulip-join_chat-brightgreen.svg
   :alt: Python Zulip chat
   :target: https://python.zulipchat.com

cherry_picker 🐍 🍒 ⛏
----------------------

.. image:: https://img.shields.io/pypi/pyversions/cherry-picker.svg
    :target: https://pypi.org/project/cherry-picker/

.. image:: https://img.shields.io/pypi/v/cherry-picker.svg
    :target: https://pypi.org/project/cherry-picker/

.. image:: https://img.shields.io/pypi/l/cherry-picker.svg
    :target: https://github.com/python/core-workflow/blob/master/LICENSE/

Utility script for backporting/cherry-picking CPython changes from ``master``
into one of the maintenance branches.  See the cherry_picker_
directory for more details.

.. _cherry_picker: https://github.com/python/core-workflow/tree/master/cherry_picker


blurb
-----

.. image:: https://img.shields.io/pypi/v/blurb.svg
    :target: https://pypi.org/project/blurb/

Interactive utility for writing CPython ``Misc/NEWS.d`` entries. See
the blurb_ directory for more details.

.. _blurb: https://github.com/python/core-workflow/tree/master/blurb


Other core workflow tools
-------------------------

======================================= ======================= =============================================== ================
 Name                                   Description             Issue tracker                                   Owner/Maintainer
======================================= ======================= =============================================== ================
`python/bedevere`_                      A bot to help identify  `GitHub <https://github.com/                    `Brett Cannon`_
                                        missing information for python/bedevere/issues>`__
                                        CPython pull requests.
`python/blurb_it`_                      ``blurb add`` on the    `GitHub <https://github.com/                    `Mariatta`_
                                        web.                    python/blurb_it/issues>`__
`python/miss-islington`_                A bot for backporting   `GitHub <https://github.com/                    `Mariatta`_
                                        CPython pull requests.  python/miss-islington/issues>`__
`python/the-knights-who-say-ni`_        CLA enforcement bot for `GitHub <https://github.com/                    `Brett Cannon`_
                                        Python organization     python/the-knights-who-say-ni/issues>`__
                                        projects.
`berkerpeksag/cpython-emailer-webhook`_ A webhook to send every `GitHub <https://github.com/                    `Berker Peksag`_
                                        CPython commit to       berkerpeksag/cpython-emailer-webhook/issues>`__
                                        python-checkins mailing 
                                        list.
`berkerpeksag/cpython-bpo-linkify`_     An extension that finds `GitHub <https://github.com/                    `Berker Peksag`_
                                        bpo-NNNN annonations    berkerpeksag/cpython-bpo-linkify/issues>`__
                                        and converts them to    
                                        bugs.python.org links.  
======================================= ======================= =============================================== ================

.. _`python/bedevere`: https://github.com/python/bedevere
.. _`python/blurb_it`: https://github.com/python/blurb_it
.. _`python/miss-islington`: https://github.com/python/miss-islington
.. _`python/the-knights-who-say-ni`: https://github.com/python/the-knights-who-say-ni
.. _`berkerpeksag/cpython-emailer-webhook`: https://github.com/berkerpeksag/cpython-emailer-webhook
.. _`berkerpeksag/cpython-bpo-linkify`: https://github.com/berkerpeksag/cpython-bpo-linkify
.. _`Brett Cannon`: https://github.com/brettcannon
.. _`Berker Peksag`: https://github.com/berkerpeksag
.. _`Mariatta`: https://github.com/mariatta


