from setuptools import setup


with open('cherry_picker/readme.rst') as f:
    long_description = f.read()


with open('cherry_picker/requirements.txt') as f:
    requirements = [l.strip() for l in f.read().split('\n')]


setup(
    name='cherry_picker',
    description='backport cpython changes from master to maintenance branches',
    long_description=long_description,
    license='Apache',
    url='https://github.com/python/core-workflow',
    author='Mariatta Wijaya',
    author_email='mariatta.wijaya@gmail.com',
    maintainer='Python Core Developers',
    maintainer_email='core-workflow@mail.python.org',
    packages=[
        'cherry_picker',
    ],
    entry_points={
        'console_scripts': [
            'cherry_picker = cherry_picker.cherry_picker:cherry_pick_cli',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: Developers',
    ],
    install_requires=requirements,
)
