# 📸 SnapNote

**SnapNote** é uma aplicação de linha de comando (CLI) inteligente para gerenciar, organizar e anotar sua galeria de imagens. Com uma interface moderna e interativa no terminal, você pode adicionar notas às suas fotos usando o teclado ou **comandos de voz**, além de categorizar automaticamente seus arquivos através de palavras-chave.

---

## 🚀 Funcionalidades

* **Anotações Inteligentes:** Selecione uma imagem pelo explorador de arquivos nativo do seu sistema e vincule uma anotação a ela digitando ou falando ao microfone.
* **Organização Automática:** Cadastre palavras-chave personalizadas. Se a sua anotação contiver uma dessas palavras, o SnapNote cria uma pasta e organiza a imagem lá dentro automaticamente.
* **Busca Rápida:** Filtre suas anotações e encontre rapidamente qual arquivo de imagem corresponde àquele registro.
* **Gestão de Palavras-chave:** Crie, consulte, exclua e abra as pastas das suas palavras-chave diretamente pelo menu do terminal.
* **Interface Rica e Responsiva:** Menus de múltipla escolha (`Questionary`), tabelas coloridas, animações de carregamento e banners estilizados (`Rich`).

---

## ⚙️ Pré-requisitos

Para rodar este projeto, você precisará do **Python** instalado em sua máquina (lembre-se de marcar a opção "Add Python to PATH" durante a instalação, se estiver no Windows).

O projeto utiliza as seguintes bibliotecas externas:
* `rich` - Para a estilização do terminal, tabelas e animações.
* `questionary` - Para os menus de seleção interativos.
* `SpeechRecognition` - Para a transcrição de voz para texto (usando a API do Google).
* `PyAudio` - Dependência necessária para captar o áudio do seu microfone.

---

## 🛠️ Instalação e Execução

**1. Salve o projeto:**
Clone o projeto ou certifique-se de que o código fonte do projeto está salvo em um arquivo como `main.py`.

**2. Instale as dependências:**
Abra o seu terminal na pasta do projeto e execute o comando abaixo para baixar todas as bibliotecas necessárias:
```bash
pip install questionary SpeechRecognition rich pyaudio opencv-python
