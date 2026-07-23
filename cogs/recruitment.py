import discord
from discord.ext import commands
import os
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict
from config.config import get_config
from utils.directory import directory

# 설정 파일 로드
parser = get_config("config")
comment_parser = get_config("comment")

# 현재 구인 메시지 ID를 저장하는 딕셔너리
current_recruitment_messages = {}

class GameTimeSelect(discord.ui.Select):
    """게임 시간 선택 드롭다운"""
    def __init__(self, cog):
        options = [
            discord.SelectOption(label="미정", value="미정", emoji="❓"),
            discord.SelectOption(label="모일시 바로 시작", value="모일시 바로 시작", emoji="⚡"),
            discord.SelectOption(label="오후 1시", value="오후 1시", emoji="🕐"),
            discord.SelectOption(label="오후 3시", value="오후 3시", emoji="🕒"),
            discord.SelectOption(label="오후 6시", value="오후 6시", emoji="🕕"),
            discord.SelectOption(label="오후 9시", value="오후 9시", emoji="🕘"),
            discord.SelectOption(label="밤 11시", value="밤 11시", emoji="🕛"),
        ]
        super().__init__(placeholder="게임 시간을 선택하세요", options=options, custom_id="game_time_select")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.cog.recruitment_settings["game_time"] = self.values[0]
        
        # 두 설정이 모두 선택되었는지 확인 (미정이 아닌 경우)
        if (self.cog.recruitment_settings["game_time"] != "미정" and 
            self.cog.recruitment_settings["game_type"] != "미정"):
            await self.cog.start_recruitment(interaction)

class GameTypeSelect(discord.ui.Select):
    """게임 종류 선택 드롭다운"""
    def __init__(self, cog):
        options = [
            discord.SelectOption(label="미정", value="미정", emoji="❓"),
            discord.SelectOption(label="일반", value="일반", emoji="🎮"),
            discord.SelectOption(label="경쟁", value="경쟁", emoji="🏆"),
            discord.SelectOption(label="미니게임", value="미니게임", emoji="🎯"),
            discord.SelectOption(label="커스텀", value="커스텀", emoji="⚙️"),
        ]
        super().__init__(placeholder="게임 종류를 선택하세요", options=options, custom_id="game_type_select")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.cog.recruitment_settings["game_type"] = self.values[0]
        
        # 두 설정이 모두 선택되었는지 확인 (미정이 아닌 경우)
        if (self.cog.recruitment_settings["game_time"] != "미정" and 
            self.cog.recruitment_settings["game_type"] != "미정"):
            await self.cog.start_recruitment(interaction)

class SettingsView(discord.ui.View):
    """게임 설정 선택 뷰"""
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.add_item(GameTimeSelect(cog=cog))
        self.add_item(GameTypeSelect(cog=cog))

class BattleView(discord.ui.View):
    """참여 인원을 관리하는 뷰"""
    def __init__(self, message_id: int = None, game_time: str = "미정", game_type: str = "미정"):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.game_time = game_time
        self.game_type = game_type
        self.players = [None, None, None, None]  # 4명의 자리
        
        # 저장된 데이터가 있으면 로드
        if message_id:
            battle_data = load_battle_data()
            if str(message_id) in battle_data:
                player_ids = battle_data[str(message_id)]["players"]
                self.players = player_ids

    def create_embed(self) -> discord.Embed:
        """구인 메시지 Embed 생성"""
        player_list_str = ""
        for i in range(4):
            if self.players[i]:
                if isinstance(self.players[i], int):
                    player_list_str += f"{i+1}. <@{self.players[i]}>\n"
                else:
                    player_list_str += f"{i+1}. {self.players[i].mention}\n"
            else:
                player_list_str += f"{i+1}. \n"

        description = (
            "🎮 BATTLEGROUND @here\n"
            f"게임 시간: {self.game_time}\n"
            f"게임종류: {self.game_type}\n\n"
            "참여인원\n"
            f"{player_list_str}"
        )

        embed = discord.Embed(
            title="배틀그라운드 스쿼드 모집",
            description=description,
            color=discord.Color.blue(),
        )
        return embed

    def save_players(self):
        """현재 참여 인원을 데이터베이스에 저장"""
        if self.message_id:
            battle_data = load_battle_data()
            player_ids = []
            for player in self.players:
                if player is None:
                    player_ids.append(None)
                elif isinstance(player, int):
                    player_ids.append(player)
                else:
                    player_ids.append(player.id)
            battle_data[str(self.message_id)] = {
                "players": player_ids,
                "game_time": self.game_time,
                "game_type": self.game_type
            }
            save_battle_data(battle_data)

    @discord.ui.button(
        label="참여", style=discord.ButtonStyle.green, custom_id="join_btn"
    )
    async def join_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        user = interaction.user

        # 이미 참여했는지 확인
        if user in self.players or user.id in self.players:
            await interaction.response.send_message(
                "이미 참여하셨습니다!", ephemeral=False, delete_after=5
            )
            return

        # 빈자리가 있는지 확인
        try:
            empty_index = self.players.index(None)
            self.players[empty_index] = user
            self.save_players()
            await interaction.message.edit(embed=self.create_embed())
            await interaction.response.send_message(
                f"참여가 완료되었습니다! ({empty_index + 1}번 슬롯)", ephemeral=False, delete_after=5
            )
        except ValueError:
            await interaction.response.send_message(
                "자리가 모두 찼습니다!", ephemeral=False, delete_after=5
            )

    @discord.ui.button(
        label="참여취소", style=discord.ButtonStyle.red, custom_id="leave_btn"
    )
    async def leave_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        user = interaction.user

        # 참여 목록에 있는지 확인 (ID로도 비교)
        user_in_list = False
        user_index = -1
        
        for i, player in enumerate(self.players):
            if player == user or (player and player.id == user.id):
                user_in_list = True
                user_index = i
                break

        if user_in_list:
            self.players[user_index] = None
            self.save_players()
            await interaction.message.edit(embed=self.create_embed())
            await interaction.response.send_message(
                "참여가 취소되었습니다.", ephemeral=False, delete_after=5
            )
        else:
            await interaction.response.send_message(
                "참여 목록에 없습니다.", ephemeral=False, delete_after=5
            )

