import discord
import os
from datetime import datetime
from utils.directory import directory

def get_server_info_path() -> str:
    """서버 정보 파일 경로 반환"""
    data_dir = os.path.join(directory, "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, "server_info.txt")

def get_server_log_path() -> str:
    """서버 로그 파일 경로 반환"""
    data_dir = os.path.join(directory, "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, "server_log.txt")

async def save_server_info(bot: discord.ext.commands.Bot):
    """
    봇의 모든 서버 정보를 텍스트 파일에 저장
    """
    try:
        file_path = get_server_info_path()
        
        # 서버 정보 수집
        guilds = bot.guilds
        total_servers = len(guilds)
        
        # 파일 내용 작성
        content = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += "📊 HRD Clan Bot - 서버 정보\n"
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # 봇 정보
        content += "🤖 봇 정보\n"
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += f"• 봇 이름: {bot.user.name}\n"
        content += f"• 봇 ID: {bot.user.id}\n"
        content += f"• 봇 버전: discord.py 2.3.2\n"
        content += f"• 등록된 서버: {total_servers}개\n\n"
        
        # 서버 목록
        content += "📋 서버 목록\n"
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        if total_servers == 0:
            content += "❌ 등록된 서버가 없습니다.\n\n"
        else:
            for index, guild in enumerate(guilds, 1):
                content += f"{index}️⃣ {guild.name}\n"
                content += f"   • 서버 ID: {guild.id}\n"
                content += f"   • 멤버 수: {guild.member_count}명\n"
                content += f"   • 채널 수: {len(guild.channels)}개\n"
                content += f"   • 생성일: {guild.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                content += f"   • 소유자: {guild.owner.mention if guild.owner else '알 수 없음'}\n\n"
        
        # 마지막 업데이트
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += f"⏰ 마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        # 파일 저장
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return True, total_servers, len(bot.cogs)
    
    except Exception as e:
        print(f"❌ 서버 정보 저장 오류: {e}")
        return False, 0, 0

def print_server_info(bot: discord.ext.commands.Bot):
    """
    터미널에 서버 정보 출력
    """
    guilds = bot.guilds
    total_servers = len(guilds)
    
    print("\n" + "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ 봇 준비 완료!")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"🤖 봇 이름: {bot.user.name}")
    print(f"🆔 봇 ID: {bot.user.id}")
    print(f"👥 등록된 서버 수: {total_servers}개")
    
    if total_servers > 0:
        print("\n" + "=========================================")
        print("📊 현재 서버 목록")
        print("=========================================")
        for guild in guilds:
            owner_name = guild.owner.name if guild.owner else "알 수 없음"
            print(f"{guild.name} , {owner_name} , 알 수 없음 , {guild.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=========================================\n")
    
    print("\n💾 서버 정보가 data/server_info.txt에 저장되었습니다!")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

def print_guild_list(bot: discord.ext.commands.Bot):
    """
    현재 서버 목록을 터미널에 출력
    """
    guilds = bot.guilds
    total_servers = len(guilds)
    
    if total_servers > 0:
        print("\n" + "=========================================")
        print("📊 현재 서버 목록")
        print("=========================================")
        for guild in guilds:
            owner_name = guild.owner.name if guild.owner else "알 수 없음"
            print(f"{guild.name} , {owner_name} , 알 수 없음 , {guild.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=========================================\n")

def print_guild_join(guild: discord.Guild):
    """
    새 서버 추가 시 터미널 출력 (간단한 형식)
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n✅ {timestamp} - {guild.name} 추가됨")

def print_guild_remove(guild: discord.Guild):
    """
    서버 제거 시 터미널 출력 (간단한 형식)
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"❌ {timestamp} - {guild.name} 제거됨")

def log_server_action(action: str, guild: discord.Guild):
    """
    서버 추가/제거 내역을 로그 파일에 기록
    """
    try:
        log_path = get_server_log_path()
        owner_name = guild.owner.name if guild.owner else "알 수 없음"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        log_entry = f"[{timestamp}] {action} - {guild.name} (서버장: {owner_name})\n"
        
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_entry)
    
    except Exception as e:
        print(f"❌ 로그 기록 오류: {e}")
