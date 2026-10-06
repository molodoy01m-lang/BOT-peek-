import os
import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput
from flask import Flask
from threading import Thread

# Web-server (Render хостинги 24/7 уктабашы үчүн)
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

# Администрация/модератор ролдорунун ID-лери:
STAFF_ROLE_IDS = [
    1554889319574143088,
    1554889058163888188,
    1532841516735795241
]

# Канал для получения заявок на Медиа (Укажите ID вашего канала)
MEDIA_LOG_CHANNEL_ID = 123456789012345678 
# ID роли Медиа (Укажите ID вашей роли)
MEDIA_ROLE_ID = 123456789012345678

# --------------------------------------------------
# 1. ТИКЕТ ИЧИНДЕГИ БАШКАРУУ БАТЫРМАЛАРЫ
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
# 2. КЫЗДАРГА АРНАЛГАН ТИКЕТ
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
# 3. КӘДҮМКИ ТИКЕТТЕР
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
# 4. МЕДИА АНКЕТАСЫ ЖАНА МОДАЛДЫК ТЕРЕЗЕ
# --------------------------------------------------

class MediaApplicationModal(Modal, title="Подать заявку"):
    game_nick = TextInput(
        label="Ваш ник в игре",
        placeholder="Введите игровой ник...",
        required=True,
        max_length=50
    )
    tiktok_link = TextInput(
        label="Ваш тик ток",
        placeholder="Ссылка на аккаунт",
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
        await interaction.response.send_message("Ваша заявка успешно отправлена!", ephemeral=True)

        log_channel = interaction.guild.get_channel(MEDIA_LOG_CHANNEL_ID)

        embed = discord.Embed(
            title="📥 Новая заявка на Медиа!",
            color=discord.Color.red()
        )
        embed.add_field(name="Отправитель", value=interaction.user.mention, inline=False)
        embed.add_field(name="Ваш ник в игре", value=self.game_nick.value, inline=False)
        embed.add_field(name="Ваш тик ток", value=self.tiktok_link.value, inline=False)
        embed.add_field(name="Ваш steam ID", value=self.steam_id.value, inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        if log_channel:
            await log_channel.send(embed=embed)


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


# --------------------------------------------------
# 5. БОТТУ БАПТОО ЖАНА КОШУУ
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
        await ctx.send(file=file, embed=embed, view=TicketMainView())
    else:
        await ctx.send(embed=main_embed, view=TicketMainView())


@bot.command()
async def send_media(ctx):
    embed = discord.Embed(
        description=(
            "• Наш проект готов к сотрудничеству с вами как с медиа игроком (TikTok стримы/видео).\n\n"
            "• Мы предлагаем партнерство, где ваша аудитория и активность помогают продвижению проекта.\n\n"
            "• Мы уверены, что совместно сможем создавать качественный и интересный контент.\n\n"
            "❯ **Что вы получите**\n"
            "• Привилегию на сервере \"Медиа\"\n"
            f"• Роль в Discord <@&{MEDIA_ROLE_ID}>\n"
            "• В привилегию \"MEDIA\" входит весь функционал привилегии \"ALASH\""
        ),
        color=discord.Color.from_rgb(180, 0, 0)
    )

    media_banner_path = "banner_media.png"

    if os.path.exists(media_banner_path):
        file = discord.File(media_banner_path, filename="banner_media.png")
        embed.set_image(url="attachment://banner_media.png")
        await ctx.send(file=file, embed=embed, view=MediaMainView())
    else:
        await ctx.send(embed=embed, view=MediaMainView())


bot.run(os.getenv("DISCORD_TOKEN"))
