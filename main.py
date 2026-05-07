#Olha só, não apaguei nada, então não reclame
import os, sys, subprocess, shutil
import tkinter as tk
from tkinter import filedialog
import questionary
from questionary import Choice, Style
import speech_recognition as sr

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme
#Estou adicionando para um uso interessante
from rich.live import Live
from time import sleep
from rich.align import Align


# Configuração do Tema e Console da Rich
#Estou mudando as cores, quero opinião boa ein
tema_customizado = Theme({
    "info": "italic grey70",
    "warning": "bold gold1",
    "error": "bold indian_red1",
    "success": "bold spring_green3",
    "highlight": "bold magenta"
})
console = Console(theme=tema_customizado)

# Estilização do Questionary
#Mudei o qmark, answer, highlighted, selected, instruction
estilo_menu = Style([
    ('qmark', 'fg:#87ceeb bold'),
    ('question', 'bold'),
    ('answer', 'fg:#00ff7f bold'),
    ('pointer', 'fg:#ff00ff bold'),
    ('highlighted', 'fg:#87ceeb underline'),
    ('selected', 'fg:#00ff7f'),
    ('separator', 'fg:#cc5454'),
    ('instruction', 'fg:#616161 italic')
])

galeria = []
palavrasChaves = []

#Adicionando um tipo de "banner"
def exibir_banner():
    banner = """
    ┏━┓┏━┓┏━┓┏━┓┏┓╻┏━┓╺┳╸┏━╸
    ┗━┓┃╻┃┣━┫┣━┛┃┗┫┃ ┃ ┃ ┣╸ 
    ┗━┛╹┗╹╹ ╹╹  ╹ ╹┗━┛ ╹ ┗━╸
    """

    # Removi o Align.center e o padding lateral exagerado, que eu tinha feito e ninguém viu, só o Bruno mesmo
    painel_banner = Panel(
        banner,
        subtitle="[bold]v1.0 - Sua Galeria Inteligente[/bold]",
        border_style="magenta",
        expand=False,  # Faz o painel se ajustar ao tamanho do texto, não à tela toda. Vai ficar nice demais
        width=50,  # Estou forçando o painel ficar largo o suficiente, pois estava cortando o título ;-;
        padding=(1, 5)  # Padding menor para não empurrar o texto, eu também mexi nisso anteriormente e não ficou legal
    )

    # Imprime direto, sem a função Align.center envolta, para quem não sabe eu também usei align
    console.print(painel_banner)


# Exibe o menu principal e retorna a opção escolhida pelo usuário.
def menuPrincipal():
    exibir_banner()

    painel = Panel.fit(
        "[bold cyan]Bem-vindo ao sistema de organização visual![/bold cyan]\n"
        "Selecione uma das opções abaixo para gerenciar sua galeria.",
        title="[bold magenta]📸 SNAPNOTE - MENU PRINCIPAL[/bold magenta]",
        border_style="magenta",
        padding=(1, 2)
    )
    console.print(painel)

    opcao = questionary.select(
        'O que você deseja fazer?',
        choices=[
            Choice(title="Selecionar imagem e gerar uma anotação.", value=1),
            Choice(title="Exibir anotações.", value=2),
            Choice(title="Buscar imagem pela anotação.", value=3),
            Choice(title="Controle de palavras-chave.", value=4),
            Choice(title="Limpar o terminal.", value=5),
            Choice(title="Finalizar execução", value=6),
        ],
        style=estilo_menu
    ).ask()

    return opcao


