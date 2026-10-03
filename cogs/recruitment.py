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

# 현재 구인 메시지를 추적하는 딕셔너리
recruitment_messages = {}

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
    """players를 최대 인원 기준으로 정규화"""
    normalized = list(players or [])[:max_players]
    normalized.extend([None] * (max_players - len(normalized)))
    return normalized


def _get_battle_data_path() -> str:
    """배틀 데이터 파일 경로 반환"""
    data_dir = os.path.join(directory, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "pending_recruitment.json")


async def is_admin_or_owner(interaction: discord.Interaction) -> bool:
    """사용자가 관리자 또는 서버 주인인지 확인"""
    if not interaction.guild:
        return False
    return interaction.user.id == interaction.guild.owner_id or interaction.user.guild_permissions.administrator


async def can_manage_recruitment(interaction: discord.Interaction, data: Optional[dict]) -> bool:
    """작성자 본인 또는 관리자/서버 주인인지 확인"""
    if await is_admin_or_owner(interaction):
        return True
    author_id = (data or {}).get("author_id")
    return author_id is not None and author_id == interaction.user.id


async def get_manageable_recruitments(interaction: discord.Interaction, battle_data: dict) -> dict:
    """요청한 유저가 관리할 수 있는 구인만 반환"""
    if await is_admin_or_owner(interaction):
        return dict(battle_data)
    return {
        message_id: data
        for message_id, data in battle_data.items()
        if data.get("author_id") is not None and data.get("author_id") == interaction.user.id
    }


class BattleView(discord.ui.View):
    """참여 인원을 관리하는 뷰"""
    def __init__(
        self,
        message_id: int = None,
        game_time: str = "미정",
        game_type: str = "미정",
        max_players: int = 4,
        voice_channel: str = "미정",
        author_id: int = None,
    ):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.game_time = game_time
        self.game_type = game_type
        self.max_players = max_players
        self.voice_channel = voice_channel
        self.author_id = author_id
        self.players = [None] * max_players

        if message_id:
            battle_data = load_battle_data()
            if str(message_id) in battle_data:
                data = battle_data[str(message_id)]
                player_ids = data.get("players", [])
                self.players = _normalize_players(player_ids, max_players)
                self.author_id = data.get("author_id", self.author_id)

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

        author_line = f"✍️ 작성자: <@{self.author_id}>\n" if self.author_id else ""

        description = (
            "🎮 BATTLEGROUND\n"
            f"{author_line}"
            f"게임 시간: {self.game_time}\n"
            f"게임종류: {self.game_type}\n"
            f"📍 음성채널: {self.voice_channel}\n"
            f"모집 인원: {self.max_players}명\n\n"
            "참여인원\n"
            + "\n".join(player_lines)
        )

        return discord.Embed(
            title="배틀그라운드 스쿼드 모집",
            description=description,
            color=discord.Color.blue(),
        )

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
            "author_id": self.author_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        save_battle_data(battle_data)

    @discord.ui.button(label="참여", style=discord.ButtonStyle.green, custom_id="join_btn")
    async def join_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user

        if any(_is_same_player(player, user) for player in self.players):
            await interaction.response.send_message("이미 참여하셨습니다!", ephemeral=True, delete_after=5)
            return

        empty_index = next((index for index, player in enumerate(self.players) if player is None), None)
        if empty_index is None:
            await interaction.response.send_message("자리가 모두 찼습니다!", ephemeral=True, delete_after=10)
            return

        self.players[empty_index] = user
        self.save_players()
        await interaction.message.edit(embed=self.create_embed())
        await interaction.response.send_message(
            f"참여가 완료되었습니다! ({empty_index + 1}번 슬롯)", ephemeral=True, delete_after=3
        )

    @discord.ui.button(label="참여취소", style=discord.ButtonStyle.red, custom_id="leave_btn")
    async def leave_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user

        for index, player in enumerate(self.players):
            if _is_same_player(player, user):
                self.players[index] = None
                self.save_players()
                await interaction.message.edit(embed=self.create_embed())
                await interaction.response.send_message("참여가 취소되었습니다.", ephemeral=True, delete_after=3)
                return

        await interaction.response.send_message("참여 목록에 없습니다.", ephemeral=True, delete_after=5)


