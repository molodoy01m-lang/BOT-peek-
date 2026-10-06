import os
import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput
from flask import Flask
from threading import Thread

# Web-server (для поддержания работы 24/7 на Render)
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

keep_alive()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# --------------------------------------------------
# БАННЕРЛЕРДІҢ СІЛТЕМЕЛЕРІ (URL)
# --------------------------------------------------
MAIN_BANNER_URL = "https://multibot.pro/api/embeds/images/g4mmec3lwfcrwi4l"
GIRL_BANNER_URL = "https://multibot.pro/api/embeds/images/9hvm8ltfsis07owb"
MEDIA_BANNER_URL = "https://multibot.pro/api/embeds/images/nfmpvssumgp3km0o"

# --------------------------------------------------
# ИДЕНТИФИКАТОРЫ РОЛЕЙ
# --------------------------------------------------

STAFF_ROLE_IDS = [
    1557048240329719870,
    1557048240329719870
]

GIRL_STAFF_ROLE_IDS = [
    1557048240329719870
]

MEDIA_STAFF_ROLE_IDS = [
    1557048240329719870
]

# --------------------------------------------------
# ИДЕНТИФИКАТОРЫ КАНАЛОВ ЛОГОВ
# --------------------------------------------------
TICKET_LOG_CHANNEL_ID = 1557052346939482247
GIRL_LOG_CHANNEL_ID = 1557052405194166405
MEDIA_LOG_CHANNEL_ID = 1557045586820333649

MEDIA_ROLE_ID = 1557044911440928961


# --------------------------------------------------
# ФУНКЦИЯ ОТПРАВКИ ЛОГОВ
# --------------------------------------------------
async def send_log(guild: discord.Guild, channel_id: int, title: str, description: str, color: discord.Color, fields: dict = None):
    log_channel = guild.get_channel(channel_id)
    if log_channel:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=discord.utils.utcnow()
        )
        if fields:
            for name, value in fields.items():
                embed.add_field(name=name, value=value, inline=False)
        embed.set_footer(text="Система логов ALASH PROJECT KZ")
        await log_channel.send(embed=embed)


# --------------------------------------------------
# 1. КНОПКИ УПРАВЛЕНИЯ ВНУТРИ ТИКЕТА
# --------------------------------------------------

class TicketControlView(View):
    def __init__(self, ticket_type: str = "general"):
        super().__init__(timeout=None)
        self.ticket_type = ticket_type

    @discord.ui.button(label="Взяться", style=discord.ButtonStyle.success, custom_id="ticket_take_btn_alash")
    async def take_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await interaction.followup.send(f"**{interaction.user.mention}** взял(а)ся за данный тикет!")

        log_channel_id = (
            GIRL_LOG_CHANNEL_ID if "девушка" in interaction.channel.name
            else MEDIA_LOG_CHANNEL_ID if "медиа" in interaction.channel.name
            else TICKET_LOG_CHANNEL_ID
        )
        await send_log(
            guild=interaction.guild,
            channel_id=log_channel_id,
            title="✋ Тикет взят в работу",
            description=f"Администратор {interaction.user.mention} взял тикет {interaction.channel.mention}",
            color=discord.Color.blue()
        )

    @discord.ui.button(label="Взять на рассмотрение", style=discord.ButtonStyle.primary, custom_id="ticket_review_btn_alash")
    async def review_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await interaction.followup.send(f"**{interaction.user.mention}** взял(а) тикет на рассмотрение.")

        log_channel_id = (
            GIRL_LOG_CHANNEL_ID if "девушка" in interaction.channel.name
            else MEDIA_LOG_CHANNEL_ID if "медиа" in interaction.channel.name
            else TICKET_LOG_CHANNEL_ID
        )
        await send_log(
            guild=interaction.guild,
            channel_id=log_channel_id,
            title="🔍 Тикет на рассмотрении",
            description=f"Администратор {interaction.user.mention} перевел тикет {interaction.channel.mention} на рассмотрение",
            color=discord.Color.orange()
        )

    @discord.ui.button(label="Закрыть тикет", style=discord.ButtonStyle.danger, custom_id="ticket_close_btn_alash")
    async def close_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("***Тикет закрывается и будет удален...***", ephemeral=False)

        log_channel_id = (
            GIRL_LOG_CHANNEL_ID if "девушка" in interaction.channel.name
            else MEDIA_LOG_CHANNEL_ID if "медиа" in interaction.channel.name
            else TICKET_LOG_CHANNEL_ID
        )
        
        await send_log(
            guild=interaction.guild,
            channel_id=log_channel_id,
            title="🔒 Тикет закрыт",
            description=f"Тикет `{interaction.channel.name}` был закрыт модератором {interaction.user.mention}",
            color=discord.Color.red()
        )

        await asyncio.sleep(3)
        await interaction.channel.delete(reason=f"Тикет закрыт: {interaction.user.name}")