# Grava o áudio do microfone, transcreve para texto usando o Google e retorna o resultado.
def gravarAudio():
    reconhecedor = sr.Recognizer()

    with sr.Microphone() as source:
        #Usei status para deixar mais "vivo"? Algo do tipo
        with console.status("\n[info]🎤 Ajustando o ruído de fundo... aguarde um instante.[/info]", spinner="bouncingBall"):
            reconhecedor.adjust_for_ambient_noise(source, duration=0.8)

        console.print("[highlight]🔴 Pode falar! Estou ouvindo...[/highlight]")

        try:
            audio = reconhecedor.listen(source, timeout=5, phrase_time_limit=20)
            #Também usei status
            with console.status("[info]⏳ Processando o áudio...[/info]", spinner="arc"):
                textoTranscrito = reconhecedor.recognize_google(audio, language='pt-BR')
            return textoTranscrito

        except sr.UnknownValueError:
            console.print("[error]❌ Desculpe, o áudio ficou confuso e não foi possível entender.[/error]")
            return None
        except sr.RequestError:
            console.print("[error]❌ Erro de conexão. Verifique sua internet.[/error]")
            return None
        except sr.WaitTimeoutError:
            console.print("[error]❌ Você demorou muito para falar. Operação cancelada.[/error]")
            return None


# Abre o explorador para selecionar uma foto, recebe a anotação (texto ou voz) e salva na galeria.
def adicionarAnotacao():
    console.print("\n[highlight]📸 Vamos adicionar uma nova anotação ao SnapNote![/highlight]")

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    console.print("[info]Aguardando seleção da imagem na janela do explorador...[/info]")
    caminhoFoto = filedialog.askopenfilename(
        title="Selecione a Imagem para o SnapNote",
        filetypes=[("Arquivos de Imagem", "*.png;*.jpg;*.jpeg")]
    )

    if caminhoFoto:
        console.print(f"[success]✅ Imagem selecionada:[/success] {caminhoFoto}")

        opcao = questionary.select(
            '\nComo deseja inserir a anotação?',
            choices=[
                Choice(title="Gravar áudio.", value=1),
                Choice(title="Digitar anotação.", value=2)
            ],
            style=estilo_menu
        ).ask()

        if opcao == 1:
            textoAnotacao = gravarAudio()
            if textoAnotacao is None:
                textoAnotacao = console.input("\n[info]📝 Digite a sua anotação para esta imagem:[/info] ")
        else:
            textoAnotacao = console.input("\n[info]📝 Digite a sua anotação para esta imagem:[/info] ")

        for i in palavrasChaves:
            if i in textoAnotacao.lower():
                destinoAbsoluto = os.path.join(os.getcwd(), i)
                os.makedirs(destinoAbsoluto, exist_ok=True)
                novoCaminho = copiarImagem(caminhoFoto, destinoAbsoluto)
                if novoCaminho:
                    caminhoFoto = novoCaminho

        galeria.append({"imagem": caminhoFoto, "anotacao": textoAnotacao})
        console.print("\n[success]✅ Anotação salva com sucesso![/success]")
    else:
        console.print("\n[error]❌ Operação cancelada. Nenhuma imagem foi selecionada.[/error]")


# Percorre a lista da galeria e exibe todas as imagens e anotações salvas.
def exibirAnotacoes():
    if not galeria:
        console.print("\n[warning]⚠️ Sua galeria está vazia. Adicione uma anotação primeiro![/warning]")
        return

    tabela = Table(title="🖼️ IMAGENS SALVAS", show_header=True, header_style="bold magenta", border_style="cyan")
    tabela.add_column("Caminho do Arquivo", style="cyan", overflow="fold")
    tabela.add_column("Anotação", style="white")

    for i in galeria:
        tabela.add_row(i["imagem"], i["anotacao"])

    console.print("\n")
    console.print(tabela)


