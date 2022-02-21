from setuptools import setup

import re
def grep(attrname, file_text):
    pattern = r"{0}\W*=\W*'([^']+)'".format(attrname)
    strval, = re.findall(pattern, file_text)
    return strval


# find version number from __init__.py
with open('exectr/__init__.py', 'r') as f:
    VERSION = grep('__version__', f.read())

setup(
    name="exectr",
    description="The shell-script executor you didn't know you needed",
    author='Daniel Dugas',
    version=VERSION,
    packages=[],
    scripts=['scripts/executor'],
    python_requires='>=3.6, <3.7',
    install_requires=[
        "pexpect",
        "strictfire",
        "Pygments",
    ],
)
