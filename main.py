#Olha só, não apaguei nada, então não reclame
import os, sys, subprocess, shutil
import tkinter as tk
from tkinter import filedialog
import questionary
from questionary import Choice, Style
import speech_recognition as sr
import cv2
from datetime import datetime

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

# Pasta onde as fotos tiradas pela câmera serão salvas
pastaFotos = os.path.join(os.getcwd(), "fotos_capturadas")


# Garante que a pasta de fotos capturadas existe
def garantirPastaFotos():
    os.makedirs(pastaFotos, exist_ok=True)


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
            Choice(title="📷  Tirar foto agora e adicionar anotação.", value=1),
            Choice(title="🖼️  Selecionar imagem e gerar uma anotação.", value=2),
            Choice(title="📋  Exibir anotações.", value=3),
            Choice(title="🔎  Buscar imagem pela anotação.", value=4),
            Choice(title="🔑  Controle de palavras-chave.", value=5),
            Choice(title="🧹  Limpar o terminal.", value=6),
            Choice(title="🚪  Finalizar execução", value=7),
        ],
        style=estilo_menu
    ).ask()

    return opcao


# Abre a câmera ao vivo, mostra preview e captura foto ao pressionar ESPAÇO ou ENTER.
# Retorna o caminho da imagem salva, ou None se cancelado.
def tirarFoto():
    garantirPastaFotos()

    console.print("\n[highlight]📷 Abrindo câmera... Aguarde.[/highlight]")
    console.print("[info]  → Pressione [ESPAÇO] ou [ENTER] para capturar a foto.[/info]")
    console.print("[info]  → Pressione [ESC] ou [Q] para cancelar.[/info]\n")

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        console.print("[error]❌ Não foi possível acessar a câmera. Verifique se ela está conectada.[/error]")
        return None

    # Configura resolução (tenta 1280x720, cai para padrão se não suportado)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    fotoCapturada = None
    nomeJanela = "SnapNote - Camera ao Vivo  |  [ESPACO/ENTER] Capturar  |  [ESC/Q] Cancelar"

    while True:
        ret, frame = cap.read()
        if not ret:
            console.print("[error]❌ Erro ao ler frame da câmera.[/error]")
            break

        # Espelha horizontalmente para efeito de espelho natural
        frameEspelhado = cv2.flip(frame, 1)

        # Overlay com instruções na parte inferior do frame
        altura, largura = frameEspelhado.shape[:2]
        overlay = frameEspelhado.copy()
        cv2.rectangle(overlay, (0, altura - 50), (largura, altura), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frameEspelhado, 0.45, 0, frameEspelhado)

        textoInstrucao = "[ESPACO / ENTER] Capturar   [ESC / Q] Cancelar"
        cv2.putText(
            frameEspelhado,
            textoInstrucao,
            (20, altura - 17),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (180, 255, 180),
            1,
            cv2.LINE_AA
        )

        # Indicador de gravação ao vivo (ponto vermelho pulsante via frame count)
        cv2.circle(frameEspelhado, (largura - 28, 28), 10, (0, 0, 220), -1)
        cv2.putText(
            frameEspelhado,
            "AO VIVO",
            (largura - 90, 34),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 0, 220),
            1,
            cv2.LINE_AA
        )

        cv2.imshow(nomeJanela, frameEspelhado)

        tecla = cv2.waitKey(1) & 0xFF

        # ESPAÇO (32) ou ENTER (13) → capturar
        if tecla in (32, 13):
            # Salva o frame original (sem espelho e sem overlay) para melhor qualidade
            ret2, frameOriginal = cap.read()
            if ret2:
                frameSalvar = cv2.flip(frameOriginal, 1)
            else:
                frameSalvar = frameEspelhado

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nomeArquivo = f"snapnote_{timestamp}.jpg"
            caminhoCompleto = os.path.join(pastaFotos, nomeArquivo)

            cv2.imwrite(caminhoCompleto, frameSalvar, [cv2.IMWRITE_JPEG_QUALITY, 95])
            fotoCapturada = caminhoCompleto

            # Feedback visual: pisca verde por 0.4s
            flash = frameSalvar.copy()
            flash[:] = (100, 255, 100)
            cv2.addWeighted(flash, 0.35, frameSalvar, 0.65, 0, frameSalvar)
            cv2.imshow(nomeJanela, frameSalvar)
            cv2.waitKey(400)
            break

        # ESC (27) ou Q (113) → cancelar
        elif tecla in (27, ord('q'), ord('Q')):
            console.print("\n[warning]⚠️ Captura cancelada pelo usuário.[/warning]")
            break

        # Fecha se janela for fechada pelo botão X
        if cv2.getWindowProperty(nomeJanela, cv2.WND_PROP_VISIBLE) < 1:
            console.print("\n[warning]⚠️ Janela fechada. Captura cancelada.[/warning]")
            break

    cap.release()
    cv2.destroyAllWindows()
    # Aguarda janela fechar completamente (necessário em alguns sistemas)
    cv2.waitKey(1)

    return fotoCapturada


# Tira foto ao vivo com a câmera e repassa o caminho para adicionarAnotacao.
def tirarFotoEAnotar():
    console.print("\n[highlight]📷 Modo câmera ao vivo do SnapNote![/highlight]")

    caminhoFoto = tirarFoto()

    if not caminhoFoto:
        console.print("[error]❌ Nenhuma foto foi capturada.[/error]")
        return

    console.print(f"\n[success]✅ Foto salva em:[/success] {caminhoFoto}")
    console.print(f"[info]📁 Pasta de fotos capturadas: {pastaFotos}[/info]")

    adicionarAnotacao(caminhoFoto)


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


# Abre o explorador para selecionar uma foto (se não receber caminho), recebe a anotação e salva na galeria.
def adicionarAnotacao(caminhoFoto=None):
    if caminhoFoto is None:
        console.print("\n[highlight]📸 Vamos adicionar uma nova anotação ao SnapNote![/highlight]")

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        console.print("[info]Aguardando seleção da imagem na janela do explorador...[/info]")
        caminhoFoto = filedialog.askopenfilename(
            title="Selecione a Imagem para o SnapNote",
            filetypes=[("Arquivos de Imagem", "*.png;*.jpg;*.jpeg")]
        )

        if not caminhoFoto:
            console.print("\n[error]❌ Operação cancelada. Nenhuma imagem foi selecionada.[/error]")
            return

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
if __name__ == "__main__":
    while True:
        opcao = menuPrincipal()

        if opcao == 1:
            tirarFotoEAnotar()
        elif opcao == 2:
            adicionarAnotacao()
        elif opcao == 3:
            exibirAnotacoes()
        elif opcao == 4:
            buscarAnotacao()
        elif opcao == 5:
            cadPalavraChave()
        elif opcao == 6:
            limparTerminal()
        elif opcao == 7 or opcao is None:
            despedida_animada()
            break
