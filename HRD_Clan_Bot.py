import discord
from discord.ext import commands

# 봇 설정 (Intents 필요)
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=".", intents=intents)


# 참여 인원을 관리하는 View 클래스
class BattleView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)  # 버튼이 사라지지 않도록 설정
    self.players = [None, None, None, None]  # 4명의 자리

  def create_embed(self):
    # 참여인원 텍스트 생성
    player_list_str = ""
    for i in range(4):
      if self.players[i]:
        player_list_str += f"{i+1}. {self.players[i].mention}\n"
      else:
        player_list_str += f"{i+1}.\n"

    # 출력할 양식 텍스트
    description = (
        "🎮 BATTLEGROUND @here\n"
        "게임 시간: 모바시\n"
        "게임종류: 경쟁전\n\n"
        "참여인원\n"
        f"{player_list_str}"
    )

    embed = discord.Embed(
        title="배틀그라운드 스쿼드 모집",
        description=description,
        color=discord.Color.blue(),
    )
    return embed

  @discord.ui.button(
      label="참여하기", style=discord.ButtonStyle.green, custom_id="join_btn"
  )
  async def join_callback(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    user = interaction.user

    # 이미 참여했는지 확인
    if user in self.players:
      await interaction.response.send_message(
          "이미 참여하셨습니다!", ephemeral=True
      )
      return

    # 빈자리가 있는지 확인
    try:
      empty_index = self.players.index(None)
      self.players[empty_index] = user
      await interaction.message.edit(embed=self.create_embed())
      await interaction.response.send_message(
          "참여가 완료되었습니다!", ephemeral=True
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

    # 참여 목록에 있는지 확인
    if user in self.players:
      index = self.players.index(user)
      self.players[index] = None
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


@bot.command(name="BATTLEGROUND")
async def battleground(ctx):
  # 명령어 입력 메시지 삭제 (선택사항)
  await ctx.message.delete()

  view = BattleView()
  await ctx.send(embed=view.create_embed(), view=view)


# 봇 토큰 입력
bot.run("YOUR_BOT_TOKEN_HERE")