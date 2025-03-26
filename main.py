import discord
import os
import asyncio
import random
from discord.ext import commands
import math
from datetime import datetime
import requests
import json
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GIT_TOKEN = os.getenv("GIT_TOKEN")
BASE_URL = "https://raw.githubusercontent.com/Darndestt/vets/main/vetali/"
REPO_URL = "https://api.github.com/repos/Darndestt/vets/contents/vetali"
CACHE_FILE = "cache.json"
PONTOS_FILE = "pontos.json"

jogo_ativo = False
tempo_intervalo = 10
pausado = False
permitir_pausa = False
pausa_anunciada = False
pausa_task = None
resposta_correta = None
pontos = {}
pontuacao_total = {}
erros = 0
jogador_iniciador = None

def carregar_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as file:
            return json.load(file)
    return []

def salvar_cache(imagens):
    try:
        with open(CACHE_FILE, "w") as file:
            json.dump(imagens, file)
        print("Cache salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao salvar cache: {e}")

def carregar_pontos():
    if os.path.exists(PONTOS_FILE) and os.path.getsize(PONTOS_FILE) > 0:
        with open(PONTOS_FILE, "r") as file:
            return json.load(file)
    return {}

def salvar_pontos():
    try:
        with open(PONTOS_FILE, "w") as file:
            json.dump(pontuacao_total, file)
        print("Cache de pontos salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao salvar cache: {e}")

pontuacao_total = carregar_pontos()

def verificar_limite_github():
    headers = {
        "Authorization": f"token {GIT_TOKEN}"
    }
    response = requests.get("https://api.github.com/rate_limit", headers=headers)

    if response.status_code == 200:
        data = response.json()
        remaining = data["rate"]["remaining"]
        reset_time = datetime.fromtimestamp(data["rate"]["reset"]).strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"Limite restante: {remaining}")
        print(f"Reset em: {reset_time}")
        return remaining
    else:
        print(f"Erro ao verificar limite: {response.status_code} - {response.text}")
        return 0

def obter_imagens():
    if verificar_limite_github() == 0:
        print("Limite de requisições atingido!")
        return []

    imagens = carregar_cache()
    if imagens:
        return imagens
        
    headers = {
        "Authorization": f"token {GIT_TOKEN}"
    }
    response = requests.get(REPO_URL, headers=headers)
    
    if response.status_code != 200:
        print(f"Erro ao buscar imagens: {response.status_code} - {response.text}")
        return []

    try:
        arquivos = response.json()
        
        if not isinstance(arquivos, list):
            print("Erro: A resposta da API não é uma lista.")
            return []
        
        imagens = [arquivo['name'].replace('.png', '') for arquivo in arquivos if isinstance(arquivo, dict) and 'name' in arquivo and arquivo['name'].endswith('.png')]
        
        salvar_cache(imagens)
        return imagens
    except Exception as e:
        print(f"Erro ao processar resposta da API: {e}")
        return []

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=".", intents=intents)

