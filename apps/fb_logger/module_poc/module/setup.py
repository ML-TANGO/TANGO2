from setuptools import setup, find_packages

setup(
    name='fb_logging',
    version='0.1',
    packages=find_packages(),
    install_requires=[],
    entry_points={},
    author='min',
    author_email='min@acryl.ai',
    description='A custom logging module for jonathan flightbase or other products',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://acryl.ai',
    classifiers=[
        'Programming Language :: Python :: 3',
    ],
)