# Busca por uma palavra específica dentro das anotações e exibe os resultados correspondentes.
def buscarAnotacao():
    if not galeria:
        console.print("\n[warning]⚠️ Sua galeria está vazia. Adicione uma anotação primeiro![/warning]")
        return

    filtro = console.input('\n[info]🔎 Digite o termo que deseja buscar:[/info] ').lower()
    resultadosEncontrados = 0

    tabela = Table(title=f"🔎 RESULTADOS PARA '{filtro.upper()}'", show_header=True, header_style="bold magenta",
                   border_style="cyan")
    tabela.add_column("Caminho do Arquivo", style="cyan", overflow="fold")
    tabela.add_column("Anotação", style="white")

    for item in galeria:
        if filtro in item['anotacao'].lower():
            tabela.add_row(item["imagem"], item["anotacao"])
            resultadosEncontrados += 1

    if resultadosEncontrados == 0:
        console.print("\n[error]❌ Nenhuma anotação encontrada para esta busca.[/error]")
    else:
        console.print("\n")
        console.print(tabela)
        console.print(f"[success]✅ {resultadosEncontrados} resultado(s) encontrado(s)![/success]")


# Limpa o texto do terminal de acordo com o sistema operacional (Windows ou Mac/Linux).
def limparTerminal():
    os.system('cls' if os.name == 'nt' else 'clear')


# Copia de forma segura um arquivo de imagem da origem para o destino.
def copiarImagem(origem, destino):
    if os.path.exists(origem):
        try:
            novoCaminho = shutil.copy2(origem, destino)
            return novoCaminho

        except Exception as erro:
            console.print(f"\n[error]❌ Ocorreu um erro inesperado ao copiar a imagem: {origem}[/error]")
            return None
    else:
        console.print("\n[error]❌ Erro: O arquivo original não foi encontrado no caminho especificado.[/error]")
        return None


