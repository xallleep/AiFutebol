from setuptools import setup, find_packages

setup(
    name="futebol-predict",
    version="0.2",
    python_requires=">=3.10",
    packages=find_packages(),
    install_requires=[
        'flask>=3.0.2',
        'requests>=2.32.0',
        # outras dependências...
    ],
)