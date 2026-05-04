import os
import sys
import subprocess
import tkinter as tk
from tkinter import filedialog
import questionary
from questionary import Choice
import speech_recognition as sr
import shutil

galeria = []
palavrasChaves = []

# Exibe o menu principal e retorna a opção escolhida pelo usuário.
def menuPrincipal():
    menuHeader = '\n=======================================\n       SNAPNOTE - MENU PRINCIPAL\n=======================================\n'
    opcao = questionary.select(
        menuHeader,
        choices=[
            Choice(title="Selecionar imagem e gerar uma anotação.", value=1),
            Choice(title="Exibir anotações.", value=2),
            Choice(title="Buscar imagem pela anotação.", value=3),
            Choice(title="Controle de palavras-chave.", value=4),
            Choice(title="Limpar o terminal.", value=5),
            Choice(title="Finalizar execução", value=6),
        ]
    ).ask()

    return opcao

# Grava o áudio do microfone, transcreve para texto usando o Google e retorna o resultado.
def gravarAudio():
    reconhecedor = sr.Recognizer()

    with sr.Microphone() as source:
        print("\n🎤 Ajustando o ruído de fundo... aguarde um instante.")
        reconhecedor.adjust_for_ambient_noise(source, duration=1)

        print("🔴 Pode falar! Estou ouvindo...")

        try:
            audio = reconhecedor.listen(source, timeout=5, phrase_time_limit=20)
            print("⏳ Processando o áudio...")
            textoTranscrito = reconhecedor.recognize_google(audio, language='pt-BR')
            return textoTranscrito

        except sr.UnknownValueError:
            print("❌ Desculpe, o áudio ficou confuso e não foi possível entender.")
            return None
        except sr.RequestError:
            print("❌ Erro de conexão. Verifique sua internet.")
            return None
        except sr.WaitTimeoutError:
            print("❌ Você demorou muito para falar. Operação cancelada.")
            return None

# Abre o explorador para selecionar uma foto, recebe a anotação (texto ou voz) e salva na galeria.
def adicionarAnotacao():
    print("\n📸 Vamos adicionar uma nova anotação ao SnapNote!")

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    print("Aguardando seleção da imagem na janela do explorador...")
    caminhoFoto = filedialog.askopenfilename(
        title="Selecione a Imagem para o SnapNote",
        filetypes=[("Arquivos de Imagem", "*.png;*.jpg;*.jpeg")]
    )

    if caminhoFoto:
        print(f"✅ Imagem selecionada: {caminhoFoto}")

        opcao = questionary.select(
            '\nComo deseja inserir a anotação?',
            choices=[
                Choice(title="Gravar áudio.", value=1),
                Choice(title="Digitar anotação.", value=2)
            ]
        ).ask()

        if opcao == 1:
            textoAnotacao = gravarAudio()
            if textoAnotacao is None:
                textoAnotacao = input("\n📝 Digite a sua anotação para esta imagem: ")
        else:
            textoAnotacao = input("\n📝 Digite a sua anotação para esta imagem: ")

        for i in palavrasChaves:
            if i in textoAnotacao.lower():
                destinoAbsoluto = os.path.join(os.getcwd(), i)
                os.makedirs(destinoAbsoluto, exist_ok=True)
                novoCaminho = copiarImagem(caminhoFoto, destinoAbsoluto)
                if novoCaminho:
                    caminhoFoto = novoCaminho

        galeria.append({"imagem": caminhoFoto, "anotacao": textoAnotacao})
        print("\n✅ Anotação salva com sucesso!")
    else:
        print("\n❌ Operação cancelada. Nenhuma imagem foi selecionada.")

# Percorre a lista da galeria e exibe todas as imagens e anotações salvas.
def exibirAnotacoes():
    if not galeria:
        print("\n⚠️ Sua galeria está vazia. Adicione uma anotação primeiro!")
        return

    print('\n--- 🖼️ IMAGENS SALVAS ---')
    for i in galeria:
        print(f'📁 Caminho: {i["imagem"]}\n📝 Anotação: {i["anotacao"]}\n{"-" * 40}')

