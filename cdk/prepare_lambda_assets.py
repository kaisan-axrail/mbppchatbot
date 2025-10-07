#!/usr/bin/env python3
"""Prepare Lambda assets by copying shared files."""
import shutil
import os

# Copy vector search to Lambda functions
shared_files = [
    'shared/vector_rag_handler.py'
]

lambda_dirs = [
    'lambda/mcp_server/shared',
    'lambda/websocket_handler/shared'
]

for shared_file in shared_files:
    if os.path.exists(f'../{shared_file}'):
        for lambda_dir in lambda_dirs:
            dest = f'../{lambda_dir}/{os.path.basename(shared_file)}'
            shutil.copy(f'../{shared_file}', dest)
            print(f'Copied {shared_file} to {lambda_dir}')
