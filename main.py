"""
SnapNote GUI — Interface gráfica moderna para o SnapNote
Dependências: customtkinter, Pillow, opencv-python, SpeechRecognition

Instalar com:
    pip install customtkinter pillow opencv-python SpeechRecognition
"""

import os, sys, shutil, threading, subprocess
from datetime import datetime
import tkinter as tk
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw, ImageFilter
import cv2

try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False

# ─────────────────────────── CONFIGURAÇÃO VISUAL ────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

PALETA = {
    "bg_deep":     "#0A0A0F",
    "bg_panel":    "#111118",
    "bg_card":     "#16161F",
    "bg_input":    "#1C1C28",
    "accent":      "#C678FF",   # violeta principal
    "accent2":     "#61AFEF",   # azul suave
    "accent3":     "#98C379",   # verde confirmação
    "warn":        "#E5C07B",   # amarelo aviso
    "danger":      "#E06C75",   # vermelho erro
    "text_main":   "#E8E8F0",
    "text_muted":  "#6B6B80",
    "text_dim":    "#3A3A50",
    "border":      "#2A2A3A",
    "border_glow": "#C678FF44",
}

FONTE_TITLE  = ("Trebuchet MS", 22, "bold")
FONTE_HEADER = ("Trebuchet MS", 14, "bold")
FONTE_BODY   = ("Consolas", 12)
FONTE_SMALL  = ("Consolas", 10)
FONTE_MONO   = ("Courier New", 11)

PASTA_FOTOS = os.path.join(os.getcwd(), "fotos_capturadas")
os.makedirs(PASTA_FOTOS, exist_ok=True)

# ─────────────────────────────── ESTADO GLOBAL ──────────────────────────────

galeria        = []   # [{"imagem": str, "anotacao": str}]
palavras_chave = []   # [str]


# ════════════════════════════════════════════════════════════════════════════
#  UTILITÁRIOS
# ════════════════════════════════════════════════════════════════════════════

def copiar_imagem(origem: str, destino: str) -> str | None:
    if os.path.exists(origem):
        try:
            return shutil.copy2(origem, destino)
        except Exception:
            return None
    return None


def aplicar_palavra_chave_a_galeria(palavra: str):
    for item in galeria:
        if palavra in item["anotacao"].lower():
            pasta = os.path.join(os.getcwd(), palavra)
            os.makedirs(pasta, exist_ok=True)
            novo = copiar_imagem(item["imagem"], pasta)
            if novo:
                item["imagem"] = novo


def thumbnail(path: str, size=(120, 90)) -> ImageTk.PhotoImage | None:
    try:
        img = Image.open(path).convert("RGB")
        img.thumbnail(size, Image.LANCZOS)

        # Canvas com fundo escuro + imagem centralizada
        canvas = Image.new("RGB", size, (22, 22, 31))
        ox = (size[0] - img.width)  // 2
        oy = (size[1] - img.height) // 2
        canvas.paste(img, (ox, oy))
        return ImageTk.PhotoImage(canvas)
    except Exception:
        return None


