"""Tema único do SnapNote: cor de destaque e tipografia.

Nenhum widget da interface deve referenciar um nome de fonte ou a cor
dourada diretamente — tudo passa por este módulo.
"""
import ctypes
import os
import sys

# ── Cor ──────────────────────────────────────────────────────────────────
GOLD = "#E8B84B"

# ── Fontes ───────────────────────────────────────────────────────────────
FONT_FALLBACK = "Segoe UI"

# Só têm valor definitivo depois que resolve_fonts() roda (precisa de um
# root do Tk já existente para consultar tkinter.font.families()).
FONT_REGULAR = FONT_FALLBACK
FONT_MEDIUM = FONT_FALLBACK

_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")
_FONT_FILES = ["Roboto-Regular.ttf", "Roboto-Medium.ttf", "Roboto-Bold.ttf"]
_FR_PRIVATE = 0x10  # AddFontResourceEx: fonte disponível só para este processo


def register_fonts() -> None:
    """Registra os .ttf de assets/fonts/ para este processo.

    Precisa rodar ANTES de criar o root do Tk (tk.Tk()) — é o próprio
    carregamento do app, antes de qualquer widget existir.
    """
    if sys.platform != "win32":
        print(f"[SnapNote] AVISO: registro de fonte privada só está implementado "
              f"para Windows (plataforma atual: '{sys.platform}'). "
              f"Usando fallback '{FONT_FALLBACK}' em toda a interface.")
        return

    failures = []
    for name in _FONT_FILES:
        path = os.path.join(_FONT_DIR, name)
        if not os.path.isfile(path):
            failures.append(f"{name}: arquivo não encontrado em {path}")
            continue
        added = ctypes.windll.gdi32.AddFontResourceExW(path, _FR_PRIVATE, 0)
        if added == 0:
            failures.append(f"{name}: AddFontResourceExW falhou (retornou 0)")

    if failures:
        print(f"[SnapNote] AVISO: falha ao registrar fonte(s) — a interface vai "
              f"cair no fallback '{FONT_FALLBACK}' onde não conseguir usar Roboto:")
        for item in failures:
            print(f"    - {item}")


def resolve_fonts() -> None:
    """Confirma, consultando o Tk, quais famílias ficaram disponíveis após
    o registro. Precisa rodar depois que tk.Tk() já existe, mas antes de
    qualquer outro widget da interface ser criado.
    """
    import tkinter.font as tkfont
    global FONT_REGULAR, FONT_MEDIUM

    available = set(tkfont.families())

    if "Roboto" in available:
        FONT_REGULAR = "Roboto"
    else:
        FONT_REGULAR = FONT_FALLBACK
        print(f"[SnapNote] AVISO: família 'Roboto' não apareceu em "
              f"tkinter.font.families() após o registro — usando fallback "
              f"'{FONT_FALLBACK}' para peso regular/bold.")

    if "Roboto Medium" in available:
        FONT_MEDIUM = "Roboto Medium"
    elif FONT_REGULAR == "Roboto":
        # O Windows pode não expor "Medium" como família separada (o Tk só
        # sabe pedir weight="normal"/"bold", não "medium"); sem um nome de
        # família próprio para o peso Medium, a única opção é usar Roboto
        # normal onde o pedido era Medium.
        FONT_MEDIUM = "Roboto"
        print("[SnapNote] AVISO: família 'Roboto Medium' não encontrada "
              "separadamente em tkinter.font.families() — textos com peso "
              "Medium vão renderizar em peso normal de 'Roboto'.")
    else:
        FONT_MEDIUM = FONT_FALLBACK

    print(f"[SnapNote] Tipografia resolvida: regular='{FONT_REGULAR}', "
          f"medium='{FONT_MEDIUM}'.")


def letter_spaced(text: str) -> str:
    """Aproxima tracking positivo inserindo um espaço fino entre letras.

    O Tkinter não tem letter-spacing nativo em fontes — isto é uma
    aproximação visual (não um valor de tracking exato em px).
    """
    return " ".join(text)


# ── Escala tipográfica ───────────────────────────────────────────────────
# Funções (não tuplas fixas) porque FONT_REGULAR/FONT_MEDIUM só têm o valor
# final depois de resolve_fonts() rodar em tempo de execução.
def type_zeiss():
    return (FONT_REGULAR, 13, "bold")


def type_mode(active: bool):
    return (FONT_MEDIUM, 14, "normal") if active else (FONT_REGULAR, 14, "normal")


def type_zoom(active: bool):
    return (FONT_MEDIUM, 13, "normal") if active else (FONT_REGULAR, 13, "normal")
