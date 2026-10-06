import os
import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput
from flask import Flask
from threading import Thread

# Web-server (Render хостингында 24/7 эшләү өчен)
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

# Администрация / модератор рольләренең ID-лары:
STAFF_ROLE_IDS = [
    1554889319574143088,
    1554889058163888188,
    1532841516735795241
]

# Медиа лог каналы
MEDIA_LOG_CHANNEL_ID = 1557045586820333649 

# Медиа роленең ID-сы:
MEDIA_ROLE_ID = 1557044911440928961

# --------------------------------------------------
# 1. ТИКЕТ ИЧЕНДӘГЕ БАШКАРУ ТӨЙМӘЛӘРЕ
# --------------------------------------------------

class TicketControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Взяться", style=discord.ButtonStyle.success, custom_id="ticket_take_btn_alash")
    async def take_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await interaction.followup.send(f"**{interaction.user.mention}** взял(а)ся за данный тикет!")

    @discord.ui.button(label="Взять на рассмотрение", style=discord.ButtonStyle.primary, custom_id="ticket_review_btn_alash")
    async def review_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await interaction.followup.send(f"**{interaction.user.mention}** взял(а) тикет на рассмотрение.")

    @discord.ui.button(label="Закрыть тикет", style=discord.ButtonStyle.danger, custom_id="ticket_close_btn_alash")
    async def close_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("***Тикет закрывается и будет удален...***", ephemeral=False)
        await asyncio.sleep(3)
        await interaction.channel.delete(reason=f"Тикет закрыт: {interaction.user.name}")


# --------------------------------------------------
# 2. КЫЗЛАР ӨЧӘН ТИКЕТ
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
        for role_id in STAFF_ROLE_IDS:
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
            view=TicketControlView()
        )

        await interaction.followup.send(f"Ваш тикет создан: {ticket_channel.mention}", ephemeral=True)


# --------------------------------------------------
# 3. ТӘРТИПТЕГЕ ТИКЕТЛАР
# --------------------------------------------------

class TicketSelectView(View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(
        placeholder="Выберите категорию тикета...",
        options=[
            discord.SelectOption(label="Жалоба на игроков или пользователей", value="report_user", description="Пожаловаться на игрока"),
            discord.SelectOption(label="Вопросы по серверу или Discord", value="questions", description="Вопросы по серверу"),
            discord.SelectOption(label="Проблемы с верификацией", value="verification", description="Проблемы с аккаунтом"),
            discord.SelectOption(label="Ошибки, баги и технические неполадки", value="bugs", description="Технические проблемы"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: Select):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user

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
            color=discord.Color.from_rgb(67, 181, 129)
        )
        embed.add_field(name="• Пользователь", value=user.mention, inline=False)
        embed.add_field(name="• Категория", value=f"{select.values[0]}", inline=False)

        await ticket_channel.send(
            content=f"{user.mention} {roles_ping_text}".strip(),
            embed=embed,
            view=TicketControlView()
        )

        await interaction.followup.send(f"Ваш тикет создан: {ticket_channel.mention}", ephemeral=True)


class TicketMainView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Открыть тикет", style=discord.ButtonStyle.primary, custom_id="open_ticket_main_btn_alash")
    async def open_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "Выберите нужную категорию для открытия тикета:",
            view=TicketSelectView(),
            ephemeral=True
        )


# --------------------------------------------------
# 4. МЕДИА АНКЕТАСЫ ЖӘНӘ ТИКЕТ КАНАЛЫН АЧУ
# --------------------------------------------------

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

        # Алдан ачылган тикет бармы-юкмы тикшерү
        existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if existing_channel:
            await interaction.followup.send(f"У вас уже открыт медиа тикет: {existing_channel.mention}", ephemeral=True)
            return

        # Каналга рөхсәтләр (Permissions)
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

        # Тикет каналын булдыру
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            reason=f"Медиа тикет открыт: {user.name}"
        )

        roles_ping_text = " ".join(valid_roles_to_ping) if valid_roles_to_ping else ""

        # Тикет каналы эчендәге Embed
        embed = discord.Embed(
            title="🎬 Заявка на роль МЕДИА",
            description="Ожидайте ответа от администрации или медиа-кураторов.",
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
            view=TicketControlView()
        )

        # Лог каналына күчермәсен җибәрү
        log_channel = guild.get_channel(MEDIA_LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="📥 Новая заявка на Медиа (Лог)",
                color=discord.Color.red()
            )
            log_embed.add_field(name="Пользователь", value=user.mention, inline=False)
            log_embed.add_field(name="Ник в игре", value=self.game_nick.value, inline=False)
            log_embed.add_field(name="TikTok / Канал", value=self.tiktok_link.value, inline=False)
            log_embed.add_field(name="Steam ID", value=self.steam_id.value, inline=False)
            log_embed.add_field(name="Созданный тикет", value=ticket_channel.mention, inline=False)
            await log_channel.send(embed=log_embed)

        await interaction.followup.send(f"Ваш медиа тикет создан: {ticket_channel.mention}", ephemeral=True)


