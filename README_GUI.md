# 📱 SnapNote — Interface Gráfica

**SnapNote GUI** é a versão com interface gráfica do SnapNote, desenvolvida para simular a experiência de um aplicativo de câmera mobile diretamente no seu computador. Com um design escuro, minimalista e moderno, você captura fotos, adiciona anotações, organiza por palavras-chave e pesquisa tudo isso em uma janela que imita a proporção de um smartphone.

---

## 🚀 Funcionalidades

* **Câmera ao vivo:** Visualize o feed da sua webcam em tempo real dentro da própria janela da interface e capture fotos com um clique no botão shutter circular.
* **Anotação rápida:** Após capturar uma foto, um popup flutuante aparece sobre a prévia escurecida da imagem, com ícones para escrever a anotação manualmente ou ditá-la por voz — a gravação transcreve e salva automaticamente, sem precisar de outra ação.
* **Organização automática por palavras-chave:** Cadastre palavras-chave por um diálogo próprio da aplicação. Toda vez que uma anotação contiver a palavra, a imagem é copiada automaticamente para a pasta correspondente.
* **Galeria estilo Google Fotos:** Grid de três colunas, sem bordas arredondadas, com as fotos agrupadas por data de captura (mais recentes primeiro) e a legenda da anotação exibida abaixo de cada miniatura.
* **Busca integrada à galeria:** Toque no ícone de lupa para abrir um campo de busca flutuante que filtra as anotações a cada tecla digitada — sem precisar trocar de tela.
* **Persistência de dados:** Anotações e palavras-chave são salvas automaticamente em `snapnote_data.json` e recarregadas na próxima vez que você abrir o app.
* **Detalhe de imagem:** Toque em qualquer foto para ver a imagem ampliada com cantos arredondados, a anotação completa e a data da captura formatada.

---

## ⚙️ Pré-requisitos

Para rodar este projeto, você precisará do **Python** instalado em sua máquina (lembre-se de marcar a opção "Add Python to PATH" durante a instalação, se estiver no Windows).

O projeto utiliza as seguintes bibliotecas externas:

* `opencv-python` — Para captura e processamento do feed da webcam.
* `Pillow` — Para carregamento e redimensionamento de imagens na interface.
* `SpeechRecognition` — Para transcrição de voz para texto via anotação por microfone (opcional).
* `PyAudio` — Dependência necessária para captar o áudio do microfone (opcional).

> **Nota:** A interface gráfica utiliza `tkinter`, que já vem incluído na instalação padrão do Python. Nenhuma instalação adicional é necessária para ele.

---

## 🛠️ Instalação e Execução

**1. Salve o projeto:**
Clone o projeto ou certifique-se de que os arquivos `gui.py` e `main.py` estão na mesma pasta.

**2. Instale as dependências:**
Abra o terminal na pasta do projeto e execute:

```bash
pip install opencv-python Pillow SpeechRecognition pyaudio
```

> Se você não precisar da funcionalidade de anotação por voz, pode instalar apenas as dependências essenciais:
> ```bash
> pip install opencv-python Pillow
> ```

**3. Execute a interface:**

```bash
python gui.py
```

---

## 🗂️ Estrutura de arquivos gerados

Ao usar o app, os seguintes arquivos e pastas são criados automaticamente no diretório do projeto:

```
sprint2_python/
├── gui.py                  # Interface gráfica (este arquivo)
├── main.py                 # Versão original em terminal (CLI)
├── snapnote_data.json      # Anotações e palavras-chave salvas
├── fotos_capturadas/       # Fotos tiradas pela câmera
│   └── snapnote_*.jpg
└── <palavra-chave>/        # Pastas criadas por palavra-chave
    └── snapnote_*.jpg
```

---

## 🖥️ Navegação

A janela possui duas telas:

| Tela | Como chegar lá | O que faz |
|------|-----------------|-----------|
| **Câmera** | Tela inicial do app | Exibe o feed ao vivo e permite capturar fotos |
| **Galeria** | Toque na miniatura no canto inferior esquerdo da câmera | Mostra as fotos organizadas por data, com busca e menu de palavras-chave nas ilhas flutuantes |

Na galeria, o botão circular no canto superior esquerdo volta para a câmera.

---

## 🎙️ Anotação por voz

Após capturar uma foto, o popup de anotação exibe uma pílula com ícones — toque no microfone para gravar sua voz e transcrever automaticamente para texto usando a API do Google (requer conexão com a internet), ou toque no ícone de lápis para digitar a anotação num campo de texto.

---

## 💾 Relação com a versão CLI

O `gui.py` é **independente** do `main.py` e pode ser executado sem ele. Ambas as versões compartilham a mesma pasta `fotos_capturadas/` e o mesmo arquivo de dados `snapnote_data.json`, portanto fotos e anotações criadas em uma versão ficam visíveis na outra.

Para usar a versão original de terminal:

```bash
python main.py
```
