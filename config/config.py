import os
import configparser
from pathlib import Path

# 프로젝트 루트 디렉토리
ROOT_DIR = Path(__file__).parent.parent
CONFIG_DIR = ROOT_DIR / 'config'

def get_config(config_name: str) -> configparser.ConfigParser:
    """
    설정 파일을 읽어서 ConfigParser 객체를 반환합니다.
    
    Args:
        config_name: 설정 파일 이름 (확장자 제외)
        ex) 'config', 'comment'
    
    Returns:
        configparser.ConfigParser: 설정 파일 파서
    """
    parser = configparser.ConfigParser()
    config_file = CONFIG_DIR / f"{config_name}.ini"
    
    if not config_file.exists():
        print(f"⚠️ 경고: {config_file} 파일을 찾을 수 없습니다.")
        return parser
    
    try:
        parser.read(config_file, encoding='utf-8')
        print(f"✅ 설정 파일 로드: {config_file}")
    except Exception as e:
        print(f"❌ 설정 파일 읽기 오류: {e}")
    
    return parser

# 기본 설정 파일 로드
config = get_config('config')
comment = get_config('comment')
