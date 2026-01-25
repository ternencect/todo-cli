#!/usr/bin/env python3
"""
todo-cli 安装脚本
"""
from setuptools import setup, find_packages
import os

# 读取 README
def read_file(filename):
    with open(os.path.join(os.path.dirname(__file__), filename), encoding='utf-8') as f:
        return f.read()

setup(
    name='todo-cli',
    version='1.0.0',
    description='一个功能完整的命令行待办事项管理工具',
    long_description=read_file('README.md'),
    long_description_content_type='text/markdown',
    author='ternencect',
    author_email='ternencect@users.noreply.github.com',
    url='https://github.com/ternencect/todo-cli',
    packages=find_packages(),
    py_modules=['todo'],
    entry_points={
        'console_scripts': [
            'todo-cli=todo:main',
        ],
    },
    python_requires='>=3.7',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'Topic :: Utilities',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Environment :: Console',
        'Operating System :: OS Independent',
    ],
    keywords='todo task management cli command-line',
    license='MIT',
)