def load_battle_data() -> dict:
    """저장된 배틀 데이터 로드"""
    data_file = _get_battle_data_path()
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
    data_file = _get_battle_data_path()

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

    def __init__(self, cog, user_id: int, session_token: int):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.session_token = session_token

    async def on_submit(self, interaction: discord.Interaction):
        session = self.cog.get_session(self.user_id, self.session_token)
        if not session:
            await interaction.response.send_message(
                "❌ 설정 세션을 찾을 수 없습니다. `/양식`을 다시 실행해주세요.",
                ephemeral=True,
                delete_after=5,
            )
            return

        session["recruitment_settings"]["game_time"] = self.game_time.value
        session["setting_notifications"].append(interaction)
        await interaction.response.send_message(
            f"✅ 게임 시간이 '{self.game_time.value}'로 설정되었습니다!",
            ephemeral=True,
        )
        await self.cog.check_and_start_recruitment(self.user_id, interaction)


class GameTypeModal(discord.ui.Modal, title="게임 종류 설정"):
    """게임 종류 입력 모달"""
    game_type = discord.ui.TextInput(
        label="게임 종류",
        placeholder="예: 일반, 경쟁, 미니게임, 커스텀 등",
        required=True,
        max_length=50,
    )

    def __init__(self, cog, user_id: int, session_token: int):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.session_token = session_token

    async def on_submit(self, interaction: discord.Interaction):
        session = self.cog.get_session(self.user_id, self.session_token)
        if not session:
            await interaction.response.send_message(
                "❌ 설정 세션을 찾을 수 없습니다. `/양식`을 다시 실행해주세요.",
                ephemeral=True,
                delete_after=5,
            )
            return

        session["recruitment_settings"]["game_type"] = self.game_type.value
        session["setting_notifications"].append(interaction)
        await interaction.response.send_message(
            f"✅ 게임 종류가 '{self.game_type.value}'로 설정되었습니다!",
            ephemeral=True,
        )
        await self.cog.check_and_start_recruitment(self.user_id, interaction)


class PlayerCountModal(discord.ui.Modal, title="인원 설정"):
    """인원 수 입력 모달"""
    player_count = discord.ui.TextInput(
        label="모집 인원 (2~4명)",
        placeholder="예: 2 (듀오) 또는 4 (스쿼드)",
        required=True,
        max_length=1,
    )

    def __init__(self, cog, user_id: int, session_token: int):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.session_token = session_token

    async def on_submit(self, interaction: discord.Interaction):
        session = self.cog.get_session(self.user_id, self.session_token)
        if not session:
            await interaction.response.send_message(
                "❌ 설정 세션을 찾을 수 없습니다. `/양식`을 다시 실행해주세요.",
                ephemeral=True,
                delete_after=5,
            )
            return

        try:
            count = int(self.player_count.value)

            if count < 2 or count > 4:
                session["setting_notifications"].append(interaction)
                await interaction.response.send_message(
                    "❌ 인원은 2명(듀오) ~ 4명(스쿼드) 사이여야 합니다!",
                    ephemeral=True,
                    delete_after=3,
                )
                return

            session["recruitment_settings"]["player_count"] = count

            if count == 2:
                player_type = "듀오"
            elif count == 3:
                player_type = "트리오"
            else:
                player_type = "스쿼드"

            session["setting_notifications"].append(interaction)
            await interaction.response.send_message(
                f"✅ 모집 인원이 {count}명({player_type})으로 설정되었습니다!",
                ephemeral=True,
            )
            await self.cog.check_and_start_recruitment(self.user_id, interaction)

        except ValueError:
            session["setting_notifications"].append(interaction)
            await interaction.response.send_message(
                "❌ 숫자를 입력해주세요! (2 또는 3 또는 4)",
                ephemeral=True,
                delete_after=3,
            )


