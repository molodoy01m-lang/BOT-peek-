import os
import asyncio
import aiohttp
import io
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
# БАПТАУЛАР ЖӘНЕ ID КАНАЛДАР
# --------------------------------------------------
AUTO_ROLE_ID = 1555292717830119514
WELCOME_CHANNEL_ID = 1497873420216439016
LEVEL_CHANNEL_ID = 1498243470513405992

user_levels = {}
verified_users = {}

GIRL_BANNER_URL = "https://media.discordapp.net/attachments/1544309714962227230/1557815971660435456/banner_girl.png?ex=6ac92cae&is=6ac7db2e&hm=250e0baedfe61fc5baff21e59e0e6bd61f5e494d88ade315be12b6e3c199c916&=&format=webp&quality=lossless&width=2048&height=729"
MEDIA_BANNER_URL = "https://multibot.pro/api/embeds/images/nfmpvssumgp3km0o"
TICKET_BANNER_URL = "https://multibot.pro/api/embeds/images/g4mmec3lwfcrwi4l"

STAFF_ROLE_IDS = [
    1557002520696463431, 1532745811778207985, 1530888080905601044,
    1530890552676188301, 1530886657530925256, 1530888429888602152
]
GIRL_STAFF_ROLE_IDS = [1532745811778207985, 1530890552676188301, 1530886657530925256]
MEDIA_STAFF_ROLE_IDS = [1530888828246556753, 1532745811778207985, 1530886657530925256]

TICKET_LOG_CHANNEL_ID = 1530913548761436361
GIRL_LOG_CHANNEL_ID = 1557062204770230333
MEDIA_LOG_CHANNEL_ID = 1557818240221323414
MEDIA_ROLE_ID = 1530924449912586351

temp_voice_channels = {}


async def send_log(guild: discord.Guild, channel_id: int, title: str, description: str, color: discord.Color, fields: dict = None):
    log_channel = guild.get_channel(channel_id)
    if log_channel:
        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
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


