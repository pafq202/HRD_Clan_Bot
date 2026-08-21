import discord
from discord.ext import commands
import os
import json
import asyncio
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


def _serialize_player_id(player) -> Optional[int]:
    """Discord 사용자 객체 또는 ID를 안전하게 정수 ID로 변환"""
    if player is None:
        return None
    if isinstance(player, int):
        return player
    return getattr(player, "id", None)


def _is_same_player(player, user: discord.User) -> bool:
    """플레이어가 특정 사용자와 동일한지 확인"""
    if player is None:
        return False
    if isinstance(player, int):
        return player == user.id
    return getattr(player, "id", None) == user.id


def _normalize_players(players: List[Optional[object]], max_players: int) -> List[Optional[object]]:
    """players 길이를 최대 인원에 맞게 정규화"""
    normalized = list(players or [])[:max_players]
    normalized.extend([None] * (max_players - len(normalized)))
    return normalized


# 관리자 또는 서버 주인 권한 체크
async def is_admin_or_owner(interaction: discord.Interaction) -> bool:
    """사용자가 관리자 또는 서버 주인인지 확인"""
    if not interaction.guild:
        return False
    return interaction.user.id == interaction.guild.owner_id or interaction.user.guild_permissions.administrator


class BattleView(discord.ui.View):
    """참여 인원을 관리하는 뷰"""
    def __init__(self, message_id: int = None, game_time: str = "미정", game_type: str = "미정", max_players: int = 4, voice_channel: str = "미정"):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.game_time = game_time
        self.game_type = game_type
        self.max_players = max_players
        self.voice_channel = voice_channel
        self.players = [None] * max_players  # 설정된 최대 인원만큼 자리 생성

        # 저장된 데이터가 있으면 로드
        if message_id:
            battle_data = load_battle_data()
            if str(message_id) in battle_data:
                player_ids = battle_data[str(message_id)].get("players", [])
                self.players = _normalize_players(player_ids, max_players)

    def create_embed(self) -> discord.Embed:
        """구인 메시지 Embed 생성"""
        player_lines = []
        for index, player in enumerate(self.players, start=1):
            if player is None:
                player_lines.append(f"{index}. ")
            elif isinstance(player, int):
                player_lines.append(f"{index}. <@{player}>")
            else:
                player_lines.append(f"{index}. {player.mention}")

        description = (
            "🎮 BATTLEGROUND\n"
            f"게임 시간: {self.game_time}\n"
            f"게임종류: {self.game_type}\n"
            f"📍 음성채널: {self.voice_channel}\n"
            f"모집 인원: {self.max_players}명\n\n"
            "참여인원\n"
            + "\n".join(player_lines)
        )

        embed = discord.Embed(
            title="배틀그라운드 스쿼드 모집",
            description=description,
            color=discord.Color.blue(),
        )
        return embed

    def save_players(self):
        """현재 참여 인원을 데이터베이스에 저장"""
        if not self.message_id:
            return

        battle_data = load_battle_data()
        battle_data[str(self.message_id)] = {
            "players": [_serialize_player_id(player) for player in self.players],
            "game_time": self.game_time,
            "game_type": self.game_type,
            "max_players": self.max_players,
            "voice_channel": self.voice_channel,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        save_battle_data(battle_data)

    @discord.ui.button(
        label="참여", style=discord.ButtonStyle.green, custom_id="join_btn"
    )
    async def join_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        user = interaction.user

        if any(_is_same_player(player, user) for player in self.players):
            await interaction.response.send_message(
                "이미 참여하셨습니다!", ephemeral=True, delete_after=5
            )
            return

        empty_index = next((index for index, player in enumerate(self.players) if player is None), None)
        if empty_index is None:
            await interaction.response.send_message(
                "자리가 모두 찼습니다!", ephemeral=True, delete_after=10
            )
            return

        self.players[empty_index] = user
        self.save_players()
        await interaction.message.edit(embed=self.create_embed())
        await interaction.response.send_message(
            f"참여가 완료되었습니다! ({empty_index + 1}번 슬롯)", ephemeral=True
        )

    @discord.ui.button(
        label="참여취소", style=discord.ButtonStyle.red, custom_id="leave_btn"
    )
    async def leave_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        user = interaction.user

        for index, player in enumerate(self.players):
            if _is_same_player(player, user):
                self.players[index] = None
                self.save_players()
                await interaction.message.edit(embed=self.create_embed())
                await interaction.response.send_message(
                    "참여가 취소되었습니다.", ephemeral=True, delete_after=3
                )
                return

        await interaction.response.send_message(
            "참여 목록에 없습니다.", ephemeral=True, delete_after=5
        )


def load_battle_data() -> dict:
    """저장된 배틀 데이터 로드"""
    data_dir = os.path.join(directory, "data")
    data_file = os.path.join(data_dir, "pending_recruitment.json")

    os.makedirs(data_dir, exist_ok=True)

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

    os.makedirs(data_dir, exist_ok=True)

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
        if minutes < 60:
            return f"{int(minutes)}분 전"
        hours = minutes // 60
        return f"{int(hours)}시간 전"
    except Exception:
        return "알 수 없음"


class GameTimeModal(discord.ui.Modal, title="게임 시간 설정"):
    """게임 시간 입력 모달"""
    game_time = discord.ui.TextInput(
        label="게임 시간",
        placeholder="예: 오후 6시, 오후 1시, 밤 11시 등",
        required=True,
        max_length=50,
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        self.cog.recruitment_settings["game_time"] = self.game_time.value
        await interaction.response.send_message(
            f"✅ 게임 시간이 '{self.game_time.value}'로 설정되었습니다!",
            ephemeral=True,
            delete_after=3,
        )

        await self.cog.check_and_start_recruitment(interaction)


class GameTypeModal(discord.ui.Modal, title="게임 종류 설정"):
    """게임 종류 입력 모달"""
    game_type = discord.ui.TextInput(
        label="게임 종류",
        placeholder="예: 일반, 경쟁, 미니게임, 커스텀 등",
        required=True,
        max_length=50,
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        self.cog.recruitment_settings["game_type"] = self.game_type.value
        await interaction.response.send_message(
            f"✅ 게임 종류가 '{self.game_type.value}'로 설정되었습니다!",
            ephemeral=True,
            delete_after=3,
        )

        await self.cog.check_and_start_recruitment(interaction)


class PlayerCountModal(discord.ui.Modal, title="인원 설정"):
    """인원 수 입력 모달"""
    player_count = discord.ui.TextInput(
        label="모집 인원 (2~4명)",
        placeholder="예: 2 (듀오) 또는 4 (스쿼드)",
        required=True,
        max_length=1,
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            count = int(self.player_count.value)

            if count < 2 or count > 4:
                await interaction.response.send_message(
                    "❌ 인원은 2명(듀오) ~ 4명(스쿼드) 사이여야 합니다!",
                    ephemeral=True,
                    delete_after=3,
                )
                return

            self.cog.recruitment_settings["player_count"] = count

            if count == 2:
                player_type = "듀오"
            elif count == 3:
                player_type = "트리오"
            else:
                player_type = "스쿼드"

            await interaction.response.send_message(
                f"✅ 모집 인원이 {count}명({player_type})으로 설정되었습니다!",
                ephemeral=True,
                delete_after=3,
            )

            await self.cog.check_and_start_recruitment(interaction)

        except ValueError:
            await interaction.response.send_message(
                "❌ 숫자를 입력해주세요! (2 또는 3 또는 4)",
                ephemeral=True,
                delete_after=3,
            )


class VoiceChannelSelect(discord.ui.Select):
    """음성 채널 선택 드롭다운"""
    def __init__(self, cog, guild: discord.Guild, voice_channel_interaction: discord.Interaction = None):
        self.cog = cog
        self.guild = guild
        self.voice_channel_interaction = voice_channel_interaction

        voice_channels = [channel for channel in guild.channels if isinstance(channel, discord.VoiceChannel)]

        options = [
            discord.SelectOption(label=f"🎮 {channel.name}", value=str(channel.id))
            for channel in voice_channels
        ]

        super().__init__(
            placeholder="음성 채널을 선택하세요...",
            options=options if options else [discord.SelectOption(label="음성 채널 없음", value="none")],
            custom_id="voice_channel_select",
            disabled=len(options) == 0,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "❌ 사용 가능한 음성 채널이 없습니다!",
                ephemeral=True,
                delete_after=3,
            )
            return

        channel_id = int(self.values[0])
        channel = self.guild.get_channel(channel_id)

        if channel:
            self.cog.recruitment_settings["voice_channel"] = f"#{channel.name}"

            if self.voice_channel_interaction:
                try:
                    await self.voice_channel_interaction.delete_original_response()
                except Exception:
                    pass

            await self.cog.check_and_start_recruitment(interaction)


class VoiceChannelView(discord.ui.View):
    """음성 채널 선택 뷰"""
    def __init__(self, cog, guild: discord.Guild, voice_channel_interaction: discord.Interaction = None):
        super().__init__(timeout=300)
        self.add_item(VoiceChannelSelect(cog, guild, voice_channel_interaction))


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

    @discord.ui.button(label="채널 선택", style=discord.ButtonStyle.blurple, custom_id="channel_select_btn")
    async def channel_select_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = VoiceChannelView(self.cog, interaction.guild, interaction)
        embed = discord.Embed(
            title="🎧 음성 채널 선택",
            description="아래 드롭다운에서 게임할 음성 채널을 선택하세요!",
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


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
            custom_id="delete_recruitment_select",
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
            "player_count": 0,
            "voice_channel": "미정",
        }
        self.settings_interaction = None
        self.recruiter = None
        self.interaction_channel = None

    def is_recruitment_complete(self) -> bool:
        """모든 설정이 완료되었는지 확인"""
        return (
            self.recruitment_settings["game_time"] != "미정"
            and self.recruitment_settings["game_type"] != "미정"
            and self.recruitment_settings["player_count"] > 0
            and self.recruitment_settings["voice_channel"] != "미정"
        )

    async def check_and_start_recruitment(self, interaction: discord.Interaction):
        """설정 완료 여부 확인 후 구인 시작"""
        if self.is_recruitment_complete():
            await self.start_recruitment(interaction)

    @discord.app_commands.command(name="양식", description="배틀그라운드 구인 설정")
    async def recruitment_settings_slash(self, interaction: discord.Interaction):
        """
        슬래시 명령어: /양식
        게임 시간, 종류, 인원, 음성 채널을 설정하여 구인 시작
        누구나 사용 가능
        """
        self.recruitment_settings = {
            "game_time": "미정",
            "game_type": "미정",
            "player_count": 0,
            "voice_channel": "미정",
        }
        self.settings_interaction = interaction
        self.interaction_channel = interaction.channel
        self.recruiter = interaction.user

        embed = discord.Embed(
            title="⚙️ 배틀그라운드 구인 설정",
            description="아래 버튼을 눌러 게임 시간과 종류 및 인원, 음성 채널을 선택 입력하세요!\n\n"
            "1️⃣ 시간 설정 버튼 클릭\n"
            "2️⃣ 종류 설정 버튼 클릭\n"
            "3️⃣ 인원 설정 버튼 클릭\n"
            "4️⃣ 채널 선택 버튼 클릭\n\n"
            "모든 설정을 완료하면 자동으로 구인이 시작됩니다! 🚀",
            color=discord.Color.blue(),
        )

        view = SettingsView(cog=self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def start_recruitment(self, interaction: discord.Interaction):
        """구인 메시지 자동 발송"""
        try:
            await interaction.response.defer()
        except Exception:
            pass

        channel = self.interaction_channel or interaction.channel
        player_count = self.recruitment_settings.get("player_count", 4)

        view = BattleView(
            game_time=self.recruitment_settings.get("game_time", "미정"),
            game_type=self.recruitment_settings.get("game_type", "미정"),
            max_players=player_count,
            voice_channel=self.recruitment_settings.get("voice_channel", "미정"),
        )

        try:
            if player_count == 2:
                player_type = "듀오"
            elif player_count == 3:
                player_type = "트리오"
            else:
                player_type = "스쿼드"

            if self.recruiter:
                view.players[0] = self.recruiter

            message = await channel.send(
                "@here 🎮 배틀그라운드 스쿼드 구인이 시작되었습니다! "
                f"({player_type} - {self.recruitment_settings.get('game_time')} - {self.recruitment_settings.get('game_type')})",
                embed=view.create_embed(),
                view=view,
            )

            view.message_id = message.id
            view.save_players()

            recruitment_messages[message.id] = {
                "recruitment": message.id,
                "settings": self.settings_interaction.id if self.settings_interaction else None,
            }

            if self.settings_interaction:
                try:
                    await self.settings_interaction.edit_original_response(
                        embed=discord.Embed(
                            title="✅ 구인이 생성되었습니다!",
                            description="설정이 완료되어 구인 메시지가 채널에 발송되었습니다.",
                            color=discord.Color.green(),
                        ),
                        view=None,
                    )
                except Exception:
                    pass

        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ 권한 오류",
                description="봇이 이 채널에 메시지를 보낼 권한이 없습니다!\n\n"
                "**해결 방법:**\n"
                "1. 서버 설정 → 역할 → HRD_Clan_Bot\n"
                "2. 다음 권한 확인:\n"
                "   • 메시지 보내기 ✅\n"
                "   • 메시지 관리 ✅\n"
                "   • 멘션 보내기 ✅",
                color=discord.Color.red(),
            )
            msg = await interaction.followup.send(embed=embed, ephemeral=True)
            await asyncio.sleep(10)
            await msg.delete()

        except discord.NotFound:
            embed = discord.Embed(
                title="❌ 채널 오류",
                description="채널을 찾을 수 없습니다!\n\n"
                "채널이 삭제되었거나 접근할 수 없을 수 있습니다.",
                color=discord.Color.red(),
            )
            msg = await interaction.followup.send(embed=embed, ephemeral=True)
            await asyncio.sleep(10)
            await msg.delete()

        except Exception as e:
            embed = discord.Embed(
                title="❌ 오류 발생",
                description=f"구인 메시지 발송 중 오류가 발생했습니다:\n\n`{str(e)}`",
                color=discord.Color.red(),
            )
            msg = await interaction.followup.send(embed=embed, ephemeral=True)
            await asyncio.sleep(10)
            await msg.delete()
            print(f"❌ 구인 시작 오류: {e}")

    @discord.app_commands.command(name="삭제", description="진행 중인 구인 메시지 삭제")
    async def delete_recruitment(self, interaction: discord.Interaction):
        """
        슬래시 명령어: /삭제
        진행 중인 구인 메시지를 선택하여 삭제합니다
        누구나 사용 가능
        """
        battle_data = load_battle_data()

        if not battle_data:
            embed = discord.Embed(
                title="❌ 구인 메시지 없음",
                description="진행 중인 구인 메시지가 없습니다.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=3)
            return

        embed = discord.Embed(
            title="📋 진행 중인 구인 목록",
            description="삭제할 구인을 선택하세요:",
            color=discord.Color.blue(),
        )

        view = DeleteRecruitmentView(self, battle_data, 0)
        message = await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        if isinstance(message, discord.Message):
            view.children[0].list_message_id = message.id
        else:
            fetched_message = await interaction.original_response()
            view.children[0].list_message_id = fetched_message.id

    async def delete_specific_recruitment(self, interaction: discord.Interaction, message_id: str, list_message_id: int):
        """특정 구인 메시지 삭제 (구인 메시지와 설정 메시지 모두 삭제)"""
        try:
            channel = interaction.channel
            message_id_int = int(message_id)

            try:
                recruitment_msg = await channel.fetch_message(message_id_int)
                await recruitment_msg.delete()
            except discord.NotFound:
                pass

            if message_id_int in recruitment_messages:
                try:
                    settings_msg_id = recruitment_messages[message_id_int].get("settings")
                    if settings_msg_id is not None:
                        settings_msg = await channel.fetch_message(settings_msg_id)
                        await settings_msg.delete()
                except discord.NotFound:
                    pass

                del recruitment_messages[message_id_int]

            try:
                if list_message_id > 0:
                    list_msg = await channel.fetch_message(list_message_id)
                    await list_msg.delete()
            except discord.NotFound:
                pass

            battle_data = load_battle_data()
            if message_id in battle_data:
                del battle_data[message_id]
                save_battle_data(battle_data)

        except Exception as e:
            print(f"❌ 구인 삭제 중 오류: {e}")

    @discord.app_commands.command(name="초대링크", description="HRD Clan Bot 초대 링크 공유")
    @discord.app_commands.check(is_admin_or_owner)
    async def invite_link(self, interaction: discord.Interaction):
        """
        슬래시 명령어: /초대링크
        HRD Clan Bot 초대 링크를 공유합니다
        관리자 또는 서버 주인만 사용 가능
        """
        embed = discord.Embed(
            title="🔗 HRD Clan Bot 초대 링크",
            description="아래 링크를 클릭하여 봇을 서버에 초대하세요!\n\n"
            "✅ 봇 권한: 메세지 보내기, 모두 멘션하기, 링크 임베드\n"
            "✅ 메세지 보내기 및 멘션 기능정도만 작동합니다",
            color=discord.Color.blue(),
            url=INVITE_LINK,
        )

        embed.add_field(
            name="🚀 빠른 시작",
            value="1. 위의 링크를 클릭하여 봇 초대\n"
            "2. `/양식` 명령어로 구인 시작\n"
            "3. `/삭제` 명령어로 구인 신청 삭제\n"
            "4. 팀원들과 함께 플레이!",
            inline=False,
        )

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="봇 초대하기", url=INVITE_LINK, style=discord.ButtonStyle.link))

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    """Cog 로드"""
    await bot.add_cog(Recruitment(bot))
