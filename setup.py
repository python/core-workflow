from setuptools import setup


with open('cherry_picker/requirements.txt') as f:
    requirements = [l.strip() for l in f.read().split('\n')]

description = "Tools for working with CPython's new core development workflow."

setup(
    name='core-workflow',
    description=description,
    long_description=description,
    license='Apache',
    url='https://github.com/python/core-workflow',
    author='Python Core Developers',
    author_email='core-workflow@mail.python.org',
    maintainer='Python Core Developers',
    maintainer_email='core-workflow@mail.python.org',
    version='0.0.3',
    packages=[
        'cherry_picker',
    ],
    entry_points={
        'console_scripts': [
            'cherry_picker = cherry_picker.cherry_picker:cherry_pick_cli',
            'blurb = blurb:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: Developers',
    ],
    install_requires=requirements,
)
