""" Setup file for Picopt
Reference:
https://hynek.me/articles/sharing-your-labor-of-love-pypi-quick-and-dirty/
"""
from setuptools import setup
from pip.req import parse_requirements

__version__ = "1.1.1"
README_FILENAME = "README.rst"
REQUIREMENTS_FILENAME = "requirements.txt"

with open(README_FILENAME, 'r') as readme_file:
    LONG_DESCRIPTION = readme_file.read()

INSTALL_REQS = parse_requirements(REQUIREMENTS_FILENAME)
REQ_LIST = [str(ir.req) for ir in INSTALL_REQS]

setup(
    name='picopt',
    version=__version__,
    description='Optimize image files and comic archives with external tools',
    author='AJ Slater',
    author_email='aj@slater.net',
    url='https://github.com/ajslater/picopt/',
    py_modules=['picopt'],
    install_requires=REQ_LIST,
    entry_points={
        'console_scripts': [
            'picopt = picopt:main'
        ]
    },
    long_description=LONG_DESCRIPTION,
    license="GPLv2",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: System Administrators',
        'Natural Language :: English',
        'Environment :: Console',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Topic :: Internet :: WWW/HTTP :: Site Management',
        'Topic :: Multimedia :: Graphics :: Graphics Conversion'
    ],
)
