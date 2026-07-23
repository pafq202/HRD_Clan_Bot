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

class GameTimeSelect(discord.ui.Select):
    """게임 시간 선택 드롭다운"""
    def __init__(self, callback=None):
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
        self.user_callback = callback

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.user_callback:
            await self.user_callback("game_time", self.values[0])

class GameTypeSelect(discord.ui.Select):
    """게임 종류 선택 드롭다운"""
    def __init__(self, callback=None):
        options = [
            discord.SelectOption(label="미정", value="미정", emoji="❓"),
            discord.SelectOption(label="일반", value="일반", emoji="🎮"),
            discord.SelectOption(label="경쟁", value="경쟁", emoji="🏆"),
            discord.SelectOption(label="미니게임", value="미니게임", emoji="🎯"),
            discord.SelectOption(label="커스텀", value="커스텀", emoji="⚙️"),
        ]
        super().__init__(placeholder="게임 종류를 선택하세요", options=options, custom_id="game_type_select")
        self.user_callback = callback

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.user_callback:
            await self.user_callback("game_type", self.values[0])

class SettingsView(discord.ui.View):
    """게임 설정 선택 뷰"""
    def __init__(self, callback=None):
        super().__init__(timeout=300)
        self.add_item(GameTimeSelect(callback=callback))
        self.add_item(GameTypeSelect(callback=callback))

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
                "이미 참여하셨습니다!", ephemeral=True
            )
            return

        # 빈자리가 있는지 확인
        try:
            empty_index = self.players.index(None)
            self.players[empty_index] = user
            self.save_players()
            await interaction.message.edit(embed=self.create_embed())
            await interaction.response.send_message(
                f"참여가 완료되었습니다! ({empty_index + 1}번 슬롯)", ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "자리가 모두 찼습니다!", ephemeral=True
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
                "참여가 취소되었습니다.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "참여 목록에 없습니다.", ephemeral=True
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

    async def update_recruitment_settings(self, key: str, value: str):
        """구인 설정 업데이트"""
        self.recruitment_settings[key] = value

    @commands.command(name="구인")
    async def recruitment(self, ctx: commands.Context, action: str = None):
        """
        구인 관련 명령어
        .구인 양식 - 게임 설정 (시간, 종류)
        .구인 시작 - 구인 메시지 발송 및 @here 태그
        """
        
        if action is None or action == "양식":
            # 게임 설정 선택 창 표시
            embed = discord.Embed(
                title="⚙️ 배틀그라운드 구인 설정",
                description="아래에서 게임 시간과 종류를 선택하세요!",
                color=discord.Color.blue(),
            )
            
            view = SettingsView(callback=self.update_recruitment_settings)
            await ctx.send(embed=embed, view=view)
            
        elif action == "시작":
            # 구인 메시지 발송
            view = BattleView(
                game_time=self.recruitment_settings.get("game_time", "미정"),
                game_type=self.recruitment_settings.get("game_type", "미정")
            )
            
            # @here 태그와 함께 메시지 발송
            message = await ctx.send(
                "@here 🎮 배틀그라운드 스쿼드 구인이 시작되었습니다!",
                embed=view.create_embed(),
                view=view
            )
            
            # 메시지 ID 저장
            view.message_id = message.id
            view.save_players()
            
            await ctx.send("✅ 구인이 시작되었습니다!")
            
        else:
            await ctx.send("❌ 명령어 오류!\n사용법: `.구인 양식` 또는 `.구인 시작`")

async def setup(bot: commands.Bot):
    """Cog 로드"""
    await bot.add_cog(Recruitment(bot))