def large_preview(path: str, max_w=520, max_h=380) -> ImageTk.PhotoImage | None:
    try:
        img = Image.open(path).convert("RGB")
        img.thumbnail((max_w, max_h), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════════════
#  WIDGETS CUSTOMIZADOS
# ════════════════════════════════════════════════════════════════════════════

class GlowButton(ctk.CTkButton):
    """Botão com borda colorida animada ao hover."""
    def __init__(self, master, color=None, **kw):
        color = color or PALETA["accent"]
        kw.setdefault("fg_color",            "#1C1C2E")
        kw.setdefault("hover_color",         "#2A1A40")
        kw.setdefault("border_color",        color)
        kw.setdefault("border_width",        1)
        kw.setdefault("text_color",          color)
        kw.setdefault("corner_radius",       8)
        kw.setdefault("font",                ("Trebuchet MS", 12, "bold"))
        super().__init__(master, **kw)


class TagBadge(ctk.CTkLabel):
    def __init__(self, master, text, on_remove=None, **kw):
        kw.setdefault("fg_color",    "#2A1040")
        kw.setdefault("text_color",  PALETA["accent"])
        kw.setdefault("corner_radius", 12)
        kw.setdefault("font",         FONTE_SMALL)
        kw.setdefault("padx",         10)
        kw.setdefault("pady",         3)
        full = f"  {text}  ✕" if on_remove else f"  {text}  "
        super().__init__(master, text=full, **kw)
        if on_remove:
            self.bind("<Button-1>", lambda e: on_remove(text))
            self.bind("<Enter>", lambda e: self.configure(fg_color="#3A1A50"))
            self.bind("<Leave>", lambda e: self.configure(fg_color="#2A1040"))


class SectionHeader(ctk.CTkFrame):
    def __init__(self, master, title, icon="", **kw):
        kw.setdefault("fg_color",    "transparent")
        super().__init__(master, **kw)
        ctk.CTkLabel(self, text=f"{icon}  {title}",
                     font=FONTE_HEADER,
                     text_color=PALETA["accent"]).pack(side="left")
        ctk.CTkFrame(self, height=1, fg_color=PALETA["border"]).pack(
            side="left", fill="x", expand=True, padx=(12, 0))


class Toast(ctk.CTkToplevel):
    """Notificação flutuante que some sozinha."""
    def __init__(self, master, msg: str, kind="success"):
        super().__init__(master)
        colors = {"success": PALETA["accent3"],
                  "warn":    PALETA["warn"],
                  "error":   PALETA["danger"],
                  "info":    PALETA["accent2"]}
        color = colors.get(kind, PALETA["accent"])
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=PALETA["bg_card"])
        ctk.CTkLabel(self, text=msg, text_color=color,
                     font=("Trebuchet MS", 12, "bold"),
                     padx=20, pady=12).pack()
        # Posiciona canto inferior direito da janela master
        self.update_idletasks()
        mx = master.winfo_x() + master.winfo_width()  - self.winfo_width()  - 20
        my = master.winfo_y() + master.winfo_height() - self.winfo_height() - 20
        self.geometry(f"+{mx}+{my}")
        self.after(2400, self.destroy)


# ════════════════════════════════════════════════════════════════════════════
#  JANELA: CÂMERA AO VIVO
# ════════════════════════════════════════════════════════════════════════════

class CameraWindow(ctk.CTkToplevel):
    def __init__(self, master, on_capture):
        super().__init__(master)
        self.title("SnapNote · Câmera ao Vivo")
        self.geometry("820x600")
        self.resizable(False, False)
        self.configure(fg_color=PALETA["bg_deep"])
        self.on_capture = on_capture

        self.cap    = None
        self._photo = None
        self._running = True

        # Layout
        self.canvas = tk.Canvas(self, width=640, height=480,
                                bg="#000", highlightthickness=0)
        self.canvas.pack(pady=(16, 0))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(pady=12)
        GlowButton(bar, text="📷  Capturar  [ESPAÇO]",
                   color=PALETA["accent3"], width=200, height=40,
                   command=self._capture).pack(side="left", padx=8)
        GlowButton(bar, text="✕  Cancelar",
                   color=PALETA["danger"], width=140, height=40,
                   command=self._cancel).pack(side="left", padx=8)

        self.bind("<space>",  lambda e: self._capture())
        self.bind("<Return>", lambda e: self._capture())
        self.bind("<Escape>", lambda e: self._cancel())

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.after(100, self._start_camera)

    def _start_camera(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("Câmera", "Não foi possível abrir a câmera.")
            self.destroy()
            return
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._loop()

    def _loop(self):
        if not self._running:
            return
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, 1)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img   = Image.fromarray(rgb)
            self._photo = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
            # Indicador "ao vivo"
            self.canvas.create_oval(610, 10, 630, 30, fill="#CC0000", outline="")
            self.canvas.create_text(600, 20, text="● AO VIVO",
                                    fill="#FF4444", font=("Consolas", 9, "bold"),
                                    anchor="e")
        self.after(30, self._loop)

    def _capture(self):
        if not self.cap or not self.cap.isOpened():
            return
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, 1)
            os.makedirs(PASTA_FOTOS, exist_ok=True)
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(PASTA_FOTOS, f"snapnote_{ts}.jpg")
            cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            self._stop()
            self.on_capture(path)

    def _cancel(self):
        self._stop()

    def _stop(self):
        self._running = False
        if self.cap:
            self.cap.release()
        self.destroy()