class MediaMainView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Подать заявку",
        style=discord.ButtonStyle.danger,
        custom_id="open_media_modal_btn_alash"
    )
    async def apply_media_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(MediaApplicationModal())


# --------------------------------------------------
# 5. БОТНЫ СӨЙЛӘҮ ЖӘНӘ ЭШКӘ ҖИБӘРҮ
# --------------------------------------------------

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(TicketMainView())
        self.add_view(GirlTicketMainView())
        self.add_view(TicketControlView())
        self.add_view(MediaMainView())

bot = MyBot()


@bot.command()
async def send_girl_ticket(ctx):
    embed = discord.Embed(
        description=(
            "**❤️ Роль Девушка**\n\n"
            "• Нажмите кнопку ниже, чтобы создать тикет для верификации и получения роли Девушка\n\n"
            "✨ **Информация**\n"
            "• Создайте тикет для верификации\n"
            "• Предоставьте доказательства\n"
            "• Модераторы рассмотрят ваш запрос\n\n"
            "📸 Чтобы получить роль, откройте тикет или обратитесь к администрации сервера."
        ),
        color=discord.Color.from_rgb(255, 105, 180)
    )

    girl_banner_path = "banner_girl.png"

    if os.path.exists(girl_banner_path):
        file = discord.File(girl_banner_path, filename="banner_girl.png")
        embed.set_image(url="attachment://banner_girl.png")
        await ctx.send(file=file, embed=embed, view=GirlTicketMainView())
    else:
        await ctx.send(embed=embed, view=GirlTicketMainView())


@bot.command()
async def send_ticket(ctx):
    main_embed = discord.Embed(
        description=(
            "**Система поддержки ALASH PROJECT KZ**\n\n"
            "**Возникли вопросы, проблемы или нужна помощь? Опишите ситуацию**\n\n"
            "**Что можно оформить через тикет?**\n"
            "• Жалобы на игроков или пользователей.\n"
            "• Вопросы по серверу или Discord.\n"
            "• Проблемы с верификацией.\n"
            "• Ошибки, баги и технические неполадки."
        ),
        color=discord.Color.from_rgb(67, 181, 129)
    )

    banner_path = "banner.png"

    if os.path.exists(banner_path):
        file = discord.File(banner_path, filename="banner.png")
        main_embed.set_image(url="attachment://banner.png")
        await ctx.send(file=file, embed=main_embed, view=TicketMainView())
    else:
        await ctx.send(embed=main_embed, view=TicketMainView())


@bot.command()
async def send_media(ctx):
    embed = discord.Embed(
        description=(
            "**🎬 МЕДИА**\n\n"
            "Клипы, хайлайты, лучшие моменты и контент от игроков.\n\n"
            "Делись своими видео и попади в подборку лучших.\n\n"
            f"❯ **Получи роль:** <@&{MEDIA_ROLE_ID}>\n"
            "• Жми кнопку ниже и подавай заявку!"
        ),
        color=discord.Color.from_rgb(180, 0, 0)
    )

    media_banner_path = "banner_media.png"

    # Сурәт файлы "banner_media.png" исеме белән бот папксында булырга тиеш
    if os.path.exists(media_banner_path):
        file = discord.File(media_banner_path, filename="banner_media.png")
        embed.set_image(url="attachment://banner_media.png")
        await ctx.send(file=file, embed=embed, view=MediaMainView())
    else:
        await ctx.send(embed=embed, view=MediaMainView())


bot.run(os.getenv("DISCORD_TOKEN"))