# --------------------------------------------------
# 2. ТИКЕТ ДЛЯ ДЕВУШЕК
# --------------------------------------------------

class GirlTicketMainView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Получить роль девушка",
        emoji="🌸",
        style=discord.ButtonStyle.secondary,
        custom_id="open_girl_ticket_btn_alash"
    )
    async def open_girl_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user

        channel_name = f"девушка-{user.name}"

        existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if existing_channel:
            await interaction.followup.send(f"У вас уже открыт тикет для верификации: {existing_channel.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        valid_roles_to_ping = []
        for role_id in GIRL_STAFF_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                valid_roles_to_ping.append(role.mention)

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            reason=f"Верификация девушки: {user.name}"
        )

        roles_ping_text = " ".join(valid_roles_to_ping) if valid_roles_to_ping else ""

        embed = discord.Embed(
            description=(
                "**🌸 Заявка на получение роли Девушки**\n\n"
                "Здравствуйте! Ожидайте ответа от администрации или модераторов.\n"
                "Подготовьтесь пройти краткую верификацию для подтверждения аккаунта."
            ),
            color=discord.Color.from_rgb(255, 105, 180)
        )
        embed.add_field(name="• Пользователь", value=user.mention, inline=False)

        await ticket_channel.send(
            content=f"{user.mention} {roles_ping_text}".strip(),
            embed=embed,
            view=TicketControlView(ticket_type="girl")
        )

        await send_log(
            guild=guild,
            channel_id=GIRL_LOG_CHANNEL_ID,
            title="🌸 Новый тикет (Девушка)",
            description=f"Пользователь {user.mention} создал тикет верификации: {ticket_channel.mention}",
            color=discord.Color.from_rgb(255, 105, 180)
        )

        await interaction.followup.send(f"Ваш тикет создан: {ticket_channel.mention}", ephemeral=True)


# --------------------------------------------------
# 3. ОБЩИЕ ТИКЕТЫ
# --------------------------------------------------

class TicketSelectView(View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(
        placeholder="Выберите категорию тикета...",
        options=[
            discord.SelectOption(label="Жалоба на игроков или пользователей", value="Жалоба на игроков", description="Пожаловаться на игрока"),
            discord.SelectOption(label="Вопросы по серверу или Discord", value="Вопросы по серверу", description="Вопросы по серверу"),
            discord.SelectOption(label="Проблемы с верификацией", value="Проблемы с верификацией", description="Проблемы с аккаунтом"),
            discord.SelectOption(label="Ошибки, баги и технические неполадки", value="Баги и неполадки", description="Технические проблемы"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: Select):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user
        category_selected = select.values[0]

        channel_name = f"заявление-{user.name}"

        existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if existing_channel:
            await interaction.followup.send(f"У вас уже открыт тикет: {existing_channel.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        valid_roles_to_ping = []
        for role_id in STAFF_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                valid_roles_to_ping.append(role.mention)

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            reason=f"Тикет открыт: {user.name}"
        )

        roles_ping_text = " ".join(valid_roles_to_ping) if valid_roles_to_ping else ""

        embed = discord.Embed(
            description=(
                "**Система поддержки ALASH PROJECT KZ**\n\n"
                "**Возникли вопросы, проблемы или нужна помощь? Опишите ситуацию**"
            ),
            color=discord.Color.from_rgb(67, 18