@bot.event
async def on_message(message):
    global jogo_ativo

    if message.author == bot.user:
        return
    
    if jogo_ativo and (message.content.startswith(".ver") or message.content.startswith(".comandos")):
        await message.channel.send(embed=discord.Embed(
            title="🚫 Comando Bloqueado",
            description="Este comando não pode ser usado durante a partida.",
            color=discord.Color.red()
        ))
        return

    imagens = obter_imagens()

    if message.content.strip() == ".ver lista":
        paginas = math.ceil(len(imagens) / 10)
        pagina_atual = 1
        imagens_pagina = imagens[(pagina_atual - 1) * 10 : pagina_atual * 10]

        embed = discord.Embed(
            title="Lista de palavras",
            description="Aqui está a lista de palavras disponíveis. Use o comando `.ver <nome>` para visualizar o desenho de cada uma.",
            color=discord.Color.random(),
        )

        embed.add_field(
            name=f"Página {pagina_atual}/{paginas}", 
            value="\n".join(imagens_pagina), 
            inline=False
        )

        msg = await message.channel.send(embed=embed)

        await msg.add_reaction("⬅️")
        await msg.add_reaction("➡️")

        def check(reaction, user):
            return user == message.author and str(reaction.emoji) in ["⬅️", "➡️"]

        try:
            while True:
                reaction, user = await asyncio.wait_for(bot.wait_for("reaction_add", check=check), timeout=60.0)

                if str(reaction.emoji) == "➡️" and pagina_atual < paginas:
                    pagina_atual += 1
                elif str(reaction.emoji) == "⬅️" and pagina_atual > 1:
                    pagina_atual -= 1

                imagens_pagina = imagens[(pagina_atual - 1) * 10 : pagina_atual * 10]
                embed = discord.Embed(
                    title="Lista de palavras",
                    description="Aqui está a lista de palavras disponíveis.",
                    color=discord.Color.random(),
                )

                embed.add_field(
                    name=f"Página {pagina_atual}/{paginas}",
                    value="\n".join(imagens_pagina),
                    inline=False,
                )

                await msg.edit(embed=embed)
                await msg.remove_reaction(reaction, user)
        
        except asyncio.TimeoutError:
            await msg.clear_reactions()
            return

    if message.content.startswith(".ver"):
        partes = message.content.split(".ver", 1)
        nome_da_imagem = partes[1].strip().lower() if len(partes) > 1 else ""

        if not nome_da_imagem:
            await message.channel.send(embed=discord.Embed(
                title="ℹ️ Informações",
                description="Digite `.ver <nome>` para ver um desenho!",
                color=discord.Color.orange()
            ))
            return

        if nome_da_imagem not in imagens:
            await message.channel.send(embed=discord.Embed(
                title="❌ Erro",
                description=f"{nome_da_imagem} não foi encontrado.",
                color=discord.Color.red()
            ))
            return

        nome_da_imagem_url = nome_da_imagem.replace(" ", "%20")
        url_imagem = f"{BASE_URL}{nome_da_imagem_url}.png"

        embed = discord.Embed(
            title=f"Desenho: {nome_da_imagem.replace('%20', ' ')}",
            color=discord.Color.random(),
            description="Feito por **crackhusband**!",
        )
        embed.set_image(url=url_imagem)
        await message.channel.send(embed=embed)

    await bot.process_commands(message)

