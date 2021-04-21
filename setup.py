from setuptools import setup

setup(
    name='pyssimist',
    version='0.1.0',
    packages=['sip', 'csta', 'common', 'tshark_tools'],
    url='https://github.com/skarcos/pyssimist',
    package_data={"csta": ["CstaPool/*.xml"]},
    license='GPL-3.0',
    author='Costas Skarakis',
    author_email='skarcos@gmail.com',
    description='A Python Network Traffic Simulator... It\'s probably not going to work.'
)
