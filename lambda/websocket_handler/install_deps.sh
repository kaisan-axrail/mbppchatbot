#!/bin/bash
# Install dependencies for Lambda x86_64 architecture

pip install -r requirements.txt \
    --python-version 3.11 \
    --platform manylinux2014_x86_64 \
    --target . \
    --only-binary=:all: \
    --upgrade
