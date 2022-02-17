from setuptools import setup

setup(
    name="exectr",
    description="The shell-script executor you didn't know you needed",
    author='Daniel Dugas',
    version='0.0.3',
    packages=[],
    scripts=['scripts/executor'],
    python_requires='>=3.6, <3.7',
    install_requires=[
        "pexpect",
        "strictfire",
        "Pygments",
    ],
)
