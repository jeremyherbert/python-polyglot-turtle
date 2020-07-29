import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="polyglot-turtle",
    version="0.0.1",
    author="Jeremy Herbert",
    author_email="jeremy.006@gmail.com",
    description="A python driver for the polyglot-turtle firmware",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jeremyherbert/python-polyglot-turtle",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=['hidapi', 'cbor2', 'packaging'],
    python_requires='>=3.6',
)