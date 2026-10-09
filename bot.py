import os
import asyncio
import aiohttp
import io
import math
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, UserSelect
from flask import Flask
from threading import Thread

# Web-server (Render-де бот 24/7 жұмыс істеп тұруы үшін)
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
intents.voice_states = True

# --------------------------------------------------
# НАСТРОЙКИ АВТО-РОЛИ И КАНАЛОВ
# --------------------------------------------------
AUTO_ROLE_ID = 1555292717830119514
WELCOME_CHANNEL_ID = 1497873420216439016
LEVEL_CHANNEL_ID = 1498243470513405992

# База данных опыта и FACEIT верификации в памяти
user_levels = {}
verified_users = {}

# --------------------------------------------------
# БАННЕРЛЕРДІҢ СІЛТЕМЕЛЕРІ (URL)
# --------------------------------------------------
MAIN_BANNER_URL = "https://multibot.pro/api/embeds/images/g4mmec3lwfcrwi4l"
GIRL_BANNER_URL = "https://media.discordapp.net/attachments/1544309714962227230/1557815971660435456/banner_girl.png?ex=6ac92cae&is=6ac7db2e&hm=250e0baedfe61fc5baff21e59e0e6bd61f5e494d88ade315be12b6e3c199c916&=&format=webp&quality=lossless&width=2048&height=729"
MEDIA_BANNER_URL = "https://multibot.pro/api/embeds/images/nfmpvssumgp3km0o"

# --------------------------------------------------
# РӨЛДЕРДІҢ ID'ЛЕРІ
# --------------------------------------------------

STAFF_ROLE_IDS = [
    1557002520696463431,
    1532745811778207985,
    1530888080905601044,
    1530890552676188301,
    1530886657530925256,
    1530888429888602152
]

GIRL_STAFF_ROLE_IDS = [
    1532745811778207985,
    1530890552676188301,
    1530886657530925256
]

MEDIA_STAFF_ROLE_IDS = [
    1530888828246556753,
    1532745811778207985,
    1530886657530925256
]

# --------------------------------------------------
# ЛОГ КАНАЛДАРДЫҢ ID'ЛЕРІ
# --------------------------------------------------
TICKET_LOG_CHANNEL_ID = 1530913548761436361
GIRL_LOG_CHANNEL_ID = 1557062204770230333
MEDIA_LOG_CHANNEL_ID = 1557818240221323414

MEDIA_ROLE_ID = 1530924449912586351

temp_voice_channels = {}


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


