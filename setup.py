#!/usr/bin/env python
from setuptools import setup, find_packages

from mantis import VERSION

setup(
    name='mantis_cli',
    version=VERSION,
    description='Management command to build and deploy webapps, especially based on Django',
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    author='Erik Telepovský',
    author_email='info@pragmaticmates.com',
    maintainer='Pragmatic Mates',
    maintainer_email='info@pragmaticmates.com',
    url='https://github.com/PragmaticMates/mantis-cli',
    packages=find_packages(),
    include_package_data=True,
    # click is imported directly by command_line.py. It used to arrive transitively via typer,
    # but typer 0.27.0 dropped that dependency, so a fresh install lost it.
    install_requires=['cffi', 'click', 'cryptography', 'pycryptodome', 'pydantic', 'PyYAML', 'rich', 'typer'],
    entry_points={
        'console_scripts': ['mantis=mantis.command_line:run'],
    },
    classifiers=[
        'Programming Language :: Python',
        'Operating System :: OS Independent',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Framework :: Django',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Development Status :: 5 - Production/Stable'
    ],
    license='GNU General Public License (GPL)',
    keywords="management deployment docker command",
)