# ════════════════════════════════════════════════════════════════════════════
#  JANELA: ADICIONAR ANOTAÇÃO
# ════════════════════════════════════════════════════════════════════════════

class AnotacaoWindow(ctk.CTkToplevel):
    def __init__(self, master, caminho_foto: str, on_save):
        super().__init__(master)
        self.title("SnapNote · Nova Anotação")
        self.geometry("660x520")
        self.resizable(False, False)
        self.configure(fg_color=PALETA["bg_panel"])
        self.caminho_foto = caminho_foto
        self.on_save      = on_save
        self._grab_after  = self.after(200, self.grab_set)

        # Preview
        frame_img = ctk.CTkFrame(self, fg_color=PALETA["bg_deep"],
                                  corner_radius=12)
        frame_img.pack(fill="x", padx=20, pady=(20, 0))

        self.lbl_img = ctk.CTkLabel(frame_img, text="",
                                    width=620, height=200)
        self.lbl_img.pack(padx=4, pady=4)
        self._load_preview()

        # Path label
        ctk.CTkLabel(self,
                     text=f"📁  {os.path.basename(caminho_foto)}",
                     text_color=PALETA["text_muted"],
                     font=FONTE_SMALL).pack(pady=(6, 0))

        # Área de anotação
        ctk.CTkLabel(self, text="✏️  Anotação",
                     font=FONTE_HEADER,
                     text_color=PALETA["accent"]).pack(anchor="w", padx=24, pady=(14, 4))

        self.txt_anotacao = ctk.CTkTextbox(
            self, height=100, width=620,
            fg_color=PALETA["bg_input"],
            border_color=PALETA["border"],
            border_width=1,
            text_color=PALETA["text_main"],
            font=FONTE_BODY)
        self.txt_anotacao.pack(padx=20, pady=(0, 4))
        self.txt_anotacao.focus()

        # Botões
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(pady=10)

        if SPEECH_AVAILABLE:
            GlowButton(bar, text="🎤  Gravar Áudio",
                       color=PALETA["accent2"], width=160, height=36,
                       command=self._gravar_audio).pack(side="left", padx=6)

        GlowButton(bar, text="💾  Salvar",
                   color=PALETA["accent3"], width=140, height=36,
                   command=self._salvar).pack(side="left", padx=6)

        GlowButton(bar, text="✕  Cancelar",
                   color=PALETA["danger"], width=120, height=36,
                   command=self.destroy).pack(side="left", padx=6)

    def _load_preview(self):
        photo = large_preview(self.caminho_foto, max_w=616, max_h=196)
        if photo:
            self.lbl_img.configure(image=photo, text="")
            self.lbl_img._photo = photo

    def _gravar_audio(self):
        self.txt_anotacao.configure(state="disabled")
        Toast(self, "🎤 Ouvindo… fale agora!", "info")

        def run():
            rec = sr.Recognizer()
            try:
                with sr.Microphone() as src:
                    rec.adjust_for_ambient_noise(src, duration=0.6)
                    audio = rec.listen(src, timeout=5, phrase_time_limit=20)
                texto = rec.recognize_google(audio, language="pt-BR")
                self.after(0, lambda: self._inserir_texto(texto))
            except Exception as e:
                self.after(0, lambda: Toast(self, f"❌ {e}", "error"))
            finally:
                self.after(0, lambda: self.txt_anotacao.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def _inserir_texto(self, texto: str):
        self.txt_anotacao.delete("1.0", "end")
        self.txt_anotacao.insert("1.0", texto)

    def _salvar(self):
        anotacao = self.txt_anotacao.get("1.0", "end").strip()
        if not anotacao:
            Toast(self, "⚠️ Anotação não pode ser vazia.", "warn")
            return

        caminho = self.caminho_foto
        for kw in palavras_chave:
            if kw in anotacao.lower():
                pasta = os.path.join(os.getcwd(), kw)
                os.makedirs(pasta, exist_ok=True)
                novo = copiar_imagem(caminho, pasta)
                if novo:
                    caminho = novo

        galeria.append({"imagem": caminho, "anotacao": anotacao})
        self.on_save()
        self.destroy()


# ════════════════════════════════════════════════════════════════════════════
#  PAINEL: GALERIA
# ════════════════════════════════════════════════════════════════════════════

class PainelGaleria(ctk.CTkFrame):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", PALETA["bg_panel"])
        super().__init__(master, **kw)
        self._thumbnails = {}   # path → PhotoImage (evita GC)
        self._build()

    def _build(self):
        # Barra superior
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(16, 8))

        SectionHeader(top, "Galeria de Imagens", "🖼️").pack(side="left", fill="x", expand=True)

        self.entry_busca = ctk.CTkEntry(
            top, placeholder_text="🔎  Buscar anotação…",
            width=240, height=34,
            fg_color=PALETA["bg_input"],
            border_color=PALETA["border"],
            text_color=PALETA["text_main"],
            font=FONTE_BODY)
        self.entry_busca.pack(side="right", padx=(8, 0))
        self.entry_busca.bind("<KeyRelease>", lambda e: self.refresh())

        # Scroll area
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=PALETA["bg_deep"], corner_radius=10)
        self.scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.lbl_empty = ctk.CTkLabel(
            self.scroll,
            text="Nenhuma imagem ainda.\nUse  📷 Tirar Foto  ou  🖼️ Selecionar Imagem.",
            text_color=PALETA["text_muted"],
            font=FONTE_BODY)

        self.refresh()

    def refresh(self, *_):
        for w in self.scroll.winfo_children():
            w.destroy()
        self._thumbnails.clear()

        filtro   = self.entry_busca.get().strip().lower() if hasattr(self, "entry_busca") else ""
        itens    = [i for i in galeria if filtro in i["anotacao"].lower()] if filtro else galeria

        if not itens:
            self.lbl_empty = ctk.CTkLabel(
                self.scroll,
                text="Nenhuma imagem encontrada." if filtro else
                     "Nenhuma imagem ainda.\nUse  📷 Tirar Foto  ou  🖼️ Selecionar Imagem.",
                text_color=PALETA["text_muted"],
                font=FONTE_BODY)
            self.lbl_empty.pack(expand=True, pady=60)
            return

        # Grade responsiva 3 colunas
        for col in range(3):
            self.scroll.grid_columnconfigure(col, weight=1)

        for idx, item in enumerate(itens):
            row, col = divmod(idx, 3)
            self._card(item, row, col)

    def _card(self, item: dict, row: int, col: int):
        card = ctk.CTkFrame(self.scroll,
                            fg_color=PALETA["bg_card"],
                            corner_radius=12,
                            border_width=1,
                            border_color=PALETA["border"])
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

        # Thumbnail
        ph = thumbnail(item["imagem"], (200, 140))
        self._thumbnails[item["imagem"]] = ph
        lbl = ctk.CTkLabel(card, image=ph, text="",
                           width=200, height=140)
        lbl.pack(padx=8, pady=(8, 4))
        lbl.bind("<Button-1>", lambda e, p=item["imagem"]: self._open_image(p))

        # Anotação
        txt = item["anotacao"]
        preview_txt = (txt[:80] + "…") if len(txt) > 80 else txt
        ctk.CTkLabel(card, text=preview_txt,
                     wraplength=190,
                     text_color=PALETA["text_main"],
                     font=FONTE_SMALL,
                     justify="left").pack(padx=10, pady=(0, 4))

        # Nome do arquivo
        ctk.CTkLabel(card, text=os.path.basename(item["imagem"]),
                     text_color=PALETA["text_muted"],
                     font=("Consolas", 9)).pack(padx=10, pady=(0, 6))

        # Hover effect
        for w in (card, lbl):
            w.bind("<Enter>", lambda e, c=card: c.configure(border_color=PALETA["accent"]))
            w.bind("<Leave>", lambda e, c=card: c.configure(border_color=PALETA["border"]))

    def _open_image(self, path: str):
        win = ctk.CTkToplevel(self)
        win.title(os.path.basename(path))
        win.configure(fg_color=PALETA["bg_deep"])
        ph = large_preview(path, 900, 700)
        if ph:
            lbl = ctk.CTkLabel(win, image=ph, text="")
            lbl.pack(padx=16, pady=16)
            lbl._photo = ph
        else:
            ctk.CTkLabel(win, text="Não foi possível abrir a imagem.",
                         text_color=PALETA["danger"]).pack(pady=40)