# --------------------------------------------------
# ВЕЙС ЖӘНЕ МОДАЛДАР (VOICE & TICKET & CLAN)
# --------------------------------------------------
class RenameVoiceModal(Modal, title="Переименовать канал"):
    new_name = TextInput(label="Новое название канала", placeholder="Введите новое название...", required=True, max_length=100)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.user.voice.channel.edit(name=self.new_name.value)
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
        if not is_ok: return await interaction.response.send_message(result, ephemeral=True)
        new_limit = min((result.user_limit or 0) + 1, 99)
        await result.edit(user_limit=new_limit)
        await interaction.response.send_message(f"➕ Слот увеличен до **{new_limit}**", ephemeral=True)

    @discord.ui.button(emoji="➖", style=discord.ButtonStyle.secondary, custom_id="vc_remove_slot", row=0)
    async def remove_slot(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok: return await interaction.response.send_message(result, ephemeral=True)
        new_limit = max((result.user_limit or len(result.members)) - 1, 1)
        await result.edit(user_limit=new_limit)
        await interaction.response.send_message(f"➖ Слот уменьшен до **{new_limit}**", ephemeral=True)

    @discord.ui.button(emoji="👤", style=discord.ButtonStyle.secondary, custom_id="vc_add_user", row=0)
    async def add_user(self, interaction: discord.Interaction, button: Button):
        is_ok, _ = self.check_owner(interaction)
        if not is_ok: return await interaction.response.send_message(_, ephemeral=True)
        await interaction.response.send_message("Выберите пользователя:", view=UserActionView("add"), ephemeral=True)

    @discord.ui.button(emoji="🔓", style=discord.ButtonStyle.secondary, custom_id="vc_open", row=0)
    async def open_channel(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok: return await interaction.response.send_message(result, ephemeral=True)
        await result.set_permissions(interaction.guild.default_role, connect=True)
        await interaction.response.send_message("🔓 Канал открыт для всех.", ephemeral=True)

    @discord.ui.button(emoji="🔒", style=discord.ButtonStyle.secondary, custom_id="vc_close", row=0)
    async def close_channel(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok: return await interaction.response.send_message(result, ephemeral=True)
        await result.set_permissions(interaction.guild.default_role, connect=False)
        await interaction.response.send_message("🔒 Канал закрыт от посторонних.", ephemeral=True)

    @discord.ui.button(emoji="👥", style=discord.ButtonStyle.secondary, custom_id="vc_block_user", row=1)
    async def block_user(self, interaction: discord.Interaction, button: Button):
        is_ok, _ = self.check_owner(interaction)
        if not is_ok: return await interaction.response.send_message(_, ephemeral=True)
        await interaction.response.send_message("Выберите пользователя для блокировки:", view=UserActionView("block"), ephemeral=True)

    @discord.ui.button(emoji="👑", style=discord.ButtonStyle.secondary, custom_id="vc_transfer", row=1)
    async def transfer_owner(self, interaction: discord.Interaction, button: Button):
        is_ok, _ = self.check_owner(interaction)
        if not is_ok: return await interaction.response.send_message(_, ephemeral=True)
        await interaction.response.send_message("Выберите нового владельца:", view=UserActionView("transfer"), ephemeral=True)

    @discord.ui.button(emoji="🙈", style=discord.ButtonStyle.secondary, custom_id="vc_hide", row=1)
    async def hide_channel(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok: return await interaction.response.send_message(result, ephemeral=True)
        await result.set_permissions(interaction.guild.default_role, view_channel=False)
        await interaction.response.send_message("🙈 Канал скрыт.", ephemeral=True)

    @discord.ui.button(emoji="👁️", style=discord.ButtonStyle.secondary, custom_id="vc_show", row=1)
    async def show_channel(self, interaction: discord.Interaction, button: Button):
        is_ok, result = self.check_owner(interaction)
        if not is_ok: return await interaction.response.send_message(result, ephemeral=True)
        await result.set_permissions(interaction.guild.default_role, view_channel=True)
        await interaction.response.send_message("👁️ Канал виден всем.", ephemeral=True)

    @discord.ui.button(emoji="✏️", style=discord.ButtonStyle.secondary, custom_id="vc_rename", row=2)
    async def rename_channel(self, interaction: discord.Interaction, button: Button):
        is_ok, _ = self.check_owner(interaction)
        if not is_ok: return await interaction.response.send_message(_, ephemeral=True)
        await interaction.response.send_modal(RenameVoiceModal())

    @discord.ui.button(emoji="🚫", style=discord.ButtonStyle.secondary, custom_id="vc_kick_user", row=2)
    async def kick_user_btn(self, interaction: discord.Interaction, button: Button):
        is_ok, _ = self.check_owner(interaction)
        if not is_ok: return await interaction.response.send_message(_, ephemeral=True)
        await interaction.response.send_message("Выберите кого выгнать:", view=UserActionView("block"), ephemeral=True)


class FaceitVerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Верифицироваться", emoji="✅", style=discord.ButtonStyle.success, url="https://www.faceit.com"))

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
        await interaction.response.send_message("🔄 Уровень успешно обновлен!", ephemeral=True)

    @discord.ui.button(label="Сбросить профиль", emoji="🛑", style=discord.ButtonStyle.danger, custom_id="faceit_reset_btn")
    async def reset_button(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        if user_id in verified_users:
            del verified_users[user_id]
            await interaction.response.send_message("🛑 Профиль сброшен.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Профиль не найден.", ephemeral=True)


class TicketControlView(View):
    def __init__(self, ticket_type: str = "general"):
        super().__init__(timeout=None)
        self.ticket_type = ticket_type

    @discord.ui.button(label="Взяться", style=discord.ButtonStyle.success, custom_id="ticket_take_btn_alash")
    async def take_button(self, interaction: discord.Interaction, button: Button):
        if not has_staff_permission(interaction.user, interaction.channel.name):
            return await interaction.response.send_message("❌ У вас нет прав!", ephemeral=True)
        await interaction.response.defer()
        await interaction.followup.send(f"**{interaction.user.mention}** взял(а)ся за тикет!")
        log_id = GIRL_LOG_CHANNEL_ID if "девушка" in interaction.channel.name else MEDIA_LOG_CHANNEL_ID if "медиа" in interaction.channel.name else TICKET_LOG_CHANNEL_ID
        await send_log(interaction.guild, log_id, "✋ Тикет взят", f"{interaction.user.mention} взял тикет {interaction.channel.mention}", discord.Color.blue())

    @discord.ui.button(label="Взять на рассмотрение", style=discord.ButtonStyle.primary, custom_id="ticket_review_btn_alash")
    async def review_button(self, interaction: discord.Interaction, button: Button):
        if not has_staff_permission(interaction.user, interaction.channel.name):
            return await interaction.response.send_message("❌ У вас нет прав!", ephemeral=True)
        await interaction.response.defer()
        await interaction.followup.send(f"**{interaction.user.mention}** взял тикет на рассмотрение.")
        log_id = GIRL_LOG_CHANNEL_ID if "девушка" in interaction.channel.name else MEDIA_LOG_CHANNEL_ID if "медиа" in interaction.channel.name else TICKET_LOG_CHANNEL_ID
        await send_log(interaction.guild, log_id, "🔍 На рассмотрении", f"{interaction.user.mention} перевел тикет на рассмотрение", discord.Color.orange())

    @discord.ui.button(label="Закрыть тикет", style=discord.ButtonStyle.danger, custom_id="ticket_close_btn_alash")
    async def close_button(self, interaction: discord.Interaction, button: Button):
        if not has_staff_permission(interaction.user, interaction.channel.name):
            return await interaction.response.send_message("❌ У вас нет прав!", ephemeral=True)
        await interaction.response.send_message("***Тикет закрывается...***", ephemeral=False)
        log_id = GIRL_LOG_CHANNEL_ID if "девушка" in interaction.channel.name else MEDIA_LOG_CHANNEL_ID if "медиа" in interaction.channel.name else TICKET_LOG_CHANNEL_ID
        await send_log(interaction.guild, log_id, "🔒 Тикет закрыт", f"Закрыл: {interaction.user.mention}", discord.Color.red())
        await asyncio.sleep(3)
        await interaction.channel.delete(reason="Тикет закрыт")


class GirlTicketMainView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Получить роль девушка", emoji="🌸", style=discord.ButtonStyle.secondary, custom_id="open_girl_ticket_btn_alash")
    async def open_girl_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user
        ch_name = f"девушка-{user.name}"
        if discord.utils.get(guild.text_channels, name=ch_name):
            return await interaction.followup.send("У вас уже открыт тикет!", ephemeral=True)
        
        overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False), user: discord.PermissionOverwrite(read_messages=True, send_messages=True), guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        pings = [guild.get_role(r).mention for r in GIRL_STAFF_ROLE_IDS if guild.get_role(r)]
        for r_id in GIRL_STAFF_ROLE_IDS:
            if guild.get_role(r_id): overwrites[guild.get_role(r_id)] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        t_channel = await guild.create_text_channel(name=ch_name, category=interaction.channel.category, overwrites=overwrites)
        embed = discord.Embed(description="**🌸 Заявка на роль Девушки**\nОжидайте ответа модераторов.", color=discord.Color.from_rgb(255, 105, 180))
        embed.add_field(name="• Пользователь", value=user.mention)
        await t_channel.send(content=f"{user.mention} " + " ".join(pings), embed=embed, view=TicketControlView("girl"))
        await send_log(guild, GIRL_LOG_CHANNEL_ID, "🌸 Новый тикет (Девушка)", f"{user.mention} открыл тикет: {t_channel.mention}", discord.Color.from_rgb(255, 105, 180))
        await interaction.followup.send(f"Ваш тикет создан: {t_channel.mention}", ephemeral=True)


class TicketSelectView(View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(placeholder="Выберите категорию...", options=[
        discord.SelectOption(label="Жалоба на игроков", value="Жалоба на игроков"),
        discord.SelectOption(label="Вопросы по серверу", value="Вопросы по серверу"),
        discord.SelectOption(label="Проблемы с верификацией", value="Проблемы с верификацией"),
        discord.SelectOption(label="Технические неполадки", value="Баги и неполадки")
    ])
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user
        cat_sel = select.values[0]
        ch_name = f"заявление-{user.name}"
        if discord.utils.get(guild.text_channels, name=ch_name):
            return await interaction.followup.send("У вас уже открыт тикет!", ephemeral=True)

        overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False), user: discord.PermissionOverwrite(read_messages=True, send_messages=True), guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        pings = [guild.get_role(r).mention for r in STAFF_ROLE_IDS if guild.get_role(r)]
        for r_id in STAFF_ROLE_IDS:
            if guild.get_role(r_id): overwrites[guild.get_role(r_id)] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        t_channel = await guild.create_text_channel(name=ch_name, category=interaction.channel.category, overwrites=overwrites)
        embed = discord.Embed(description="**Система поддержки ALASH PROJECT KZ**\nОпишите вашу ситуацию.", color=discord.Color.from_rgb(57, 255, 20))
        embed.add_field(name="• Пользователь", value=user.mention)
        embed.add_field(name="• Категория", value=cat_sel)
        await t_channel.send(content=f"{user.mention} " + " ".join(pings), embed=embed, view=TicketControlView("general"))
        await send_log(guild, TICKET_LOG_CHANNEL_ID, "📩 Новый тикет", f"{user.mention} открыл тикет: {t_channel.mention}", discord.Color.green(), {"Категория": cat_sel})
        await interaction.followup.send(f"Тикет создан: {t_channel.mention}", ephemeral=True)


class TicketMainView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Открыть тикет", style=discord.ButtonStyle.secondary, custom_id="open_ticket_main_btn_alash")
    async def open_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Выберите категорию:", view=TicketSelectView(), ephemeral=True)


class MediaApplicationModal(Modal, title="Подать заявку на Медиа"):
    game_nick = TextInput(label="Ваш ник в игре", required=True, max_length=50)
    tiktok_link = TextInput(label="Ссылка на TikTok / Канал", required=True, max_length=150)
    steam_id = TextInput(label="Ваш steam ID", style=discord.TextStyle.paragraph, required=True, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user
        ch_name = f"медиа-{user.name}"
        if discord.utils.get(guild.text_channels, name=ch_name):
            return await interaction.followup.send("У вас уже есть медиа тикет!", ephemeral=True)

        overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False), user: discord.PermissionOverwrite(read_messages=True, send_messages=True), guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        pings = [guild.get_role(r).mention for r in MEDIA_STAFF_ROLE_IDS if guild.get_role(r)]
        for r_id in MEDIA_STAFF_ROLE_IDS:
            if guild.get_role(r_id): overwrites[guild.get_role(r_id)] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        t_channel = await guild.create_text_channel(name=ch_name, category=interaction.channel.category, overwrites=overwrites)
        embed = discord.Embed(title="🎬 Заявка на Медиа", color=discord.Color.red())
        embed.add_field(name="• Пользователь", value=user.mention)
        embed.add_field(name="• Ник", value=self.game_nick.value)
        embed.add_field(name="• Канал", value=self.tiktok_link.value)
        embed.add_field(name="• Steam ID", value=self.steam_id.value)
        embed.set_thumbnail(url=user.display_avatar.url)
        await t_channel.send(content=f"{user.mention} " + " ".join(pings), embed=embed, view=TicketControlView("media"))
        await send_log(guild, MEDIA_LOG_CHANNEL_ID, "🎬 Новая заявка на Медиа", f"{user.mention} подал заявку: {t_channel.mention}", discord.Color.red())
        await interaction.followup.send(f"Медиа тикет создан: {t_channel.mention}", ephemeral=True)


class MediaMainView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Подать заявку", style=discord.ButtonStyle.secondary, custom_id="open_media_modal_btn_alash")
    async def apply_media_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(MediaApplicationModal())


# --- КЛАНДАР ЖҮЙЕСІ ---
class CreateClanModal(Modal, title="Создание клана"):
    clan_name = TextInput(label="Название клана", placeholder="Введите название...", required=True, max_length=50)
    clan_tag = TextInput(label="Тег клана", placeholder="Введите тег...", required=True, max_length=10)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"✅ Клан **{self.clan_name.value}** с тегом **[{self.clan_tag.value}]** успешно создан!", ephemeral=True)


class ClanPanelView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Создать клан", style=discord.ButtonStyle.primary, custom_id="create_clan_btn_alash")
    async def create_clan(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CreateClanModal())

    @discord.ui.button(label="Рейтинг кланов", style=discord.ButtonStyle.secondary, custom_id="clan_rating_btn_alash")
    async def clan_rating(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🏆 Рейтинг кланов пуст.", ephemeral=True)

    @discord.ui.button(label="Мой клан", style=discord.ButtonStyle.secondary, custom_id="my_clan_btn_alash")
    async def my_clan(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🛡️ У вас пока нет клана.", ephemeral=True)


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
        self.add_view(ClanPanelView())

bot = MyBot()


# --------------------------------------------------
# СОБЫТИЯ ЖӘНЕ КОМАНДАЛАР
# --------------------------------------------------
@bot.event
async def on_member_join(member):
    role = member.guild.get_role(AUTO_ROLE_ID)
    if role:
        try: await member.add_roles(role, reason="Авто-роль")
        except: pass
    w_channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if w_channel:
        embed = discord.Embed(description=f"Добро пожаловать на сервер, {member.mention}!", color=discord.Color.from_rgb(255, 50, 50))
        embed.set_image(url=member.display_avatar.url)
        await w_channel.send(content=f"Приветствую тебя в нашем дискорд канале, {member.mention}!", embed=embed)


@bot.event
async def on_message(message):
    if message.author.bot: return
    uid = message.author.id
    if uid not in user_levels: user_levels[uid] = {"exp": 0, "level": 1}
    user_levels[uid]["exp"] += 20
    if user_levels[uid]["exp"] >= user_levels[uid]["level"] * 100:
        user_levels[uid]["level"] += 1
        l_ch = message.guild.get_channel(LEVEL_CHANNEL_ID)
        if l_ch: await l_ch.send(f"Поздравляем {message.author.mention}! Ты достиг {user_levels[uid]['level']} уровня!")
    await bot.process_commands(message)


@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and "создать войс" in after.channel.name.lower():
        v_ch = await member.guild.create_voice_channel(name=f"Комната {member.name}", category=after.channel.category)
        await v_ch.set_permissions(member, connect=True, speak=True, manage_channels=True)
        temp_voice_channels[v_ch.id] = member.id
        await member.move_to(v_ch)
    if before.channel and before.channel.id in temp_voice_channels:
        if len(before.channel.members) == 0:
            del temp_voice_channels[before.channel.id]
            await before.channel.delete()


@bot.command()
async def send_verification(ctx):
    embed = discord.Embed(
        title="<a:15770animatedarrowyellow:1503049767016595586> FACEIT Верификация",
        description=(
            "Нажмите кнопку ниже, чтобы пройти верификацию.\n\n"
            "<a:a_pink_dot:1503133833548271646> Проверка Discord\n"
            "<a:a_pink_dot:1503133833548271646> Проверка профиля FACEIT\n"
            "<a:a_pink_dot:1503133833548271646> Проверка привязанного Steam для CS2\n"
            "<a:a_pink_dot:1503133833548271646> Определение FACEIT Level 1–10\n"
            "<a:a_pink_dot:1503133833548271646> Защита от повторной привязки аккаунта\n\n"
            "После успешной проверки бот автоматически выдаст роль верификации и роль вашего FACEIT Level.\n"
            "**ALASH PROJECT KZ**"
        ),
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=FaceitVerifyView())


@bot.command()
async def send_voice_panel(ctx):
    embed = discord.Embed(description="# **Управление приватной комнатой**\n\n➕ • Добавить слот\n👤 • Изменить слоты\n🔓 • Открыть канал\n👥 • Добавить пользователя\n🙈 • Скрыть канал\n✏️ • Переименовать канал\n\n➖ • Убрать слот\n👑 • Передать канал\n🔒 • Закрыть канал\n🚫 • Выгнать пользователя\n👁️ • Показать канал\n\n*Кнопки активны в вашем войсе.*", color=discord.Color.dark_grey())
    await ctx.send(embed=embed, view=VoiceControlPanel())


@bot.command()
async def send_girl_ticket(ctx):
    file = await get_discord_file_from_url(GIRL_BANNER_URL, "banner_girl.png")
    if file:
        img_embed = discord.Embed(color=discord.Color.from_rgb(255, 105, 180)).set_image(url="attachment://banner_girl.png")
        await ctx.send(file=file, embed=img_embed)
    text_embed = discord.Embed(description="<:18690member:1503151722611347586> **Роль Девушка**\n\n<a:a_pink_dot:1503133833548271646> Нажмите кнопку ниже для создания тикета.", color=discord.Color.from_rgb(255, 105, 180))
    await ctx.send(embed=text_embed, view=GirlTicketMainView())


@bot.command()
async def send_ticket(ctx):
    file = await get_discord_file_from_url(TICKET_BANNER_URL, "banner.png")
    if file:
        img_embed = discord.Embed(color=discord.Color.from_rgb(57, 255, 20)).set_image(url="attachment://banner.png")
        await ctx.send(file=file, embed=img_embed)
    text_embed = discord.Embed(description="<:18690member:1503151722611347586> **Система поддержки ALASH PROJECT KZ**\n\n<a:15770animatedarrowyellow:1503049767016595586> **Возникли вопросы или проблемы? Опишите ситуацию**", color=discord.Color.from_rgb(57, 255, 20))
    await ctx.send(embed=text_embed, view=TicketMainView())


@bot.command()
async def send_media(ctx):
    file = await get_discord_file_from_url(MEDIA_BANNER_URL, "banner_media.png")
    if file:
        img_embed = discord.Embed(color=discord.Color.from_rgb(180, 0, 0)).set_image(url="attachment://banner_media.png")
        await ctx.send(file=file, embed=img_embed)
    text_embed = discord.Embed(description="<a:a_pink_dot:1503133833548271646> Наш проект готов к сотрудничеству с медиа игроками.\n\n<a:15770animatedarrowyellow:1503049767016595586> **Что вы получите**\n<a:a_pink_dot:1503133833548271646> Роль <@&{MEDIA_ROLE_ID}>".format(MEDIA_ROLE_ID=MEDIA_ROLE_ID), color=discord.Color.from_rgb(180, 0, 0))
    await ctx.send(embed=text_embed, view=MediaMainView())


@bot.command()
async def send_clan(ctx):
    embed = discord.Embed(
        title="<a:15770animatedarrowyellow:1503049767016595586> Клановые войны",
        description=(
            "Создай клан, собери команду и бросай вызов другим кланам в матчах 5v5\n\n"
            "<a:15770animatedarrowyellow:1503049767016595586> **Как начать**\n"
            "<a:a_pink_dot:1503133833548271646> Нажми \"Создать клан\" и введи название и тег\n"
            "<a:a_pink_dot:1503133833548271646> Пригласи минимум 4 участников через \"Мой клан\"\n"
            "<a:a_pink_dot:1503133833548271646> Бросай вызовы через меню управления кланом\n\n"
            "<a:15770animatedarrowyellow:1503049767016595586> **Правила**\n"
            "<a:a_pink_dot:1503133833548271646> Минимум 5 участников для участия в войнах\n"
            "<a:a_pink_dot:1503133833548271646> Cooldown между вызовами одному клану — 2 ч.\n"
            "<a:a_pink_dot:1503133833548271646> Если клан не собрал 5 игроков за 5 мин до матча — NO-SHOW\n"
            "<a:a_pink_dot:1503133833548271646> Тег клана автоматически добавляется к нику каждого участника\n\n"
            "**Alash project kz**"
        ),
        color=discord.Color.from_rgb(180, 0, 0)
    )
    embed.set_footer(text="alash-project.kz")
    await ctx.send(embed=embed, view=ClanPanelView())


bot.run(os.getenv("DISCORD_TOKEN"))
