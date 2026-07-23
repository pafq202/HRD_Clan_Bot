import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import json

# 환경변수 로드
load_dotenv()

# 봇 설정 (Intents 필요)
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=".", intents=intents)

# 참여 데이터를 저장할 JSON 파일
BATTLE_DATA_FILE = "battle_data.json"

# 구인 설정 임시 저장소
recruitment_settings = {
    "game_time": "미정",
    "game_type": "미정"
}

def load_battle_data():
    """저장된 배틀 데이터 로드"""
    if os.path.exists(BATTLE_DATA_FILE):
        with open(BATTLE_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_battle_data(data):
    """배틀 데이터 저장"""
    with open(BATTLE_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 게임 시간 선택 드롭다운
class GameTimeSelect(discord.ui.Select):
    def __init__(self):
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

    async def callback(self, interaction: discord.Interaction):
        recruitment_settings["game_time"] = self.values[0]
        await interaction.response.defer()

# 게임 종류 선택 드롭다운
class GameTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="미정", value="미정", emoji="❓"),
            discord.SelectOption(label="일반", value="일반", emoji="🎮"),
            discord.SelectOption(label="경쟁", value="경쟁", emoji="🏆"),
            discord.SelectOption(label="미니게임", value="미니게임", emoji="🎯"),
            discord.SelectOption(label="커스텀", value="커스텀", emoji="⚙️"),
        ]
        super().__init__(placeholder="게임 종류를 선택하세요", options=options, custom_id="game_type_select")

    async def callback(self, interaction: discord.Interaction):
        recruitment_settings["game_type"] = self.values[0]
        await interaction.response.defer()

# 설정 선택 View
class SettingsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(GameTimeSelect())
        self.add_item(GameTypeSelect())

# 참여 인원을 관리하는 View 클래스
class BattleView(discord.ui.View):
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

    def create_embed(self):
        # 참여인원 텍스트 생성
        player_list_str = ""
        for i in range(4):
            if self.players[i]:
                # player_id가 저장된 경우 처리
                if isinstance(self.players[i], int):
                    player_list_str += f"{i+1}. <@{self.players[i]}>\n"
                else:
                    player_list_str += f"{i+1}. {self.players[i].mention}\n"
            else:
                player_list_str += f"{i+1}. \n"

        # 출력할 양식 텍스트
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
            # 유저 객체를 ID로 변환하여 저장
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
            self.save_players()  # 데이터 저장
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
            self.save_players()  # 데이터 저장
            await interaction.message.edit(embed=self.create_embed())
            await interaction.response.send_message(
                "참여가 취소되었습니다.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "참여 목록에 없습니다.", ephemeral=True
            )


@bot.event
async def on_ready():
    print(f"로그인 완료: {bot.user}")
    # Persistent views 복원
    try:
        bot.add_view(BattleView())
        print("Persistent views 등록 완료")
    except Exception as e:
        print(f"Persistent views 등록 중 오류: {e}")


@bot.command(name="구인")
async def recruitment(ctx, action: str = None):
    """
    구인 관련 명령어
    /구인 양식 - 게임 설정 (시간, 종류)
    /구인 시작 - 구인 메시지 발송 및 @here 태그
    """
    
    if action is None or action == "양식":
        # 게임 설정 선택 창 표시
        embed = discord.Embed(
            title="⚙️ 배틀그라운드 구인 설정",
            description="아래에서 게임 시간과 종류를 선택하세요!",
            color=discord.Color.blue(),
        )
        
        view = SettingsView()
        await ctx.send(embed=embed, view=view)
        
    elif action == "시작":
        # 구인 메시지 발송
        view = BattleView(
            game_time=recruitment_settings.get("game_time", "미정"),
            game_type=recruitment_settings.get("game_type", "미정")
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


# 봇 토큰 입력 (환경변수에서 로드)
TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN_HERE")
if TOKEN == "YOUR_BOT_TOKEN_HERE":
    print("⚠️ 경고: DISCORD_TOKEN 환경변수가 설정되지 않았습니다!")
    print("📝 .env 파일을 생성하고 'DISCORD_TOKEN=your_token_here'를 추가하세요.")

bot.run(TOKEN)
