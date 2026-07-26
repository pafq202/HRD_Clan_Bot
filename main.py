import discord
import os
from discord.ext import commands
from dotenv import load_dotenv
import logging
from utils import server_logger

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# 봇 설정 (Intents 필요)
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix=".", intents=intents)

# 현재 디렉토리
directory = os.path.dirname(os.path.abspath(__file__))

@bot.event
async def on_ready():
    log.info(f"✅ 봇 로그인 완료: {bot.user}")
    log.info(f"📋 서버 수: {len(bot.guilds)}")
    log.info(f"✅ 로드된 Cog 수: {len(bot.cogs)}")
    log.info(f"⚡ 슬래시 명령어: {len(bot.tree.get_commands())} 개")
    
    try:
        synced = await bot.tree.sync()
        log.info(f"✅ 슬래시 명령어 동기화 완료: {len(synced)} 개")
    except Exception as e:
        log.error(f"❌ 슬래시 명령어 동기화 실패: {e}")
    
    # 서버 정보 저장 (터미널 출력 없음)
    await server_logger.save_server_info(bot)

@bot.event
async def on_guild_join(guild: discord.Guild):
    """봇이 새 서버에 추가될 때"""
    # 파일만 업데이트 (터미널 출력 없음)
    await server_logger.save_server_info(bot)

@bot.event
async def on_guild_remove(guild: discord.Guild):
    """봇이 서버에서 제거될 때"""
    # 파일만 업데이트 (터미널 출력 없음)
    await server_logger.save_server_info(bot)

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
    """봇 초기화 및 실행"""
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

# 봇 토큰 입력 (환경변수에서 로드)
TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN_HERE")
if TOKEN == "YOUR_BOT_TOKEN_HERE":
    log.error("⚠️ 경고: DISCORD_TOKEN 환경변수가 설정되지 않았습니다!")
    log.error("📝 .env 파일을 생성하고 'DISCORD_TOKEN=your_token_here'를 추가하세요.")
    exit(1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
