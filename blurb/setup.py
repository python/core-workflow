from setuptools import setup

description = "Command-line tool to manage CPython Misc/NEWS entries"

setup(
    name='blurb',
    description=description,
    long_description=description,
    license='License :: OSI Approved :: BSD License',
    url='https://github.com/python/core-workflow',
    author='Larry Hastings',
    author_email='larry@hastings.org',
    maintainer='Python Core Developers',
    maintainer_email='core-workflow@mail.python.org',
    version='1.0',
    scripts=[
        'blurb',
    ],
    classifiers=[
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
    ],
)
