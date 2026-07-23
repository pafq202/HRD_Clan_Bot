import os
from pathlib import Path

# 프로젝트 루트 디렉토리
directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 주요 디렉토리 경로
CONFIG_DIR = os.path.join(directory, "config")
COGS_DIR = os.path.join(directory, "cogs")
DATA_DIR = os.path.join(directory, "data")
UTILS_DIR = os.path.join(directory, "utils")

# 디렉토리 생성
for dir_path in [CONFIG_DIR, COGS_DIR, DATA_DIR, UTILS_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        print(f"✅ 디렉토리 생성: {dir_path}")
