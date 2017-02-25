#!/bin/bash
cd /home/akeil/code/steamwatch
python setup.py sdist

#pip=/home/akeil/.venvs/remindme/bin/pip
dist=file:///home/akeil/code/steamwatch/dist
#pip install --user --upgrade --force-reinstall --pre --no-deps --no-index --find-links "$dist" steamwatch
pip install --user --upgrade --force-reinstall --pre --find-links "$dist" steamwatch