@bot.command()
async def play(ctx):
    global jogo_ativo, pausado, resposta_correta, pontos, pontuacao_total, erros, jogador_iniciador, permitir_pausa, tempo_intervalo

    if jogo_ativo:
        await ctx.send(embed=discord.Embed(
            title="🎮 Partida em andamento",
            description="Uma partida já está em andamento!",
            color=discord.Color.red()
        ))
        return

    pontos = {}
    erros = 0
    jogo_ativo = True
    jogador_iniciador = ctx.author

    pontos[ctx.author] = 0
    
    await ctx.send(embed=discord.Embed(
        title="🎮 Partida inicializada",
        description="A partida começará em 10 segundos...",
        color=discord.Color.green()
    ))
    await asyncio.sleep(10)

    while pausado:
        if not pausa_anunciada:
            await ctx.send(embed=discord.Embed(
                title="⏸️ Jogo Pausado",
                description="O jogo está pausado. Aguarde a retomada.",
                color=discord.Color.orange()
            ))
            pausa_anunciada = True
        await asyncio.sleep(1)

    while tempo_intervalo > 0:
        if pausado:
            await asyncio.sleep(1)
            continue

        await asyncio.sleep(1)
        tempo_intervalo -= 1

    imagens = obter_imagens()
    if not imagens:
        await ctx.send("🚨 Erro ao carregar imagens. Jogo cancelado.")
        jogo_ativo = False
        return

    while jogo_ativo:
        if pausado:
            if not pausa_anunciada:
                await ctx.send(embed=discord.Embed(
                    title="⏸️ Jogo Pausado",
                    description="O jogo está pausado. Aguarde a retomada.",
                    color=discord.Color.orange()
                ))
                pausa_anunciada = True
            await asyncio.sleep(1)
            continue
        else:
            pausa_anunciada = False 

        permitir_pausa = False

        resposta_correta = random.choice(imagens)
        url_imagem = f"{BASE_URL}{resposta_correta.replace(' ', '%20')}.png"

        embed = discord.Embed(
            title="🎨 Adivinhe o desenho!",
            description="Digite a resposta no chat!",
            color=discord.Color.random(),
        )
        embed.set_image(url=url_imagem)

        await ctx.send(embed=embed)

        try:
            msg = await bot.wait_for(
                "message",
                timeout=60.0,
                check=lambda msg: msg.content.lower().strip() == resposta_correta.lower() and msg.author != bot.user
            )

            player = msg.author
            player_id = msg.author.id
            print(f"player_id: {player_id}, Usuário: {player.name}")

            if player not in pontos:
                pontos[player] = 0

            pontos[player] += 2

            if player not in pontuacao_total:
                pontuacao_total[player] = 0

            pontuacao_total[player] += 2

            salvar_pontos()

            await ctx.send(embed=discord.Embed(
                title="✅ Resposta Correta",
                description=f"{player.mention} acertou! A resposta era **{resposta_correta}**.",
                color=discord.Color.green()
            ))

        except asyncio.TimeoutError:
            await ctx.send(embed=discord.Embed(
                title="⏳ Tempo Esgotado",
                description=f"A resposta era **{resposta_correta}**.",
                color=discord.Color.red()
            ))

        for player in pontos:
                if pontos.get(player) is None:
                    pontos[player] = 0

        await ctx.send(embed=discord.Embed(
            title="📊 Pontuação Atual",
             description="\n".join([f"{player.mention}: {pontos[player]} pontos" for player in pontos]),
            color=discord.Color.blue()
        ))

        if erros >= 5:
            vencedor = max(pontos, key=pontos.get, default=None)
            if vencedor and pontos[vencedor] > 0:
                await ctx.send(embed=discord.Embed(
                    title="🏆 Partida Finalizada",
                    description=f"O vencedor foi **{vencedor.mention}** com {pontos[vencedor]} pontos!",
                    color=discord.Color.gold()
                ))
            else:
                await ctx.send(embed=discord.Embed(
                    title="🏆 Partida Finalizada",
                    description="Não houve vencedor.",
                    color=discord.Color.gold()
                ))
            jogo_ativo = False
            pausado = False
            resposta_correta = None
            break

        await ctx.send(embed=discord.Embed(
            title="⌛ Próxima Rodada",
            description="A próxima rodada começará em 10 segundos...",
            color=discord.Color.blue()
        ))

        permitir_pausa = True
        tempo_intervalo = 10

        while tempo_intervalo > 0:
            if pausado:
                await asyncio.sleep(1)
                continue

            await asyncio.sleep(1)
            tempo_intervalo -= 1

@bot.command()
async def pausar(ctx):
    global pausado, jogo_ativo, pausa_anunciada, permitir_pausa, pausa_task
    
    if not jogo_ativo:
        await ctx.send(embed=discord.Embed(
            title="🚫 Erro",
            description="Nenhuma partida em andamento para pausar ou retomar.",
            color=discord.Color.red()
        ))
        return
    
    if not permitir_pausa:
        await ctx.send(embed=discord.Embed(
            title="🚫 Erro",
            description="Você só pode pausar no intervalo entre rodadas!",
            color=discord.Color.red()
        ))
        return
    
    if ctx.author != jogador_iniciador:
        await ctx.send(embed=discord.Embed(
            title="🚫 Erro",
            description="Somente o iniciador do jogo pode pausar ou retomar a partida.",
            color=discord.Color.red()
        ))
        return

    if pausado:
        pausado = False
        pausa_anunciada = False

        if pausa_task is not None:
            pausa_task.cancel()
            pausa_task = None 
        
        await ctx.send(embed=discord.Embed(
            title="▶️ Jogo Retomado",
            description="A partida foi retomada.",
            color=discord.Color.green()
        ))
    else:
        pausado = True
        await ctx.send(embed=discord.Embed(
            title="⏸️ Jogo Pausado",
            description="O jogo foi pausado. Digite `.pausar` para retomar.",
            color=discord.Color.orange()
        ))

        pausa_task = asyncio.create_task(verificar_timeout_pausa(ctx))