# Gerencia o submenu de palavras-chave, permitindo cadastrar, consultar, apagar ou visualizar pastas.
def cadPalavraChave():
    while True:
        opcao = questionary.select(
            '\nO que deseja fazer?',
            choices=[
                Choice(title="Cadastrar palavra-chave.", value=1),
                Choice(title="Consultar palavras-chaves cadastradas.", value=2),
                Choice(title="Apagar palavra-chave.", value=3),
                Choice(title="Visualizar pasta da palavra-chave.", value=4),
                Choice(title="Entender como funciona.", value=5),
                Choice(title="Voltar ao menu principal.", value=6)
            ],
            style=estilo_menu
        ).ask()

        if opcao == 1:
            palavra = console.input("\n[info]🔑 Digite a nova palavra-chave:[/info] ").strip().lower()

            if not palavra:
                console.print("\n[error]❌ Formato inválido! A palavra-chave não pode ser vazia.[/error]")
            elif ' ' in palavra:
                console.print(
                    "\n[error]❌ Formato inválido! A palavra-chave deve ser uma única palavra (sem espaços). Você pode usar '-' ou '_'.[/error]")
            elif palavra not in palavrasChaves:
                palavrasChaves.append(palavra)
                for i in galeria:
                    if palavra in i['anotacao'].lower():
                        destinoAbsoluto = os.path.join(os.getcwd(), palavra)
                        os.makedirs(destinoAbsoluto, exist_ok=True)
                        novoCaminho = copiarImagem(i['imagem'], destinoAbsoluto)
                        if novoCaminho:
                            i['imagem'] = novoCaminho
                console.print(f"\n[success]✅ Palavra-chave '{palavra}' cadastrada com sucesso![/success]")
                console.print(
                    f"[info]📁 As imagens correspondentes serão organizadas em: {os.path.join(os.getcwd(), palavra)}[/info]")
            else:
                console.print("\n[warning]⚠️ Esta palavra-chave já está cadastrada.[/warning]")

        elif opcao == 2:
            if not palavrasChaves:
                console.print("\n[warning]⚠️ Nenhuma palavra-chave cadastrada ainda.[/warning]")
            else:
                painel_chaves = Panel(
                    "\n".join([f"🔹 {p.capitalize()}" for p in palavrasChaves]),
                    title="[bold magenta]🔑 PALAVRAS-CHAVES CADASTRADAS[/bold magenta]",
                    expand=False,
                    border_style="cyan"
                )
                console.print("\n")
                console.print(painel_chaves)

        elif opcao == 3:
            if not palavrasChaves:
                console.print("\n[warning]⚠️ Nenhuma palavra-chave cadastrada para apagar.[/warning]")
            else:
                opcoesExclusao = [Choice(title=p.capitalize(), value=p) for p in palavrasChaves]
                palavraApagar = questionary.select(
                    "\n🗑️ Qual palavra-chave deseja apagar?",
                    choices=opcoesExclusao,
                    style=estilo_menu
                ).ask()

                if palavraApagar:
                    confirmacao = questionary.confirm(
                        f"Tem certeza que deseja apagar a palavra '{palavraApagar}' e excluir a sua pasta?",
                        style=estilo_menu
                    ).ask()

                    if confirmacao:
                        palavrasChaves.remove(palavraApagar)
                        caminhoPasta = os.path.join(os.getcwd(), palavraApagar)

                        if os.path.exists(caminhoPasta):
                            shutil.rmtree(caminhoPasta, ignore_errors=True)

                        console.print(
                            f"\n[success]✅ Palavra-chave '{palavraApagar}' e sua pasta foram removidas com sucesso![/success]")
                    else:
                        console.print("\n[info]❌ Operação cancelada.[/info]")

        elif opcao == 4:
            if not palavrasChaves:
                console.print("\n[warning]⚠️ Nenhuma palavra-chave cadastrada para visualizar.[/warning]")
            else:
                opcoesVisualizar = [Choice(title=p.capitalize(), value=p) for p in palavrasChaves]
                palavraVisualizar = questionary.select(
                    "\n📂 Qual pasta de palavra-chave deseja abrir?",
                    choices=opcoesVisualizar,
                    style=estilo_menu
                ).ask()

                if palavraVisualizar:
                    caminhoPasta = os.path.join(os.getcwd(), palavraVisualizar)

                    if os.path.exists(caminhoPasta):
                        if os.name == 'nt':
                            os.startfile(caminhoPasta)
                        elif sys.platform == 'darwin':
                            subprocess.Popen(['open', caminhoPasta])
                        else:
                            subprocess.Popen(['xdg-open', caminhoPasta])
                        console.print(f"\n[success]✅ Abrindo o explorador na pasta:[/success] {caminhoPasta}")
                    else:
                        console.print(
                            "\n[warning]⚠️ A pasta para esta palavra-chave ainda não existe no disco (nenhuma imagem foi vinculada a ela ainda).[/warning]")

        elif opcao == 5:
            info_painel = Panel(
                "Cadastre termos para organizar suas imagens de forma automática.\n"
                "O sistema reconhece os termos nas suas anotações e separa os arquivos em suas respectivas pastas.",
                title="💡 [bold yellow]MÓDULO DE PALAVRAS-CHAVE[/bold yellow]",
                border_style="yellow",
                expand=False
            )
            console.print("\n")
            console.print(info_painel)
        else:
            break


#Criando uma despedida "melhor"
def despedida_animada():
    mensagens = ["Limpando cache...", "Organizando arquivos...", "SnapNote desligando..."]

    with Live(console=console, refresh_per_second=4) as live:
        for msg in mensagens:
            live.update(Align.center(Panel(f"[bold magenta]{msg}[/bold magenta]", width=40)))
            sleep(0.8)

    # Limpa tudo e deixa uma mensagem final mais boa para a visão
    limparTerminal()
    console.print('\n[highlight]👋 Encerrando o SnapNote. Até logo![/highlight]\n')


# Loop principal de execução do programa
while True:
    opcao = menuPrincipal()

    if opcao == 1:
        adicionarAnotacao()
    elif opcao == 2:
        exibirAnotacoes()
    elif opcao == 3:
        buscarAnotacao()
    elif opcao == 4:
        cadPalavraChave()
    elif opcao == 5:
        limparTerminal()
    elif opcao == 6 or opcao is None:
        despedida_animada()
        break