async def get_discord_file_from_url(url: str, filename: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.read()
                return discord.File(io.BytesIO(data), filename=filename)
    return None


def has_staff_permission(member: discord.Member, channel_name: str) -> bool:
    user_role_ids = [role.id for role in member.roles]
    
    if "девушка" in channel_name:
        required_roles = GIRL_STAFF_ROLE_IDS
    elif "медиа" in channel_name:
        required_roles = MEDIA_STAFF_ROLE_IDS
    else:
        required_roles = STAFF_ROLE_IDS

    return any(role_id in user_role_ids for role_id in required_roles)


class RenameVoiceModal(Modal, title="Переименовать канал"):
    new_name = TextInput(
        label="Новое название канала",
        placeholder="Введите новое название...",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        voice_channel = interaction.user.voice.channel
        await voice_channel.edit(name=self.new_name.value)
        await interaction.response.send_message(f"✅ Канал переименован в: **{self.new_name.value}**", ephemeral=True)


class UserActionView(View):
    def __init__(self, action: str):
        super().__init__(timeout=60)
        self.action = action

    @discord.ui.select(cls=UserSelect, placeholder="Выберите пользователя...")
    async def select_user(self, interaction: discord.Interaction, select: UserSelect):
        target_member = select.values[0]
        voice_channel = interaction.user.voice.channel

        if self.action == "add":
            await voice_channel.set_permissions(target_member, connect=True, view_channel=True)
            await interaction.response.send_message(f"✅ Пользователю {target_member.mention} доступ разрешен.", ephemeral=True)
        elif self.action == "block":
            await voice_channel.set_permissions(target_member, connect=False)
            if target_member in voice_channel.members:
                await target_member.move_to(None)
            await interaction.response.send_message(f"🚫 Пользователь {target_member.mention} заблокирован.", ephemeral=True)
        elif self.action == "transfer":
            temp_voice_channels[voice_channel.id] = target_member.id
            await interaction.response.send_message(f"👑 Права на канал переданы {target_member.mention}.", ephemeral=True)


class VoiceControlPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    def check_owner(self, interaction: discord.Interaction):
        if not interaction.user.voice or not interaction.user.voice.channel:
            return False, "❌ Вы должны находиться в своем приватном канале!"
        
        voice_channel = interaction.user.voice.channel
        owner_id = temp_voice_channels.get(voice_channel.id)

        if not owner_id or owner_id != interaction.user.id:
            return False, "❌ Вы не являетесь владельцем этого приватного канала!"
            
        return True, voice_channel

    @discord.ui.button(emoji="➕", style=discord.ButtonStyle.secondary, custom_id="vc_add_slot", row=0)
    async def add_slot(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok:
            return await interaction.response.send_message(result, ephemeral=True)
        channel = result
        new_limit = min((channel.user_limit or 0) + 1, 99)
        await channel.edit(user_limit=new_limit)
        await interaction.response.send_message(f"➕ Слот увеличен до **{new_limit}**", ephemeral=True)

    @discord.ui.button(emoji="➖", style=discord.ButtonStyle.secondary, custom_id="vc_remove_slot", row=0)
    async def remove_slot(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok:
            return await interaction.response.send_message(result, ephemeral=True)
        channel = result
        current = channel.user_limit or len(channel.members)
        new_limit = max(current - 1, 1)
        await channel.edit(user_limit=new_limit)
        await interaction.response.send_message(f"➖ Слот уменьшен до **{new_limit}**", ephemeral=True)

    @discord.ui.button(emoji="👤", style=discord.ButtonStyle.secondary, custom_id="vc_add_user", row=0)
    async def add_user(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok:
            return await interaction.response.send_message(result, ephemeral=True)
        await interaction.response.send_message("Выберите пользователя, которому хотите дать доступ:", view=UserActionView("add"), ephemeral=True)

    @discord.ui.button(emoji="🔓", style=discord.ButtonStyle.secondary, custom_id="vc_open", row=0)
    async def open_channel(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok:
            return await interaction.response.send_message(result, ephemeral=True)
        channel = result
        await channel.set_permissions(interaction.guild.default_role, connect=True)
        await interaction.response.send_message("🔓 Канал открыт для всех.", ephemeral=True)

    @discord.ui.button(emoji="🔒", style=discord.ButtonStyle.secondary, custom_id="vc_close", row=0)
    async def close_channel(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok:
            return await interaction.response.send_message(result, ephemeral=True)
        channel = result
        await channel.set_permissions(interaction.guild.default_role, connect=False)
        await interaction.response.send_message("🔒 Канал закрыт от посторонних.", ephemeral=True)

    @discord.ui.button(emoji="👥", style=discord.ButtonStyle.secondary, custom_id="vc_block_user", row=1)
    async def block_user(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok:
            return await interaction.response.send_message(result, ephemeral=True)
        await interaction.response.send_message("Выберите пользователя для блокировки:", view=UserActionView("block"), ephemeral=True)

    @discord.ui.button(emoji="👑", style=discord.ButtonStyle.secondary, custom_id="vc_transfer", row=1)
    async def transfer_owner(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok:
            return await interaction.response.send_message(result, ephemeral=True)
        await interaction.response.send_message("Выберите нового владельца приватного канала:", view=UserActionView("transfer"), ephemeral=True)

    @discord.ui.button(emoji="🙈", style=discord.ButtonStyle.secondary, custom_id="vc_hide", row=1)
    async def hide_channel(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok:
            return await interaction.response.send_message(result, ephemeral=True)
        channel = result
        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await interaction.response.send_message("🙈 Канал скрыт.", ephemeral=True)

    @discord.ui.button(emoji="👁️", style=discord.ButtonStyle.secondary, custom_id="vc_show", row=1)
    async def show_channel(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok:
            return await interaction.response.send_message(result, ephemeral=True)
        channel = result
        await channel.set_permissions(interaction.guild.default_role, view_channel=True)
        await interaction.response.send_message("👁️ Канал снова виден всем.", ephemeral=True)

    @discord.ui.button(emoji="✏️", style=discord.ButtonStyle.secondary, custom_id="vc_rename", row=2)
    async def rename_channel(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok:
            return await interaction.response.send_message(result, ephemeral=True)
        await interaction.response.send_modal(RenameVoiceModal())

    @discord.ui.button(emoji="🚫", style=discord.ButtonStyle.secondary, custom_id="vc_kick_user", row=2)
    async def kick_user_btn(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok:
            return await interaction.response.send_message(result, ephemeral=True)
        await interaction.response.send_message("Выберите пользователя, которого нужно выгнать:", view=UserActionView("block"), ephemeral=True)


class FaceitVerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(
            label="Верифицироваться", 
            emoji="✅", 
            style=discord.ButtonStyle.success, 
            url="https://your-render-app-url.onrender.com/verify"
        ))

    @discord.ui.button(label="Мой профиль", emoji="👤", style=discord.ButtonStyle.primary, custom_id="faceit_profile_btn")
    async def profile_button(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        if user_id in verified_users:
            data = verified_users[user_id]
            await interaction.response.send_message(f"👤 Ваш профиль FACEIT:\n• Уровень: **{data['level']}**\n• Steam: **{data['steam']}**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Вы еще не прошли FACEIT верификацию!", ephemeral=True)

    @discord.ui.button(label="Обновить уровень", emoji="🔄", style=discord.ButtonStyle.secondary, custom_id="faceit_refresh_btn")
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        if user_id in verified_users:
            await interaction.response.send_message("🔄 Ваш FACEIT уровень успешно обновлен!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Сначала пройдите верификацию!", ephemeral=True)

    @discord.ui.button(label="Сбросить профиль", emoji="🛑", style=discord.ButtonStyle.danger, custom_id="faceit_reset_btn")
    async def reset_button(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        if user_id in verified_users:
            del verified_users[user_id]
            await interaction.response.send_message("🛑 Ваш верифицированный профиль сброшен.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ У вас нет привязанного профиля.", ephemeral=True)


class TicketControlView(View):
    def __init__(self, ticket_type: str = "general"):
        super().__init__(timeout=None)
        self.ticket_type = ticket_type

    @discord.ui.button(label="Взяться", style=discord.ButtonStyle.success, custom_id="ticket_take_btn_alash")
    async def take_button(self, interaction: discord.Interaction, button: Button):
        if not has_staff_permission(interaction.user, interaction.channel.name):
            await interaction.response.send_message("❌ У вас нет прав для взаимодействия с тикетом!", ephemeral=True)
            return

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
        if not has_staff_permission(interaction.user, interaction.channel.name):
            await interaction.response.send_message("❌ У вас нет прав для взаимодействия с тикетом!", ephemeral=True)
            return

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
        if not has_staff_permission(interaction.user, interaction.channel.name):
            await interaction.response.send_message("❌ У вас нет прав для взаимодействия с тикетом!", ephemeral=True)
            return

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

        category = interaction.channel.category
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
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
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
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

        category = interaction.channel.category
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Тикет открыт: {user.name}"
        )

        roles_ping_text = " ".join(valid_roles_to_ping) if valid_roles_to_ping else ""
        embed = discord.Embed(
            description=(
                "**Система поддержки ALASH PROJECT KZ**\n\n"
                "**Возникли вопросы, проблемы или нужна помощь? Опишите ситуацию**"
            ),
            color=discord.Color.from_rgb(57, 255, 20)
        )
        embed.add_field(name="• Пользователь", value=user.mention, inline=False)
        embed.add_field(name="• Категория", value=f"{category_selected}", inline=False)

        await ticket_channel.send(
            content=f"{user.mention} {roles_ping_text}".strip(),
            embed=embed,
            view=TicketControlView(ticket_type="general")
        )

        await send_log(
            guild=guild,
            channel_id=TICKET_LOG_CHANNEL_ID,
            title="📩 Новый общий тикет",
            description=f"Пользователь {user.mention} открыл тикет {ticket_channel.mention}",
            color=discord.Color.green(),
            fields={"Категория": category_selected}
        )
        await interaction.followup.send(f"Ваш тикет создан: {ticket_channel.mention}", ephemeral=True)


class TicketMainView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Открыть тикет",
        style=discord.ButtonStyle.secondary,
        custom_id="open_ticket_main_btn_alash"
    )
    async def open_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "Выберите нужную категорию для открытия тикета:",
            view=TicketSelectView(),
            ephemeral=True
        )


class MediaApplicationModal(Modal, title="Подать заявку на Медиа"):
    game_nick = TextInput(
        label="Ваш ник в игре",
        placeholder="Введите игровой ник...",
        required=True,
        max_length=50
    )
    tiktok_link = TextInput(
        label="Ваш тик ток / Канал",
        placeholder="Ссылка на ваш аккаунт/канал",
        required=True,
        max_length=150
    )
    steam_id = TextInput(
        label="Ваш steam ID",
        placeholder="steam ID можете найти у себя в профиле",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user
        channel_name = f"медиа-{user.name}"

        existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if existing_channel:
            await interaction.followup.send(f"У вас уже открыт медиа тикет: {existing_channel.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        valid_roles_to_ping = []
        for role_id in MEDIA_STAFF_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                valid_roles_to_ping.append(role.mention)

        category = interaction.channel.category
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Медиа тикет открыт: {user.name}"
        )

        roles_ping_text = " ".join(valid_roles_to_ping) if valid_roles_to_ping else ""
        embed = discord.Embed(
            title="🎬 Заявка на роль МЕДИА",
            description="Ожидайте ответа от медиа-кураторов.",
            color=discord.Color.red()
        )
        embed.add_field(name="• Пользователь", value=user.mention, inline=False)
        embed.add_field(name="• Ник в игре", value=self.game_nick.value, inline=False)
        embed.add_field(name="• TikTok / Канал", value=self.tiktok_link.value, inline=False)
        embed.add_field(name="• Steam ID", value=self.steam_id.value, inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)

        await ticket_channel.send(
            content=f"{user.mention} {roles_ping_text}".strip(),
            embed=embed,
            view=TicketControlView(ticket_type="media")
        )

        await send_log(
            guild=guild,
            channel_id=MEDIA_LOG_CHANNEL_ID,
            title="🎬 Новая заявка на Медиа",
            description=f"Пользователь {user.mention} подал заявку: {ticket_channel.mention}",
            color=discord.Color.red(),
            fields={
                "Ник в игре": self.game_nick.value,
                "TikTok / Канал": self.tiktok_link.value,
                "Steam ID": self.steam_id.value
            }
        )
        await interaction.followup.send(f"Ваш медиа тикет создан: {ticket_channel.mention}", ephemeral=True)


class MediaMainView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Подать заявку",
        style=discord.ButtonStyle.secondary,
        custom_id="open_media_modal_btn_alash"
    )
    async def apply_media_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(MediaApplicationModal())


class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(TicketMainView())
        self.add_view(GirlTicketMainView())
        self.add_view(TicketControlView())
        self.add_view(MediaMainView())
        self.add_view(VoiceControlPanel())
        self.add_view(FaceitVerifyView())

bot = MyBot()


# --------------------------------------------------
# ЖАҢА ПИКЕТ (БАННЕР МЕН АВАТАРКА ТҮРІНДЕГІ ПРИВЕТСТВИЕ)
# --------------------------------------------------

@bot.event
async def on_member_join(member):
    role = member.guild.get_role(AUTO_ROLE_ID)
    if role:
        try:
            await member.add_roles(role, reason="Автоматическая роль при входе")
        except Exception as e:
            print(f"Ошибка при выдаче роли: {e}")

    welcome_channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        # Сіз сұраған әдемі баннер түрі (Multibot генераторы арқылы қолданушы аватаркасы мен аты шығады)
        embed = discord.Embed(color=discord.Color.from_rgb(255, 50, 50))
        embed.set_image(url=f"https://multibot.pro/api/embeds/images/g4mmec3lwfcrwi4l?avatar={member.display_avatar.url}&name={member.name}")
        
        await welcome_channel.send(content=f"Добро пожаловать на сервер, {member.mention}!", embed=embed)


# --------------------------------------------------
# СИСТЕМА УРОВНЕЙ
# --------------------------------------------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id
    if user_id not in user_levels:
        user_levels[user_id] = {"exp": 0, "level": 1}

    user_levels[user_id]["exp"] += 20
    current_level = user_levels[user_id]["level"]
    exp_needed = current_level * 100

    if user_levels[user_id]["exp"] >= exp_needed:
        user_levels[user_id]["level"] += 1
        new_level = user_levels[user_id]["level"]
        
        level_channel = message.guild.get_channel(LEVEL_CHANNEL_ID)
        if level_channel:
            await level_channel.send(f"Поздравляем {message.author.mention}! Ты достиг {new_level} уровня!")

    await bot.process_commands(message)


@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and ("Создать войс" in after.channel.name or "создать войс" in after.channel.name.lower()):
        category = after.channel.category
        guild = member.guild
        voice_channel = await guild.create_voice_channel(
            name=f"Комната {member.name}",
            category=category,
            reason=f"Приватный войс для {member.name}"
        )
        await voice_channel.set_permissions(member, connect=True, speak=True, manage_channels=True)
        temp_voice_channels[voice_channel.id] = member.id
        await member.move_to(voice_channel)

    if before.channel and before.channel.id in temp_voice_channels:
        if len(before.channel.members) == 0:
            del temp_voice_channels[before.channel.id]
            await before.channel.delete(reason="Временный приватный войс пуст.")


@bot.command()
async def send_verification(ctx):
    embed = discord.Embed(
        title="🛡️ FACEIT Верификация",
        description=(
            "Нажмите кнопку ниже, чтобы пройти верификацию.\n\n"
            "• Проверка Discord\n"
            "• Проверка профиля FACEIT\n"
            "• Проверка привязанного Steam для CS2\n"
            "• Определение FACEIT Level 1–10\n"
            "• Защита от повторной привязки аккаунта\n\n"
            "После успешной проверки бот автоматически выдаст роль верификации и роль вашего FACEIT Level.\n"
            "ALASH PROJECT KZ"
        ),
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=FaceitVerifyView())


@bot.command()
async def send_voice_panel(ctx):
    embed = discord.Embed(
        description=(
            "# **Управление приватной комнатой**\n\n"
            "➕ • Добавить слот\n"
            "👤 • Изменить слоты\n"
            "🔓 • Открыть канал\n"
            "👥 • Добавить пользователь(ля/лей)\n"
            "🙈 • Скрыть канал\n"
            "✏️ • Переименовать канал\n\n"
            "➖ • Убрать слот\n"
            "👑 • Передать канал\n"
            "🔒 • Закрыть канал\n"
            "🚫 • Убрать пользователь(ля/лей)\n"
            "👁️ • Показать канал\n"
            "🚫 • Заблокировать пользователь(ля/лей)\n\n"
            "*Кнопки становятся активными, когда Вы находитесь в своём приватном канале.*"
        ),
        color=discord.Color.dark_grey()
    )
    await ctx.send(embed=embed, view=VoiceControlPanel())


@bot.command()
async def send_girl_ticket(ctx):
    file = await get_discord_file_from_url(GIRL_BANNER_URL, "banner_girl.png")
    if file:
        img_embed = discord.Embed(color=discord.Color.from_rgb(255, 105, 180))
        img_embed.set_image(url="attachment://banner_girl.png")
        await ctx.send(file=file, embed=img_embed)
    else:
        img_embed = discord.Embed(color=discord.Color.from_rgb(255, 105, 180))
        img_embed.set_image(url=GIRL_BANNER_URL)
        await ctx.send(embed=img_embed)

    text_embed = discord.Embed(
        description=(
            "<:18690member:1503151722611347586> **Роль Девушка**\n\n"
            "<a:a_pink_dot:1503133833548271646> Нажмите кнопку ниже, чтобы создать тикет для верификации и получения роли Девушка\n\n"
            "<a:15770animatedarrowyellow:1503049767016595586> **Информация**\n"
            "<a:a_pink_dot:1503133833548271646> Создайте тикет для верификации\n"
            "<a:a_pink_dot:1503133833548271646> Предоставьте доказательства\n"
            "<a:a_pink_dot:1503133833548271646> Модераторы рассмотрят ваш запрос\n\n"
            "<a:15770animatedarrowyellow:1503049767016595586> Чтобы получить роль, откройте тикет или обратитесь к администрации сервера."
        ),
        color=discord.Color.from_rgb(255, 105, 180)
    )
    await ctx.send(embed=text_embed, view=GirlTicketMainView())


@bot.command()
async def send_ticket(ctx):
    file = await get_discord_file_from_url(MAIN_BANNER_URL, "banner.png")
    if file:
        img_embed = discord.Embed(color=discord.Color.from_rgb(57, 255, 20))
        img_embed.set_image(url="attachment://banner.png")
        await ctx.send(file=file, embed=img_embed)
    else:
        img_embed = discord.Embed(color=discord.Color.from_rgb(57, 255, 20))
        img_embed.set_image(url=MAIN_BANNER_URL)
        await ctx.send(embed=img_embed)

    text_embed = discord.Embed(
        description=(
            "<:18690member:1503151722611347586> **Система поддержки ALASH PROJECT KZ**\n\n"
            "<a:15770animatedarrowyellow:1503049767016595586> **Возникли вопросы, проблемы или нужна помощь? Опишите ситуацию**\n\n"
            "<a:15770animatedarrowyellow:1503049767016595586> **Что можно оформить через тикет?**\n"
            "<a:a_pink_dot:1503133833548271646> Жалобы на игроков или пользователей.\n"
            "<a:a_pink_dot:1503133833548271646> Вопросы по серверу или Discord.\n"
            "<a:a_pink_dot:1503133833548271646> Проблемы с верификацией.\n"
            "<a:a_pink_dot:1503133833548271646> Ошибки, баги и технические неполадки."
        ),
        color=discord.Color.from_rgb(57, 255, 20)
    )
    await ctx.send(embed=text_embed, view=TicketMainView())


@bot.command()
async def send_media(ctx):
    file = await get_discord_file_from_url(MEDIA_BANNER_URL, "banner_media.png")
    if file:
        img_embed = discord.Embed(color=discord.Color.from_rgb(180, 0, 0))
        img_embed.set_image(url="attachment://banner_media.png")
        await ctx.send(file=file, embed=img_embed)
    else:
        img_embed = discord.Embed(color=discord.Color.from_rgb(180, 0, 0))
        img_embed.set_image(url=MEDIA_BANNER_URL)
        await ctx.send(embed=img_embed)

    text_embed = discord.Embed(
        description=(
            "<a:a_pink_dot:1503133833548271646> Наш проект готов к сотрудничеству с вами как с медиа игроком (TikTok стримы/видео).\n\n"
            "<a:a_pink_dot:1503133833548271646> Мы предлагаем партнерство, где ваша аудитория и активность помогают продвижению проекта.\n\n"
            "<a:a_pink_dot:1503133833548271646> Мы уверены, что совместно сможем создавать качественный и интересный контент.\n\n"
            f"<a:15770animatedarrowyellow:1503049767016595586> **Что вы получите**\n"
            "<a:a_pink_dot:1503133833548271646> Привилегию на сервере \"Медиа\"\n"
            f"<a:a_pink_dot:1503133833548271646> Роль в Discord <@&{MEDIA_ROLE_ID}>\n"
            "<a:a_pink_dot:1503133833548271646> В привилегию \"MEDIA\" входит весь функционал привилегии \"ALASH\""
        ),
        color=discord.Color.from_rgb(180, 0, 0)
    )
    await ctx.send(embed=text_embed, view=MediaMainView())


bot.run(os.getenv("DISCORD_TOKEN"))