class VoiceChannelSelect(discord.ui.Select):
    """음성 채널 선택 드롭다운"""
    def __init__(
        self,
        cog,
        guild: discord.Guild,
        user_id: int,
        session_token: int,
        voice_channel_interaction: discord.Interaction = None,
    ):
        self.cog = cog
        self.guild = guild
        self.user_id = user_id
        self.session_token = session_token
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
        session = self.cog.get_session(self.user_id, self.session_token)
        if not session:
            await interaction.response.send_message(
                "❌ 설정 세션을 찾을 수 없습니다. `/양식`을 다시 실행해주세요.",
                ephemeral=True,
                delete_after=5,
            )
            return

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
            session["recruitment_settings"]["voice_channel"] = f"#{channel.name}"

            if self.voice_channel_interaction:
                try:
                    await self.voice_channel_interaction.delete_original_response()
                except Exception:
                    pass

            await self.cog.check_and_start_recruitment(self.user_id, interaction)


class VoiceChannelView(discord.ui.View):
    """음성 채널 선택 뷰"""
    def __init__(
        self,
        cog,
        guild: discord.Guild,
        user_id: int,
        session_token: int,
        voice_channel_interaction: discord.Interaction = None,
    ):
        super().__init__(timeout=300)
        self.add_item(VoiceChannelSelect(cog, guild, user_id, session_token, voice_channel_interaction))