def load_battle_data() -> dict:
    """저장된 배틀 데이터 로드"""
    data_dir = os.path.join(directory, "data")
    data_file = os.path.join(data_dir, "pending_recruitment.json")
    
    # data 디렉토리가 없으면 생성
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    # 파일이 없으면 빈 딕셔너리 반환
    if not os.path.exists(data_file):
        return {}
    
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 데이터 로드 오류: {e}")
        return {}

def save_battle_data(data: dict):
    """배틀 데이터 저장"""
    data_dir = os.path.join(directory, "data")
    data_file = os.path.join(data_dir, "pending_recruitment.json")
    
    # data 디렉토리가 없으면 생성
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    try:
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"❌ 데이터 저장 오류: {e}")

class Recruitment(commands.Cog):
    """구인 관련 명령어 및 기능"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.recruitment_settings = {
            "game_time": "미정",
            "game_type": "미정"
        }

    @discord.app_commands.command(name="양식", description="배틀그라운드 구인 설정 및 시작")
    async def recruitment_settings_slash(self, interaction: discord.Interaction):
        """
        슬래시 명령어: /양식
        게임 시간과 게임 종류를 선택하면 자동으로 구인 메시지 발송
        """
        # 설정 초기화
        self.recruitment_settings = {
            "game_time": "미정",
            "game_type": "미정"
        }
        
        embed = discord.Embed(
            title="⚙️ 배틀그라운드 구인 설정",
            description="게임 시간과 종류를 **모두** 선택하면 자동으로 구인이 시작됩니다!\n\n(미정이 아닌 값을 선택해주세요)",
            color=discord.Color.blue(),
        )
        
        view = SettingsView(cog=self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    async def start_recruitment(self, interaction: discord.Interaction):
        """구인 메시지 자동 발송"""
        try:
            await interaction.response.defer()
        except:
            pass
        
        # 원래 명령어를 사용한 채널에 구인 메시지 발송
        channel = interaction.channel
        
        view = BattleView(
            game_time=self.recruitment_settings.get("game_time", "미정"),
            game_type=self.recruitment_settings.get("game_type", "미정")
        )
        
        # @here 태그와 함께 메시지 발송
        message = await channel.send(
            "@here 🎮 배틀그라��드 스쿼드 구인이 시작되었습니다!",
            embed=view.create_embed(),
            view=view
        )
        
        # 메시지 ID 저장 (삭제용)
        view.message_id = message.id
        view.save_players()
        
        # 현재 서버의 구인 메시지 ID 저장
        current_recruitment_messages[interaction.guild_id] = message.id
        
        # 설정 완료 메시지
        embed = discord.Embed(
            title="✅ 구인이 시작되었습니다!",
            description=f"**게임 시간**: {self.recruitment_settings.get('game_time', '미정')}\n**게임 종류**: {self.recruitment_settings.get('game_type', '미정')}\n\n삭제하려면 `/삭제` 명령어를 사용하세요.",
            color=discord.Color.green(),
        )
        await channel.send(embed=embed, delete_after=10)

    @discord.app_commands.command(name="삭제", description="진행 중인 구인 메시지 삭제")
    async def delete_recruitment(self, interaction: discord.Interaction):
        """
        슬래시 명령어: /삭제
        진행 중인 구인 메시지를 삭제합니다
        """
        guild_id = interaction.guild_id
        
        # 현재 서버에 구인 메시지가 있는지 확인
        if guild_id not in current_recruitment_messages:
            embed = discord.Embed(
                title="❌ 구인 메시지 없음",
                description="진행 중인 구인 메시지가 없습니다.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=5)
            return
        
        try:
            message_id = current_recruitment_messages[guild_id]
            channel = interaction.channel
            
            # 메시지 삭제 시도
            try:
                message = await channel.fetch_message(message_id)
                await message.delete()
            except discord.NotFound:
                # 메시지가 이미 삭제되었거나 찾을 수 없는 경우
                pass
            
            # 저장된 메시지 ID 제거
            del current_recruitment_messages[guild_id]
            
            # 데이터도 제거
            battle_data = load_battle_data()
            if str(message_id) in battle_data:
                del battle_data[str(message_id)]
                save_battle_data(battle_data)
            
            embed = discord.Embed(
                title="✅ 구인이 삭제되었습니다!",
                description="진행 중인 구인 메시지가 삭제되었습니다.",
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=False, delete_after=5)
            
        except Exception as e:
            print(f"❌ 구인 삭제 중 오류: {e}")
            embed = discord.Embed(
                title="❌ 오류 발생",
                description=f"구인 삭제 중 오류가 발생했습니다: {e}",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=5)

async def setup(bot: commands.Bot):
    """Cog 로드"""
    await bot.add_cog(Recruitment(bot))
