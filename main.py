import discord
import os
from discord.ext import commands
from dotenv import load_dotenv
import logging
import asyncio
from utils import server_logger

# 환경변수 로드
load_dotenv()

# 로깅 설정 (Discord.py 로깅 오류 완벽 해결)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# Discord.py 로거 레벨 조정 (로깅 오류 방지)
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.http').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.WARNING)

# 봇 설정 (Intents 필요)
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix=".", intents=intents)

# 현재 디렉토리
directory = os.path.dirname(os.path.abspath(__file__))

# 재연결 시도 횟수 추적
reconnect_attempts = 0
MAX_RECONNECT_ATTEMPTS = 5

@bot.event
async def on_ready():
    global reconnect_attempts
    # 연결 성공 시 재연결 시도 횟수 초기화
    reconnect_attempts = 0
    
    log.info(f"✅ 봇 로그인 완료: {bot.user}")
    log.info(f"📋 서버 수: {len(bot.guilds)}")
    log.info(f"✅ 로드된 Cog 수: {len(bot.cogs)}")
    log.info(f"⚡ 슬래시 명령어: {len(bot.tree.get_commands())} 개")
    
    try:
        synced = await bot.tree.sync()
        log.info(f"✅ 슬래시 명령어 동기화 완료: {len(synced)} 개")
    except Exception as e:
        log.error(f"❌ 슬래시 명령어 동기화 실패: {e}")
    
    # 서버 정보 저장
    await server_logger.save_server_info(bot)
    # 터미널에 서버 정보 출력
    server_logger.print_server_info(bot)

@bot.event
async def on_guild_join(guild: discord.Guild):
    """봇이 새 서버에 추가될 때"""
    # 파일 업데이트
    await server_logger.save_server_info(bot)
    # 터미널에 전체 서버 목록 출력
    server_logger.print_guild_list(bot)
    # 추가 정보 출력
    server_logger.print_guild_join(guild)
    # 로그 기록
    server_logger.log_server_action("추가", guild)

@bot.event
async def on_guild_remove(guild: discord.Guild):
    """봇이 서버에서 제거될 때"""
    # 파일 업데이트
    await server_logger.save_server_info(bot)
    # 제거 정보 출력
    server_logger.print_guild_remove(guild)
    # 업데이트된 서버 목록 출력
    server_logger.print_guild_list(bot)
    # 로그 기록
    server_logger.log_server_action("제거", guild)

@bot.event
async def on_command_error(ctx, error):
    log.error(f"❌ 명령어 오류: {error}")
    await ctx.send(f"오류가 발생했습니다: {error}", delete_after=5)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """슬래시 명령어 에러 핸들러"""
    if isinstance(error, discord.app_commands.CheckFailure):
        embed = discord.Embed(
            title="❌ 권한이 없습니다",
            description="이 명령어를 사용할 권한이 없습니다.\n\n"
                       "필요 권한:\n"
                       "• 서버 주인 또는\n"
                       "• 관리자 권한",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)
    else:
        log.error(f"❌ 슬래시 명령어 오류: {error}")
        embed = discord.Embed(
            title="❌ 오류 발생",
            description=f"명령어 실행 중 오류가 발생했습니다.",
            color=discord.Color.red(),
        )
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)
        except:
            pass

@bot.event
async def on_error(event, *args, **kwargs):
    """모든 이벤트 에러 자동 처리"""
    global reconnect_attempts
    
    log.error(f"❌ 이벤트 '{event}'에서 오류 발생")
    
    # 에러가 발생했으므로 재연결 시도
    if reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
        reconnect_attempts += 1
        log.warning(f"⏳ 자동 재연결 시도 ({reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})")
        await asyncio.sleep(2 ** reconnect_attempts)  # 지수 백오프 (2초, 4초, 8초, 16초, 32초)
    else:
        log.error(f"❌ 최대 재연결 횟수 ({MAX_RECONNECT_ATTEMPTS}회) 초과! 봇을 재시작하세요.")

async def load_cogs():
    """Cog 비동기 로드"""
    cogs_dir = os.path.join(directory, 'cogs')
    for filename in os.listdir(cogs_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            cog_name = f'cogs.{filename[:-3]}'
            try:
                await bot.load_extension(cog_name)
                log.info(f"✅ Cog 로드: {filename}")
            except Exception as e:
                log.error(f"❌ Cog 로드 실패 ({filename}): {e}")

async def main():
    """봇 초기화 및 실행 (자동 재연결 활성화)"""
    global reconnect_attempts
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            async with bot:
                await load_cogs()
                log.info("🚀 봇 시작...")
                await bot.start(TOKEN)
        except Exception as e:
            retry_count += 1
            log.error(f"❌ 봇 실행 오류: {e}")
            
            if retry_count < max_retries:
                wait_time = 5 * retry_count
                log.warning(f"⏳ {wait_time}초 후 재시작 시도... ({retry_count}/{max_retries})")
                await asyncio.sleep(wait_time)
            else:
                log.error(f"❌ {max_retries}회 재시도 후 실패! 봇을 수동으로 재시작하세요.")
                break
        
        # 정상 종료 후 재연결 시도
        reconnect_attempts = 0
        await asyncio.sleep(1)

# 봇 토큰 입력 (환경변수에서 로드)
TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN_HERE")
if TOKEN == "YOUR_BOT_TOKEN_HERE":
    log.error("⚠️ 경고: DISCORD_TOKEN 환경변수가 설정되지 않았습니다!")
    log.error("📝 .env 파일을 생성하고 'DISCORD_TOKEN=your_token_here'를 추가하세요.")
    exit(1)

if __name__ == "__main__":
    asyncio.run(main())