# Busca por uma palavra específica dentro das anotações e exibe os resultados correspondentes.
def buscarAnotacao():
    if not galeria:
        print("\n⚠️ Sua galeria está vazia. Adicione uma anotação primeiro!")
        return

    filtro = input('\n🔎 Digite o termo que deseja buscar: ').lower()
    resultadosEncontrados = 0

    print(f"\n--- 🔎 RESULTADOS PARA '{filtro.upper()}' ---")

    for item in galeria:
        if filtro in item['anotacao'].lower():
            print(f'📁 Caminho: {item["imagem"]}\n📝 Anotação: {item["anotacao"]}\n{"-" * 40}')
            resultadosEncontrados += 1

    if resultadosEncontrados == 0:
        print("\n❌ Nenhuma anotação encontrada para esta busca.")
    else:
        print(f"\n✅ {resultadosEncontrados} resultado(s) encontrado(s)!")

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
            print(f"\n❌ Ocorreu um erro inesperado ao copiar a imagem: {origem}")
            return None
    else:
        print("\n❌ Erro: O arquivo original não foi encontrado no caminho especificado.")
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
            ]
        ).ask()

        if opcao == 1:
            palavra = input("\n🔑 Digite a nova palavra-chave: ").strip().lower()

            if not palavra:
                print("\n❌ Formato inválido! A palavra-chave não pode ser vazia.")
            elif ' ' in palavra:
                print(
                    "\n❌ Formato inválido! A palavra-chave deve ser uma única palavra (sem espaços). Você pode usar '-' ou '_'.")
            elif palavra not in palavrasChaves:
                palavrasChaves.append(palavra)
                for i in galeria:
                    if palavra in i['anotacao'].lower():
                        destinoAbsoluto = os.path.join(os.getcwd(), palavra)
                        os.makedirs(destinoAbsoluto, exist_ok=True)
                        novoCaminho = copiarImagem(i['imagem'], destinoAbsoluto)
                        if novoCaminho:
                            i['imagem'] = novoCaminho
                print(
                    f'\n✅ Palavra-chave \'{palavra}\' cadastrada com sucesso!\n📁 As imagens correspondentes serão organizadas em: {os.path.join(os.getcwd(), palavra)}')
            else:
                print("\n⚠️ Esta palavra-chave já está cadastrada.")

        elif opcao == 2:
            if not palavrasChaves:
                print("\n⚠️ Nenhuma palavra-chave cadastrada ainda.")
            else:
                print('\n--- 🔑 PALAVRAS-CHAVES CADASTRADAS ---')
                for i in palavrasChaves:
                    print(f'🔹 {i.capitalize()}')
                print("-" * 40)

        elif opcao == 3:
            if not palavrasChaves:
                print("\n⚠️ Nenhuma palavra-chave cadastrada para apagar.")
            else:
                opcoesExclusao = [Choice(title=p.capitalize(), value=p) for p in palavrasChaves]
                palavraApagar = questionary.select(
                    "\n🗑️ Qual palavra-chave deseja apagar?",
                    choices=opcoesExclusao
                ).ask()

                if palavraApagar:
                    confirmacao = questionary.confirm(
                        f"Tem certeza que deseja apagar a palavra '{palavraApagar}' e excluir a sua pasta?").ask()

                    if confirmacao:
                        palavrasChaves.remove(palavraApagar)
                        caminhoPasta = os.path.join(os.getcwd(), palavraApagar)

                        if os.path.exists(caminhoPasta):
                            shutil.rmtree(caminhoPasta, ignore_errors=True)

                        print(f"\n✅ Palavra-chave '{palavraApagar}' e sua pasta foram removidas com sucesso!")
                    else:
                        print("\n❌ Operação cancelada.")

        elif opcao == 4:
            if not palavrasChaves:
                print("\n⚠️ Nenhuma palavra-chave cadastrada para visualizar.")
            else:
                opcoesVisualizar = [Choice(title=p.capitalize(), value=p) for p in palavrasChaves]
                palavraVisualizar = questionary.select(
                    "\n📂 Qual pasta de palavra-chave deseja abrir?",
                    choices=opcoesVisualizar
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
                        print(f"\n✅ Abrindo o explorador na pasta: {caminhoPasta}")
                    else:
                        print(
                            "\n⚠️ A pasta para esta palavra-chave ainda não existe no disco (nenhuma imagem foi vinculada a ela ainda).")

        elif opcao == 5:
            print('\n--- 💡 MÓDULO DE PALAVRAS-CHAVE ---')
            print('Cadastre termos para organizar suas imagens de forma automática.')
            print('O sistema reconhece os termos nas suas anotações e separa os arquivos em suas respectivas pastas.')
            print("-" * 35)
        else:
            break

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
    elif opcao == 6:
        print('\n👋 Encerrando o SnapNote. Até logo!\n')
        break