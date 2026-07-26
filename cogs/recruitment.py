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

# 현재 구인 메시지와 설정 메시지를 추적하는 딕셔너리
recruitment_messages = {}  # {message_id: {"recruitment": message_id, "settings": message_id, "list": message_id}}

# 초대 링크
INVITE_LINK = "https://discord.com/oauth2/authorize?client_id=1529528450157641779"

class BattleView(discord.ui.View):
    """참여 인원을 관리하는 뷰"""
    def __init__(self, message_id: int = None, game_time: str = "미정", game_type: str = "미정", max_players: int = 4):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.game_time = game_time
        self.game_type = game_type
        self.max_players = max_players
        self.players = [None] * max_players  # 설정된 최대 인원만큼 자리 생성
        
        # 저장된 데이터가 있으면 로드
        if message_id:
            battle_data = load_battle_data()
            if str(message_id) in battle_data:
                player_ids = battle_data[str(message_id)]["players"]
                self.players = player_ids

    def create_embed(self) -> discord.Embed:
        """구인 메시지 Embed 생성"""
        player_list_str = ""
        for i in range(self.max_players):
            if self.players[i]:
                if isinstance(self.players[i], int):
                    player_list_str += f"{i+1}. <@{self.players[i]}>\n"
                else:
                    player_list_str += f"{i+1}. {self.players[i].mention}\n"
            else:
                player_list_str += f"{i+1}. \n"

        description = (
            "🎮 BATTLEGROUND\n"
            f"게임 시간: {self.game_time}\n"
            f"게임종류: {self.game_type}\n"
            f"모집 인원: {self.max_players}명\n\n"
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
                "game_type": self.game_type,
                "max_players": self.max_players,
                "created_at": datetime.now(timezone.utc).isoformat()
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
                "이미 참여하셨습니다!", ephemeral=True, delete_after=5
            )
            return

        # 빈자리가 있는지 확인
        try:
            empty_index = self.players.index(None)
            self.players[empty_index] = user
            self.save_players()
            await interaction.message.edit(embed=self.create_embed())
            await interaction.response.send_message(
                f"참여가 완료되었습니다! ({empty_index + 1}번 슬롯)", ephemeral=True, delete_after=10
            )
        except ValueError:
            await interaction.response.send_message(
                "자리가 모두 찼습니다!", ephemeral=True, delete_after=10
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
                "참여가 취소되었습니다.", ephemeral=True, delete_after=3
            )
        else:
            await interaction.response.send_message(
                "참여 목록에 없습니다.", ephemeral=True, delete_after=5
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

def get_time_difference(created_at_str: str) -> str:
    """생성 시간으로부터 경과 시간 반환"""
    try:
        created_at = datetime.fromisoformat(created_at_str)
        now = datetime.now(timezone.utc)
        diff = now - created_at
        
        minutes = diff.total_seconds() // 60
        if minutes < 1:
            return "방금 전"
        elif minutes < 60:
            return f"{int(minutes)}분 전"
        else:
            hours = minutes // 60
            return f"{int(hours)}시간 전"
    except:
        return "알 수 없음"

class GameTimeModal(discord.ui.Modal, title="게임 시간 설정"):
    """게임 시간 입력 모달"""
    game_time = discord.ui.TextInput(
        label="게임 시간",
        placeholder="예: 오후 6시, 오후 1시, 밤 11시 등",
        required=True,
        max_length=50
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        self.cog.recruitment_settings["game_time"] = self.game_time.value
        await interaction.response.send_message(
            f"✅ 게임 시간이 '{self.game_time.value}'로 설정되었습니다!",
            ephemeral=True,
            delete_after=3
        )

class GameTypeModal(discord.ui.Modal, title="게임 종류 설정"):
    """게임 종류 입력 모달"""
    game_type = discord.ui.TextInput(
        label="게임 종류",
        placeholder="예: 일반, 경쟁, 미니게임, 커스텀 등",
        required=True,
        max_length=50
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        self.cog.recruitment_settings["game_type"] = self.game_type.value
        await interaction.response.send_message(
            f"✅ 게임 종류가 '{self.game_type.value}'로 설정되었습니다!",
            ephemeral=True,
            delete_after=3
        )

class PlayerCountModal(discord.ui.Modal, title="인원 설정"):
    """인원 수 입력 모달"""
    player_count = discord.ui.TextInput(
        label="모집 인원 (2~4명)",
        placeholder="예: 2 (듀오) 또는 4 (스쿼드)",
        required=True,
        max_length=1
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            count = int(self.player_count.value)
            
            # 유효성 검사 (2~4명)
            if count < 2 or count > 4:
                await interaction.response.send_message(
                    "❌ 인원은 2명(듀오) ~ 4명(스쿼드) 사이여야 합니다!",
                    ephemeral=True,
                    delete_after=3
                )
                return
            
            self.cog.recruitment_settings["player_count"] = count
            
            # 인원 타입 결정
            if count == 2:
                player_type = "듀오"
            elif count == 3:
                player_type = "트리오"
            else:
                player_type = "스쿼드"
            
            await interaction.response.send_message(
                f"✅ 모집 인원이 {count}명({player_type})으로 설정되었습니다!",
                ephemeral=True,
                delete_after=3
            )
            
            # 세 가지 설정이 모두 완료되었는지 확인
            if (self.cog.recruitment_settings["game_time"] != "미정" and
                self.cog.recruitment_settings["game_type"] != "미정" and
                self.cog.recruitment_settings["player_count"] > 0):
                await self.cog.start_recruitment(interaction)
        
        except ValueError:
            await interaction.response.send_message(
                "❌ 숫자를 입력해주세요! (2 또는 3 또는 4)",
                ephemeral=True,
                delete_after=3
            )

class SettingsView(discord.ui.View):
    """게임 설정 입력 버튼 뷰"""
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
    
    @discord.ui.button(label="시간 설정", style=discord.ButtonStyle.blurple, custom_id="time_input_btn")
    async def time_input_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GameTimeModal(self.cog))
    
    @discord.ui.button(label="종류 설정", style=discord.ButtonStyle.blurple, custom_id="type_input_btn")
    async def type_input_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GameTypeModal(self.cog))
    
    @discord.ui.button(label="인원 설정", style=discord.ButtonStyle.blurple, custom_id="player_input_btn")
    async def player_input_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PlayerCountModal(self.cog))

class DeleteRecruitmentSelect(discord.ui.Select):
    """삭제할 구인 선택 드롭다운"""
    def __init__(self, cog, recruitments: Dict, list_message_id: int):
        self.cog = cog
        self.recruitments = recruitments
        self.list_message_id = list_message_id
        
        options = []
        for message_id, data in recruitments.items():
            game_time = data.get("game_time", "미정")
            game_type = data.get("game_type", "미정")
            max_players = data.get("max_players", 4)
            created_at = data.get("created_at", "")
            time_diff = get_time_difference(created_at)
            
            label = f"{game_time} - {game_type} ({max_players}명) ({time_diff})"
            options.append(discord.SelectOption(label=label, value=message_id))
        
        super().__init__(
            placeholder="삭제할 구인을 선택하세요...",
            options=options,
            custom_id="delete_recruitment_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        message_id = self.values[0]
        await self.cog.delete_specific_recruitment(interaction, message_id, self.list_message_id)

class DeleteRecruitmentView(discord.ui.View):
    """삭제할 구인 선택 뷰"""
    def __init__(self, cog, recruitments: Dict, list_message_id: int):
        super().__init__(timeout=300)
        self.add_item(DeleteRecruitmentSelect(cog, recruitments, list_message_id))

class Recruitment(commands.Cog):
    """구인 관련 명령어 및 기능"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.recruitment_settings = {
            "game_time": "미정",
            "game_type": "미정",
            "player_count": 0
        }

    @discord.app_commands.command(name="양식", description="배틀그라운드 구인 설정")
    async def recruitment_settings_slash(self, interaction: discord.Interaction):
        """
        슬래시 명령어: /양식
        게임 시간, 종류, 인원을 설정하여 구인 시작
        """
        # 설정 초기화
        self.recruitment_settings = {
            "game_time": "미정",
            "game_type": "미정",
            "player_count": 0
        }
        
        embed = discord.Embed(
            title="⚙️ 배틀그라운드 구인 설정",
            description="아래 버튼을 눌러 게임 시간과 종류 및 인원을 선택 입력하세요!\n\n"
                       "1️⃣ 시간 설정 버튼 클릭\n"
                       "2️⃣ 종류 설정 버튼 클릭\n"
                       "3️⃣ 인원 설정 버튼 클릭\n\n"
                       "모든 설정을 완료하면 자동으로 구인이 시작됩니다! 🚀",
            color=discord.Color.blue(),
        )
        
        view = SettingsView(cog=self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def start_recruitment(self, interaction: discord.Interaction):
        """구인 메시지 자동 발송"""
        try:
            await interaction.response.defer()
        except:
            pass
        
        # 원래 명령어를 사용한 채널에 구인 메시지 발송
        channel = interaction.channel
        
        player_count = self.recruitment_settings.get("player_count", 4)
        
        view = BattleView(
            game_time=self.recruitment_settings.get("game_time", "미정"),
            game_type=self.recruitment_settings.get("game_type", "미정"),
            max_players=player_count
        )
        
        # @here 태그와 함께 메시지 발송
        message = await channel.send(
            "@here 🎮 배틀그라운드 스쿼드 구인이 시작되었습니다!",
            embed=view.create_embed(),
            view=view
        )
        
        # 메시지 ID 저장 (삭제용)
        view.message_id = message.id
        view.save_players()
        
        # 인원 타입 결정
        if player_count == 2:
            player_type = "듀오"
        elif player_count == 3:
            player_type = "트리오"
        else:
            player_type = "스쿼드"
        
        # 설정 완료 메시지 (본인만 봄)
        embed = discord.Embed(
            title="✅ 구인이 시작되었습니다!",
            description=f"**게임 시간**: {self.recruitment_settings.get('game_time', '미정')}\n"
                       f"**게임 종류**: {self.recruitment_settings.get('game_type', '미정')}\n"
                       f"**모집 인원**: {player_count}명({player_type})\n\n"
                       f"삭제하려면 `/삭제` 명령어를 사용하세요.",
            color=discord.Color.green(),
        )
        msg = await interaction.followup.send(embed=embed, ephemeral=True)
        await msg.delete(delay=10)
        
        # 구인 메시지와 설정 메시지 ID 매핑 저장
        recruitment_messages[message.id] = {
            "recruitment": message.id,
            "settings": message.id
        }

    @discord.app_commands.command(name="삭제", description="진행 중인 구인 메시지 삭제")
    async def delete_recruitment(self, interaction: discord.Interaction):
        """
        슬래시 명령어: /삭제
        진행 중인 구인 메시지를 선택하여 삭제합니다
        """
        # 저장된 배틀 데이터 로드
        battle_data = load_battle_data()
        
        if not battle_data:
            embed = discord.Embed(
                title="❌ 구인 메시지 없음",
                description="진행 중인 구인 메시지가 없습니다.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=3)
            return
        
        # 현재 서버의 구인만 필터링 (선택사항: 모든 구인 표시 가능)
        embed = discord.Embed(
            title="📋 진행 중인 구인 목록",
            description="삭제할 구인을 선택하세요:",
            color=discord.Color.blue(),
        )
        
        view = DeleteRecruitmentView(self, battle_data, 0)  # list_message_id는 나중에 업데이트됨
        message = await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        # 목록 메시지 ID를 view에 저장
        if isinstance(message, discord.Message):
            view.children[0].list_message_id = message.id
        else:
            # 비동기 처리로 메시지 ID 얻기
            fetched_message = await interaction.original_response()
            view.children[0].list_message_id = fetched_message.id

    async def delete_specific_recruitment(self, interaction: discord.Interaction, message_id: str, list_message_id: int):
        """특정 구인 메시지 삭제 (구인 메시지와 설정 메시지 모두 삭제)"""
        try:
            channel = interaction.channel
            
            # 메시지 삭제 시도
            try:
                # 구인 메시지 삭제
                recruitment_msg = await channel.fetch_message(int(message_id))
                await recruitment_msg.delete()
            except discord.NotFound:
                pass
            
            # 설정 메시지 삭제 (있다면)
            if int(message_id) in recruitment_messages:
                try:
                    settings_msg_id = recruitment_messages[int(message_id)]["settings"]
                    settings_msg = await channel.fetch_message(settings_msg_id)
                    await settings_msg.delete()
                except discord.NotFound:
                    pass
                
                # 매핑 정보 제거
                del recruitment_messages[int(message_id)]
            
            # 목록 메시지 삭제
            try:
                if list_message_id > 0:
                    list_msg = await channel.fetch_message(list_message_id)
                    await list_msg.delete()
            except discord.NotFound:
                pass
            
            # 데이터에서 제거
            battle_data = load_battle_data()
            if message_id in battle_data:
                del battle_data[message_id]
                save_battle_data(battle_data)
            
            embed = discord.Embed(
                title="✅ 구인이 삭제되었습니다!",
                description="선택한 구인 메시지와 설정이 모두 삭제되었습니다.",
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=5)
            
        except Exception as e:
            print(f"❌ 구인 삭제 중 오류: {e}")
            embed = discord.Embed(
                title="❌ 오류 발생",
                description=f"구인 삭제 중 오류가 발생했습니다: {e}",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=5)

    @discord.app_commands.command(name="초대링크", description="HRD Clan Bot 초대 링크 공유")
    async def invite_link(self, interaction: discord.Interaction):
        """
        슬래시 명령어: /초대링크
        HRD Clan Bot 초대 링크를 공유합니다
        """
        embed = discord.Embed(
            title="🔗 HRD Clan Bot 초대 링크",
            description="아래 링크를 클릭하여 봇을 서버에 초대하세요!\n\n"
                       "✅ 봇 권한: 메세지 보내기, 모두 멘션하기, 링크 임베드\n"
                       "✅ 메세지 보내기 및 멘션 기능정도만 작동합니다",
            color=discord.Color.blue(),
            url=INVITE_LINK
        )
        
        embed.add_field(
            name="🚀 빠른 시작",
            value="1. 위의 링크를 클릭하여 봇 초대\n"
                  "2. `/양식` 명령어로 구인 시작\n"
                  "3. `/삭제` 명령어로 구인 신청 삭제\n"
                  "4. 팀원들과 함께 플레이!",
            inline=False
        )
        
        # 클릭 가능한 버튼 추가
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="봇 초대하기", url=INVITE_LINK, style=discord.ButtonStyle.link))
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    """Cog 로드"""
    await bot.add_cog(Recruitment(bot))
