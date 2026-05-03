import os
import tkinter as tk
from tkinter import filedialog
import questionary
from questionary import Choice

galeria = []

# Função que exibe menu principal e retorna a opção
def menuPrincipal():
    menuHeader = '\n=======================================\n       SNAPNOTE - MENU PRINCIPAL\n=======================================\n'
    opcao = questionary.select(
        menuHeader,
        choices=[
            Choice(title="Selecionar imagem e gerar uma anotação.", value=1),
            Choice(title="Exibir anotações.", value=2),
            Choice(title="Buscar imagem pela anotação.", value=3),
            Choice(title="Limpar o terminal.", value=4),
            Choice(title="Finalizar execução", value=5),
        ]
    ).ask()

    return opcao

# Função da Opção 1 - Salvar imagem com anotação
def adicionarAnotacao():
    print("Vamos adicionar uma nova anotação ao SnapNote!")

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    print("Aguardando você selecionar a imagem na janela...")
    caminho_foto = filedialog.askopenfilename(
        title="Selecione o Print para o SnapNote",
        filetypes=[("Arquivos de Imagem", "*.png;*.jpg;*.jpeg")]
    )

    if caminho_foto:
        print(f"\nImagem selecionada: {caminho_foto}")
        texto_anotacao = input("Digite a sua anotação para este print: ")

        galeria.append({"imagem": caminho_foto, "anotacao": texto_anotacao})
        print("✅ Anotação salva com sucesso!")
    else:
        print("❌ Operação cancelada. Nenhuma imagem foi selecionada.")

#Função que exibe as anotações já salvas
def exibirAnotacoes():
    if not galeria:
        print("Sua galeria está vazia. Adicione uma anotação primeiro!")
        return

    print('Imagens salvas:\n')
    for i in galeria:
        print(f'Caminho da imagem: {i['imagem']}\nAnotação: {i['anotacao']}\n')

#Função que busca anotações com filtro
def buscarAnotacao():
    if not galeria:
        print("Sua galeria está vazia. Adicione uma anotação primeiro!")
        return

    filtro = input('Digite o que deseja buscar:\n').lower()
    resultados_encontrados = 0

    print(f"\n--- Resultados para '{filtro}' ---")

    for item in galeria:
        if filtro in item['anotacao'].lower():
            print(f'\nCaminho da imagem: {item["imagem"]}\nAnotação: {item["anotacao"]}\n')
            resultados_encontrados += 1

    if resultados_encontrados == 0:
        print("❌ Nenhuma anotação encontrada para essa busca.")
    else:
        print(f"✅ {resultados_encontrados} resultado(s) encontrado(s)!")

#Função para limpar o terminal
def limparTerminal():
    os.system('cls' if os.name == 'nt' else 'clear')

while True:
    opcao = menuPrincipal()

    if opcao == 1:
        adicionarAnotacao()
    elif opcao == 2:
        exibirAnotacoes()
    elif opcao == 3:
        buscarAnotacao()
    elif opcao == 4:
        limparTerminal()
    elif opcao == 5:
        print('Encerrando...')
        break