class SettingsView(discord.ui.View):
    """게임 설정 입력 버튼 뷰"""
    def __init__(self, cog, user_id: int, session_token: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.session_token = session_token

    @discord.ui.button(label="시간 설정", style=discord.ButtonStyle.blurple, custom_id="time_input_btn")
    async def time_input_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GameTimeModal(self.cog, self.user_id, self.session_token))

    @discord.ui.button(label="종류 설정", style=discord.ButtonStyle.blurple, custom_id="type_input_btn")
    async def type_input_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GameTypeModal(self.cog, self.user_id, self.session_token))

    @discord.ui.button(label="인원 설정", style=discord.ButtonStyle.blurple, custom_id="player_input_btn")
    async def player_input_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PlayerCountModal(self.cog, self.user_id, self.session_token))

    @discord.ui.button(label="채널 선택", style=discord.ButtonStyle.blurple, custom_id="channel_select_btn")
    async def channel_select_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = VoiceChannelView(
            self.cog,
            interaction.guild,
            self.user_id,
            self.session_token,
            interaction,
        )
        embed = discord.Embed(
            title="🎧 음성 채널 선택",
            description="아래 드롭다운에서 게임할 음성 채널을 선택하세요!",
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


def _author_suffix(interaction: discord.Interaction, data: dict) -> str:
    """드롭다운 라벨용 작성자 표시"""
    author_id = data.get("author_id")
    if not author_id:
        return ""
    member = interaction.guild.get_member(author_id) if interaction.guild else None
    return f" - 작성자: {member.display_name if member else author_id}"


class DeleteRecruitmentSelect(discord.ui.Select):
    """삭제할 구인 선택 드롭다운"""
    def __init__(self, cog, recruitments: Dict, list_message_id: int, interaction: discord.Interaction):
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

            label = f"{game_time} - {game_type} ({max_players}명) ({time_diff}){_author_suffix(interaction, data)}"
            options.append(discord.SelectOption(label=label[:100], value=message_id))

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
    def __init__(self, cog, recruitments: Dict, list_message_id: int, interaction: discord.Interaction):
        super().__init__(timeout=300)
        self.add_item(DeleteRecruitmentSelect(cog, recruitments, list_message_id, interaction))


class EditState:
    """/수정 에서 다시 입력받는 설정"""
    def __init__(self, message_id: str, channel):
        self.message_id = message_id
        self.channel = channel
        self.game_time = "미정"
        self.game_type = "미정"
        self.player_count = 0
        self.voice_channel = "미정"
        self.notifications = []
        self.done = False

    def is_complete(self) -> bool:
        return (
            self.game_time != "미정"
            and self.game_type != "미정"
            and self.player_count > 0
            and self.voice_channel != "미정"
        )


class EditGameTimeModal(discord.ui.Modal, title="게임 시간 수정"):
    game_time = discord.ui.TextInput(label="게임 시간", placeholder="예: 오후 6시", required=True, max_length=50)

    def __init__(self, cog, state: EditState):
        super().__init__()
        self.cog = cog
        self.state = state

    async def on_submit(self, interaction: discord.Interaction):
        self.state.game_time = self.game_time.value
        await self.cog.after_edit_input(
            interaction, self.state, f"✅ 게임 시간이 '{self.game_time.value}'로 설정되었습니다!"
        )


class EditGameTypeModal(discord.ui.Modal, title="게임 종류 수정"):
    game_type = discord.ui.TextInput(label="게임 종류", placeholder="예: 일반, 경쟁", required=True, max_length=50)

    def __init__(self, cog, state: EditState):
        super().__init__()
        self.cog = cog
        self.state = state

    async def on_submit(self, interaction: discord.Interaction):
        self.state.game_type = self.game_type.value
        await self.cog.after_edit_input(
            interaction, self.state, f"✅ 게임 종류가 '{self.game_type.value}'로 설정되었습니다!"
        )


class EditPlayerCountModal(discord.ui.Modal, title="인원 수정"):
    player_count = discord.ui.TextInput(label="모집 인원 (2~4명)", placeholder="예: 2 또는 4", required=True, max_length=1)

    def __init__(self, cog, state: EditState):
        super().__init__()
        self.cog = cog
        self.state = state

    async def on_submit(self, interaction: discord.Interaction):
        try:
            count = int(self.player_count.value)
        except ValueError:
            count = 0
        if count < 2 or count > 4:
            await interaction.response.send_message(
                "❌ 인원은 2명(듀오) ~ 4명(스쿼드) 사이의 숫자여야 합니다!", ephemeral=True, delete_after=3
            )
            return
        self.state.player_count = count
        await self.cog.after_edit_input(interaction, self.state, f"✅ 모집 인원이 {count}명으로 설정되었습니다!")


class EditVoiceChannelSelect(discord.ui.Select):
    def __init__(self, cog, guild: discord.Guild, state: EditState, channel_interaction: discord.Interaction):
        self.cog = cog
        self.guild = guild
        self.state = state
        self.channel_interaction = channel_interaction

        options = [
            discord.SelectOption(label=f"🎮 {channel.name}"[:100], value=str(channel.id))
            for channel in guild.channels
            if isinstance(channel, discord.VoiceChannel)
        ][:25]
        super().__init__(
            placeholder="음성 채널을 선택하세요...",
            options=options if options else [discord.SelectOption(label="음성 채널 없음", value="none")],
            disabled=len(options) == 0,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("❌ 사용 가능한 음성 채널이 없습니다!", ephemeral=True, delete_after=3)
            return
        channel = self.guild.get_channel(int(self.values[0]))
        if not channel:
            return
        self.state.voice_channel = f"#{channel.name}"
        try:
            await self.channel_interaction.delete_original_response()
        except Exception:
            pass
        await self.cog.check_and_apply_edit(interaction, self.state)


class EditSettingsView(discord.ui.View):
    """구인 수정용 설정 버튼 뷰"""
    def __init__(self, cog, state: EditState):
        super().__init__(timeout=300)
        self.cog = cog
        self.state = state

    @discord.ui.button(label="시간 설정", style=discord.ButtonStyle.blurple)
    async def time_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditGameTimeModal(self.cog, self.state))

    @discord.ui.button(label="종류 설정", style=discord.ButtonStyle.blurple)
    async def type_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditGameTypeModal(self.cog, self.state))

    @discord.ui.button(label="인원 설정", style=discord.ButtonStyle.blurple)
    async def count_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditPlayerCountModal(self.cog, self.state))

    @discord.ui.button(label="채널 선택", style=discord.ButtonStyle.blurple)
    async def channel_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View(timeout=300)
        view.add_item(EditVoiceChannelSelect(self.cog, interaction.guild, self.state, interaction))
        embed = discord.Embed(
            title="🎧 음성 채널 선택",
            description="아래 드롭다운에서 게임할 음성 채널을 선택하세요!",
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class EditRecruitmentSelect(discord.ui.Select):
    """수정할 구인 선택 드롭다운"""
    def __init__(self, cog, recruitments: Dict, interaction: discord.Interaction):
        self.cog = cog
        options = []
        for message_id, data in recruitments.items():
            label = (
                f"{data.get('game_time', '미정')} - {data.get('game_type', '미정')} "
                f"({data.get('max_players', 4)}명) ({get_time_difference(data.get('created_at', ''))})"
                f"{_author_suffix(interaction, data)}"
            )
            options.append(discord.SelectOption(label=label[:100], value=message_id))

        super().__init__(placeholder="수정할 구인을 선택하세요...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await self.cog.start_edit(interaction, self.values[0])


class EditRecruitmentView(discord.ui.View):
    def __init__(self, cog, recruitments: Dict, interaction: discord.Interaction):
        super().__init__(timeout=300)
        self.add_item(EditRecruitmentSelect(cog, recruitments, interaction))


class Recruitment(commands.Cog):
    """구인 관련 명령어 및 기능"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: Dict[int, dict] = {}
        self.session_counter = 0

    def _new_session(self, session_token: int) -> dict:
        return {
            "recruitment_settings": {
                "game_time": "미정",
                "game_type": "미정",
                "player_count": 0,
                "voice_channel": "미정",
            },
            "settings_interaction": None,
            "recruiter": None,
            "interaction_channel": None,
            "setting_notifications": [],
            "session_token": session_token,
        }

    def get_session(self, user_id: int, session_token: Optional[int] = None) -> Optional[dict]:
        session = self.sessions.get(user_id)
        if not session:
            return None
        if session_token is not None and session.get("session_token") != session_token:
            return None
        return session

    def is_recruitment_complete(self, user_id: int) -> bool:
        """모든 설정이 완료되었는지 확인"""
        session = self.get_session(user_id)
        if not session:
            return False

        recruitment_settings = session["recruitment_settings"]
        return (
            recruitment_settings["game_time"] != "미정"
            and recruitment_settings["game_type"] != "미정"
            and recruitment_settings["player_count"] > 0
            and recruitment_settings["voice_channel"] != "미정"
        )

    async def check_and_start_recruitment(self, user_id: int, interaction: discord.Interaction):
        """설정 완료 여부 확인 후 구인 시작"""
        if self.is_recruitment_complete(user_id):
            await self.start_recruitment(user_id, interaction)

    async def clear_setting_notifications(self, user_id: int):
        """설정 완료 메시지들 삭제"""
        session = self.get_session(user_id)
        if not session:
            return

        setting_notifications = session["setting_notifications"]
        for notification_interaction in list(setting_notifications):
            try:
                await notification_interaction.delete_original_response()
            except Exception:
                pass
        setting_notifications.clear()

    @discord.app_commands.command(name="양식", description="배틀그라운드 구인 설정")
    async def recruitment_settings_slash(self, interaction: discord.Interaction):
        """슬래시 명령어: /양식 - 게임 시간, 종류, 인원, 음성 채널을 설정하여 구인 시작"""
        user_id = interaction.user.id
        self.session_counter += 1
        self.sessions[user_id] = self._new_session(self.session_counter)
        session = self.sessions[user_id]
        session["settings_interaction"] = interaction
        session["interaction_channel"] = interaction.channel
        session["recruiter"] = interaction.user

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

        view = SettingsView(cog=self, user_id=user_id, session_token=session["session_token"])
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def start_recruitment(self, user_id: int, interaction: discord.Interaction):
        """구인 메시지 자동 발송"""
        session = self.get_session(user_id)
        if not session:
            return

        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass

        recruitment_settings = session["recruitment_settings"]
        channel = session.get("interaction_channel") or interaction.channel
        player_count = recruitment_settings.get("player_count", 4)
        settings_interaction = session.get("settings_interaction")
        recruiter = session.get("recruiter")

        if settings_interaction:
            try:
                await settings_interaction.delete_original_response()
            except Exception:
                pass
        
        await self.clear_setting_notifications(user_id)
        session["settings_interaction"] = None

        view = BattleView(
            game_time=recruitment_settings.get("game_time", "미정"),
            game_type=recruitment_settings.get("game_type", "미정"),
            max_players=player_count,
            voice_channel=recruitment_settings.get("voice_channel", "미정"),
            author_id=recruiter.id if recruiter else None,
        )

        try:
            if player_count == 2:
                player_type = "듀오"
            elif player_count == 3:
                player_type = "트리오"
            else:
                player_type = "스쿼드"

            if recruiter:
                view.players[0] = recruiter

            message = await channel.send(
                "@here 🎮 배틀그라운드 스쿼드 구인이 시작되었습니다! "
                f"({player_type} - {recruitment_settings.get('game_time')} - {recruitment_settings.get('game_type')})",
                embed=view.create_embed(),
                view=view,
            )

            view.message_id = message.id
            view.save_players()

            recruitment_messages[message.id] = {
                "recruitment": message.id,
                "settings": settings_interaction.id if settings_interaction else None,
            }
            self.sessions.pop(user_id, None)

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
        """슬래시 명령어: /삭제 - 진행 중인 구인 메시지를 선택하여 삭제"""
        battle_data = await get_manageable_recruitments(interaction, load_battle_data())

        if not battle_data:
            embed = discord.Embed(
                title="❌ 구인 메시지 없음",
                description="삭제할 수 있는 구인 공고가 없습니다 (본인이 작성한 공고만 삭제 가능합니다).",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=3)
            return

        embed = discord.Embed(
            title="📋 진행 중인 구인 목록",
            description="삭제할 구인을 선택하세요:",
            color=discord.Color.blue(),
        )

        view = DeleteRecruitmentView(self, battle_data, 0, interaction)
        message = await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        if isinstance(message, discord.Message):
            view.children[0].list_message_id = message.id
        else:
            fetched_message = await interaction.original_response()
            view.children[0].list_message_id = fetched_message.id

    async def delete_specific_recruitment(self, interaction: discord.Interaction, message_id: str, list_message_id: int):
        """특정 구인 메시지 삭제"""
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        
        battle_data = load_battle_data()
        recruitment_data = battle_data.get(message_id)
        if not await can_manage_recruitment(interaction, recruitment_data):
            await interaction.followup.send("❌ 본인이 작성한 구인 공고만 삭제할 수 있습니다.", ephemeral=True)
            return

        try:
            channel = interaction.channel
            message_id_int = int(message_id)
            
            # 1️⃣ 구인 메시지 삭제
            try:
                recruitment_msg = await channel.fetch_message(message_id_int)
                await recruitment_msg.delete()
            except discord.NotFound:
                pass
            
            # 2️⃣ 데이터 저장소에서 삭제
            battle_data = load_battle_data()
            if message_id in battle_data:
                del battle_data[message_id]
                save_battle_data(battle_data)
            
            # 관리자가 타인의 공고를 삭제한 경우 작성자에게 DM 알림
            author_id = (recruitment_data or {}).get("author_id")
            if author_id and author_id != interaction.user.id:
                await self.notify_author_deleted(interaction, author_id, recruitment_data)

            # 3️⃣ 목록 메시지 삭제
            try:
                list_msg = await interaction.original_response()
                await list_msg.delete()
            except:
                pass
            
            # 4️⃣ 완료 메시지
            msg = await interaction.followup.send("✅ 구인 메시지가 삭제되었습니다!", ephemeral=True)
            await asyncio.sleep(3)
            try:
                await msg.delete()
            except:
                pass
            
        except Exception as e:
            print(f"❌ 구인 삭제 중 오류: {e}")
            try:
                msg = await interaction.followup.send(f"❌ 오류: {str(e)}", ephemeral=True)
                await asyncio.sleep(5)
                await msg.delete()
            except:
                pass

    async def notify_author_deleted(self, interaction: discord.Interaction, author_id: int, data: dict):
        """관리자 삭제 시 작성자에게 DM 전송 (실패해도 무시)"""
        try:
            author = interaction.guild.get_member(author_id) or await self.bot.fetch_user(author_id)
            embed = discord.Embed(
                title="🗑️ 구인 공고 삭제 알림",
                description=(
                    f"관리자에 의해 회원님이 작성하신 구인 공고(게임 시간: {data.get('game_time', '미정')}, "
                    f"게임 종류: {data.get('game_type', '미정')})가 삭제되었습니다.\n\n"
                    f"서버: {interaction.guild.name}"
                ),
                color=discord.Color.red(),
            )
            await author.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    @discord.app_commands.command(name="수정", description="진행 중인 구인 공고 설정 수정")
    async def edit_recruitment(self, interaction: discord.Interaction):
        """슬래시 명령어: /수정 - 본인이 작성한 구인 공고의 설정을 다시 입력"""
        battle_data = await get_manageable_recruitments(interaction, load_battle_data())

        if not battle_data:
            embed = discord.Embed(
                title="❌ 구인 메시지 없음",
                description="수정할 수 있는 구인 공고가 없습니다 (본인이 작성한 공고만 수정 가능합니다).",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=3)
            return

        embed = discord.Embed(
            title="📋 진행 중인 구인 목록",
            description="수정할 구인을 선택하세요:",
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(
            embed=embed, view=EditRecruitmentView(self, battle_data, interaction), ephemeral=True
        )

    async def start_edit(self, interaction: discord.Interaction, message_id: str):
        """선택한 구인의 수정용 설정 뷰 표시"""
        if not await can_manage_recruitment(interaction, load_battle_data().get(message_id)):
            await interaction.response.send_message(
                "❌ 본인이 작성한 구인 공고만 수정할 수 있습니다.", ephemeral=True
            )
            return

        state = EditState(message_id, interaction.channel)
        embed = discord.Embed(
            title="⚙️ 구인 공고 수정",
            description="아래 버튼으로 시간, 종류, 인원, 음성 채널을 모두 다시 입력하세요!\n\n"
            "모든 설정을 완료하면 기존 구인 공고가 수정됩니다.",
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, view=EditSettingsView(self, state), ephemeral=True)

    async def after_edit_input(self, interaction: discord.Interaction, state: EditState, text: str):
        await interaction.response.send_message(text, ephemeral=True)
        state.notifications.append(interaction)
        await self.check_and_apply_edit(interaction, state)

    async def check_and_apply_edit(self, interaction: discord.Interaction, state: EditState):
        """4개 항목이 모두 입력되면 기존 구인 메시지 수정"""
        if state.done or not state.is_complete():
            return
        state.done = True

        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        battle_data = load_battle_data()
        data = battle_data.get(state.message_id)
        if data is None or not await can_manage_recruitment(interaction, data):
            await interaction.followup.send("❌ 본인이 작성한 구인 공고만 수정할 수 있습니다.", ephemeral=True)
            return

        try:
            view = BattleView(
                message_id=int(state.message_id),
                game_time=state.game_time,
                game_type=state.game_type,
                max_players=state.player_count,
                voice_channel=state.voice_channel,
                author_id=data.get("author_id"),
            )
            message = await state.channel.fetch_message(int(state.message_id))
            await message.edit(embed=view.create_embed(), view=view)
            view.save_players()
        except Exception as e:
            state.done = False
            print(f"❌ 구인 수정 중 오류: {e}")
            await interaction.followup.send(f"❌ 오류: {str(e)}", ephemeral=True)
            return

        for notification in state.notifications:
            try:
                await notification.delete_original_response()
            except Exception:
                pass
        await interaction.followup.send("✅ 구인 공고가 수정되었습니다!", ephemeral=True)

    @discord.app_commands.command(name="초대링크", description="HRD Clan Bot 초대 링크 공유")
    @discord.app_commands.check(is_admin_or_owner)
    async def invite_link(self, interaction: discord.Interaction):
        """슬래시 명령어: /초대링크 - HRD Clan Bot 초대 링크를 공유 (관리자 또는 서버 주인만 사용 가능)"""
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