async def verificar_timeout_pausa(ctx):
    global pausado, jogo_ativo, pausa_task
    
    await asyncio.sleep(60)
    
    if pausado:
        pausado = False
        pausa_task = None
        await ctx.send(embed=discord.Embed(
            title="⏩ Jogo Retomado Automaticamente",
            description="O jogo foi retomado automaticamente após 1 minuto de pausa.",
            color=discord.Color.green()
        ))

@bot.command()
async def fim(ctx):
    global jogo_ativo, pausado, resposta_correta, pontos, jogador_iniciador

    if not jogo_ativo:
        await ctx.send(embed=discord.Embed(
            title="🚫 Erro",
            description="Nenhuma partida em andamento para encerrar.",
            color=discord.Color.red()
        ))
        return

    if ctx.author != jogador_iniciador:
        await ctx.send(embed=discord.Embed(
            title="🚫 Erro",
            description="Apenas quem iniciou o jogo pode encerrá-lo.",
            color=discord.Color.red()
        ))
        return

    vencedor = max(pontos, key=pontos.get, default=None)
    if vencedor and pontos[vencedor] > 0:
        await ctx.send(embed=discord.Embed(
            title="🏆 Final da Partida",
            description=f"O vencedor foi **{vencedor.mention}** com {pontos[vencedor]} pontos!",
            color=discord.Color.green()
        ))
    else:
        await ctx.send(embed=discord.Embed(
            title="🏆 Final da Partida",
            description="Não houve vencedor.",
            color=discord.Color.green()
        ))

    jogo_ativo = False
    pausado = False
    resposta_correta = None
    erros = 0 
    pontos = {}
    await ctx.send(embed=discord.Embed(
        title="🛑 Partida Encerrada",
        description="A partida foi encerrada.",
        color=discord.Color.red()
    ))

@bot.command()
async def perfil(ctx):
    usuario = ctx.author
    
    pontos_usuario = pontuacao_total.get(usuario, 0)
    if pontos_usuario >= 50000:
        insignia = "🍓 Conquistada!"
        insignia_descricao = "Parabéns! Você acumulou mais de **50.000 pontos** e conquistou esta insígnia!"
    else:
        insignia = "⚪ Ainda não conquistada"
        insignia_descricao = "Acumule **50.000 pontos** para desbloquear esta insígnia!"

    embed = discord.Embed(
        title=f"Perfil de {usuario.display_name}",
        description=f"🎯 **Total de pontos acumulados:** `{pontos_usuario}`",
        color=discord.Color.random()
    )
    
    if usuario.avatar:
        embed.set_thumbnail(url=usuario.avatar.url)

    embed.add_field(name="🏅 Insígnia Especial", value=f"{insignia}\n{insignia_descricao}", inline=False)

    await ctx.send(embed=embed)

@bot.command()
async def comandos(ctx):
    embed = discord.Embed(
        title="Comandos Disponíveis",
        description="Aqui estão os comandos que você pode usar:",
        color=discord.Color.random()
    )
    embed.add_field(name=".play", value="Inicia uma nova partida do jogo.", inline=False)
    embed.add_field(name=".pausar", value="Pausa ou retoma a partida em andamento.", inline=False)
    embed.add_field(name=".fim", value="Encerra a partida atual e exibe o vencedor.", inline=False)
    embed.add_field(name=".ver <nome>", value="Exibe a imagem do desenho correspondente ao nome fornecido.", inline=False)
    embed.add_field(name=".ver lista", value="Exibe uma lista de palavras disponíveis.", inline=False)
    embed.add_field(name=".comandos", value="Exibe este menu de comandos.", inline=False)

    await ctx.send(embed=embed)

bot.run(TOKEN)