# ════════════════════════════════════════════════════════════════════════════
#  PAINEL: PALAVRAS-CHAVE
# ════════════════════════════════════════════════════════════════════════════

class PainelPalavrasChave(ctk.CTkFrame):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", PALETA["bg_panel"])
        super().__init__(master, **kw)
        self._build()

    def _build(self):
        SectionHeader(self, "Palavras-Chave", "🔑").pack(
            fill="x", padx=20, pady=(16, 12))

        # Explicação
        ctk.CTkLabel(
            self,
            text="Quando uma anotação contém uma palavra-chave, a imagem é copiada\n"
                 "automaticamente para uma pasta com o nome da palavra.",
            text_color=PALETA["text_muted"],
            font=FONTE_SMALL,
            justify="left"
        ).pack(anchor="w", padx=24, pady=(0, 12))

        # Input + botão adicionar
        add_frame = ctk.CTkFrame(self, fg_color="transparent")
        add_frame.pack(fill="x", padx=20, pady=(0, 16))

        self.entry_kw = ctk.CTkEntry(
            add_frame,
            placeholder_text="nova-palavra-chave",
            width=280, height=38,
            fg_color=PALETA["bg_input"],
            border_color=PALETA["border"],
            text_color=PALETA["text_main"],
            font=FONTE_BODY)
        self.entry_kw.pack(side="left", padx=(0, 10))
        self.entry_kw.bind("<Return>", lambda e: self._adicionar())

        GlowButton(add_frame, text="＋  Adicionar",
                   color=PALETA["accent3"], width=140, height=38,
                   command=self._adicionar).pack(side="left")

        # Container das tags
        self.tags_frame = ctk.CTkScrollableFrame(
            self, fg_color=PALETA["bg_deep"],
            corner_radius=10, height=200)
        self.tags_frame.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # Pastas no disco
        SectionHeader(self, "Pastas no Disco", "📂").pack(
            fill="x", padx=20, pady=(8, 8))

        self.lista_pastas = ctk.CTkScrollableFrame(
            self, fg_color=PALETA["bg_deep"],
            corner_radius=10, height=160)
        self.lista_pastas.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.refresh()

    def refresh(self):
        for w in self.tags_frame.winfo_children():
            w.destroy()
        for w in self.lista_pastas.winfo_children():
            w.destroy()

        if not palavras_chave:
            ctk.CTkLabel(self.tags_frame,
                         text="Nenhuma palavra-chave cadastrada.",
                         text_color=PALETA["text_muted"],
                         font=FONTE_BODY).pack(pady=20)
        else:
            row_frame = None
            for i, kw in enumerate(palavras_chave):
                if i % 4 == 0:
                    row_frame = ctk.CTkFrame(self.tags_frame, fg_color="transparent")
                    row_frame.pack(fill="x", pady=4, padx=8)
                TagBadge(row_frame, kw, on_remove=self._remover).pack(side="left", padx=4)

        # Listar pastas existentes no disco
        for kw in palavras_chave:
            pasta = os.path.join(os.getcwd(), kw)
            existe = os.path.isdir(pasta)
            n_imgs = len([f for f in os.listdir(pasta)
                          if f.lower().endswith((".jpg",".jpeg",".png"))]) if existe else 0

            row = ctk.CTkFrame(self.lista_pastas, fg_color=PALETA["bg_card"],
                               corner_radius=8)
            row.pack(fill="x", padx=4, pady=3)

            icon = "📁" if existe else "📂"
            ctk.CTkLabel(row,
                         text=f"{icon}  {kw}/",
                         text_color=PALETA["accent2"] if existe else PALETA["text_muted"],
                         font=FONTE_BODY,
                         width=200, anchor="w").pack(side="left", padx=12, pady=6)

            ctk.CTkLabel(row,
                         text=f"{n_imgs} imagem(ns)" if existe else "pasta não criada ainda",
                         text_color=PALETA["text_muted"],
                         font=FONTE_SMALL).pack(side="left")

            if existe:
                GlowButton(row, text="Abrir",
                           color=PALETA["accent"], width=70, height=26,
                           command=lambda p=pasta: self._abrir_pasta(p)
                           ).pack(side="right", padx=8)

    def _adicionar(self):
        palavra = self.entry_kw.get().strip().lower()
        self.entry_kw.delete(0, "end")

        if not palavra:
            Toast(self.master.master, "⚠️ Palavra não pode ser vazia.", "warn")
            return
        if " " in palavra:
            Toast(self.master.master, "⚠️ Use '-' ou '_' no lugar de espaços.", "warn")
            return
        if palavra in palavras_chave:
            Toast(self.master.master, "⚠️ Palavra já cadastrada.", "warn")
            return

        palavras_chave.append(palavra)
        aplicar_palavra_chave_a_galeria(palavra)
        self.refresh()
        Toast(self.master.master, f"✅ '{palavra}' adicionada!", "success")

    def _remover(self, palavra: str):
        if not messagebox.askyesno(
                "Remover palavra-chave",
                f"Remover '{palavra}' e apagar sua pasta do disco?"):
            return
        palavras_chave.remove(palavra)
        pasta = os.path.join(os.getcwd(), palavra)
        if os.path.isdir(pasta):
            shutil.rmtree(pasta, ignore_errors=True)
        self.refresh()
        Toast(self.master.master, f"🗑️ '{palavra}' removida.", "info")

    @staticmethod
    def _abrir_pasta(path: str):
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


