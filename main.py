
# BOT PRONTO - CONFIGURE APENAS TOKEN DISCORD E GITHUB

import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
import datetime
import chat_exporter
import os
import requests
import base64
import uuid

TOKEN = os.getenv("TOKEN")

STAFF_ROLE_ID = 1475253235437797508
CATEGORIA_ID = 1429081867965173800
CANAL_AVALIACAO_ID = 1475253873617666271

GITHUB_TOKEN = "COLOQUE_SEU_GITHUB_TOKEN_AQUI"
GITHUB_USER = "COLOQUE_SEU_USUARIO_GITHUB"
REPO_NAME = "transcripts"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

tickets = {}

def formatar_duracao(delta):
    segundos = int(delta.total_seconds())
    if segundos < 60:
        return f"{segundos} segundos"
    elif segundos < 3600:
        return f"{segundos // 60} minutos"
    else:
        return f"{segundos // 3600} horas"

def upload_github(html_content):
    filename = f"{uuid.uuid4()}.html"
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{filename}"

    content_encoded = base64.b64encode(html_content.encode()).decode()

    data = {
        "message": "Novo transcript",
        "content": content_encoded
    }

    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    response = requests.put(url, json=data, headers=headers)

    if response.status_code == 201:
        return f"https://{GITHUB_USER}.github.io/{REPO_NAME}/{filename}"
    return None

class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Recrutamento", emoji="📋"),
            discord.SelectOption(label="Dúvida", emoji="❓"),
            discord.SelectOption(label="Denúncia", emoji="🚨"),
            discord.SelectOption(label="Outro", emoji="📌"),
        ]
        super().__init__(placeholder="Escolha uma opção...", options=options)

    async def callback(self, interaction: discord.Interaction):
        categoria = bot.get_channel(CATEGORIA_ID)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True),
            interaction.guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True)
        }

        canal = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=categoria,
            overwrites=overwrites
        )

        tickets[canal.id] = {
            "autor": interaction.user,
            "inicio": datetime.datetime.utcnow(),
            "assumiu": None
        }

        embed = discord.Embed(
            title="🎫 Ticket Aberto",
            description=f"Olá {interaction.user.mention}\n\nDescreva seu problema sem marcar a staff.",
            color=discord.Color.blue()
        )

        await canal.send(embed=embed, view=TicketButtons())
        await interaction.response.send_message("Ticket criado!", ephemeral=True)

class TicketButtons(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Assumir Ticket", style=discord.ButtonStyle.primary)
    async def assumir(self, interaction: discord.Interaction, button: Button):
        if STAFF_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        tickets[interaction.channel.id]["assumiu"] = interaction.user
        await interaction.response.send_message(f"Assumido por {interaction.user.mention}")

    @discord.ui.button(label="Fechar Ticket", style=discord.ButtonStyle.danger)
    async def fechar(self, interaction: discord.Interaction, button: Button):
        if STAFF_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        await interaction.response.send_modal(FecharModal())

class FecharModal(Modal, title="Finalizar Ticket"):
    motivo = TextInput(label="Motivo do fechamento", style=discord.TextStyle.long)

    async def on_submit(self, interaction: discord.Interaction):
        data = tickets.get(interaction.channel.id)
        fim = datetime.datetime.utcnow()
        duracao = formatar_duracao(fim - data["inicio"])

        autor = data["autor"]
        staff = data["assumiu"]

        transcript = await chat_exporter.export(
            interaction.channel,
            guild=interaction.guild,
            bot=bot
        )

        link = upload_github(transcript)

        embed_dm = discord.Embed(
            title="📩 Atendimento Finalizado",
            description=f"👮 Atendido por: {staff.mention if staff else 'Não definido'}\n\n📝 Motivo:\n{self.motivo.value}\n\n⏱ Duração: {duracao}",
            color=discord.Color.blue()
        )

        view = AvaliacaoView(staff, autor, duracao, link)
        await autor.send(embed=embed_dm, view=view)
        await interaction.channel.delete()

class AvaliacaoView(View):
    def __init__(self, staff, cliente, duracao, link):
        super().__init__(timeout=None)
        self.staff = staff
        self.cliente = cliente
        self.duracao = duracao
        self.link = link

    async def enviar(self, interaction, nota):
        canal = bot.get_channel(CANAL_AVALIACAO_ID)

        embed = discord.Embed(
            title="⭐ Nova Avaliação",
            description=f"👤 Cliente: {self.cliente.mention}\n👮 Staff: {self.staff.mention if self.staff else 'Não definido'}\n⭐ Avaliação: {nota}\n\n⏱ Duração: {self.duracao}",
            color=discord.Color.gold()
        )

        await canal.send(embed=embed)
        await interaction.response.send_message("Avaliação enviada!", ephemeral=True)

    @discord.ui.button(label="Péssimo", style=discord.ButtonStyle.danger)
    async def pessimo(self, interaction: discord.Interaction, button: Button):
        await self.enviar(interaction, "Péssimo")

    @discord.ui.button(label="Ruim", style=discord.ButtonStyle.danger)
    async def ruim(self, interaction: discord.Interaction, button: Button):
        await self.enviar(interaction, "Ruim")

    @discord.ui.button(label="Médio", style=discord.ButtonStyle.secondary)
    async def medio(self, interaction: discord.Interaction, button: Button):
        await self.enviar(interaction, "Médio")

    @discord.ui.button(label="Bom", style=discord.ButtonStyle.primary)
    async def bom(self, interaction: discord.Interaction, button: Button):
        await self.enviar(interaction, "Bom")

    @discord.ui.button(label="Excelente", style=discord.ButtonStyle.success)
    async def excelente(self, interaction: discord.Interaction, button: Button):
        await self.enviar(interaction, "Excelente")

    @discord.ui.button(label="Script", style=discord.ButtonStyle.secondary)
    async def script(self, interaction: discord.Interaction, button: Button):
        if self.link:
            await interaction.response.send_message(self.link, ephemeral=True)
        else:
            await interaction.response.send_message("Transcript não disponível.", ephemeral=True)

class TicketPanel(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

@bot.command()
async def painel(ctx):
    embed = discord.Embed(
        title="🎟 Sistema de Tickets",
        description="Selecione uma opção abaixo:",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=TicketPanel())

bot.run(TOKEN)