# ════════════════════════════════════════════════════════════════════════════
#  JANELA PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════

class SnapNoteApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SnapNote  ·  Galeria Inteligente")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(fg_color=PALETA["bg_deep"])
        self._build_ui()

    # ── Layout ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(
            self, width=220, fg_color=PALETA["bg_panel"],
            corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        # Área de conteúdo
        self.content = ctk.CTkFrame(self, fg_color=PALETA["bg_deep"],
                                    corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

        # Painel padrão: galeria
        self.painel_galeria = PainelGaleria(self.content)
        self.painel_galeria.pack(fill="both", expand=True)

        self.painel_kw = PainelPalavrasChave(self.content)

        self._current_panel = "galeria"

    def _build_sidebar(self):
        # Logo / título
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=16, pady=(24, 4))

        ctk.CTkLabel(logo_frame,
                     text="◈ SnapNote",
                     font=("Trebuchet MS", 20, "bold"),
                     text_color=PALETA["accent"]).pack(anchor="w")
        ctk.CTkLabel(logo_frame,
                     text="Galeria Inteligente",
                     font=FONTE_SMALL,
                     text_color=PALETA["text_muted"]).pack(anchor="w")

        ctk.CTkFrame(self.sidebar, height=1,
                     fg_color=PALETA["border"]).pack(fill="x", padx=12, pady=12)

        # Ações principais
        ctk.CTkLabel(self.sidebar, text="CAPTURAR",
                     font=("Consolas", 9, "bold"),
                     text_color=PALETA["text_dim"]).pack(anchor="w", padx=18, pady=(4, 4))

        self._nav_btn(self.sidebar,
                      "📷  Tirar Foto",
                      PALETA["accent"],
                      self._tirar_foto)

        self._nav_btn(self.sidebar,
                      "🖼️  Selecionar Imagem",
                      PALETA["accent2"],
                      self._selecionar_imagem)

        ctk.CTkFrame(self.sidebar, height=1,
                     fg_color=PALETA["border"]).pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(self.sidebar, text="NAVEGAR",
                     font=("Consolas", 9, "bold"),
                     text_color=PALETA["text_dim"]).pack(anchor="w", padx=18, pady=(0, 4))

        self._nav_btn(self.sidebar, "🖼️  Galeria",
                      PALETA["accent"],  self._show_galeria)
        self._nav_btn(self.sidebar, "🔑  Palavras-Chave",
                      PALETA["warn"],    self._show_kw)

        # Espaço + contador
        ctk.CTkFrame(self.sidebar, fg_color="transparent").pack(fill="y", expand=True)

        ctk.CTkFrame(self.sidebar, height=1,
                     fg_color=PALETA["border"]).pack(fill="x", padx=12, pady=8)

        self.lbl_count = ctk.CTkLabel(
            self.sidebar,
            text="0 imagens  ·  0 tags",
            text_color=PALETA["text_muted"],
            font=FONTE_SMALL)
        self.lbl_count.pack(padx=16, pady=(0, 4))

        ctk.CTkLabel(self.sidebar,
                     text="v1.0  ·  SnapNote",
                     text_color=PALETA["text_dim"],
                     font=("Consolas", 9)).pack(pady=(0, 16))

    @staticmethod
    def _nav_btn(parent, text, color, command):
        btn = ctk.CTkButton(
            parent,
            text=text,
            fg_color="transparent",
            hover_color=PALETA["bg_input"],
            text_color=color,
            anchor="w",
            height=38,
            corner_radius=8,
            font=("Trebuchet MS", 12),
            command=command)
        btn.pack(fill="x", padx=8, pady=2)

    # ── Navegação ────────────────────────────────────────────────────────────

    def _show_galeria(self):
        self.painel_kw.pack_forget()
        self.painel_galeria.pack(fill="both", expand=True)
        self._current_panel = "galeria"

    def _show_kw(self):
        self.painel_galeria.pack_forget()
        self.painel_kw.pack(fill="both", expand=True)
        self._current_panel = "kw"

    # ── Ações ────────────────────────────────────────────────────────────────

    def _tirar_foto(self):
        CameraWindow(self, on_capture=self._on_foto_capturada)

    def _on_foto_capturada(self, path: str):
        Toast(self, f"📷 Foto salva!", "success")
        AnotacaoWindow(self, path, on_save=self._on_anotacao_salva)

    def _selecionar_imagem(self):
        path = filedialog.askopenfilename(
            title="Selecione uma imagem",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg")])
        if path:
            AnotacaoWindow(self, path, on_save=self._on_anotacao_salva)

    def _on_anotacao_salva(self):
        Toast(self, "✅ Anotação salva com sucesso!", "success")
        self.painel_galeria.refresh()
        self.painel_kw.refresh()
        self._update_counter()
        self._show_galeria()

    def _update_counter(self):
        self.lbl_count.configure(
            text=f"{len(galeria)} imagem(ns)  ·  {len(palavras_chave)} tag(s)")


# ════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = SnapNoteApp()
    app.mainloop()
