import os
import sys

# Em algumas instalações do Python 3.13 para Windows, o python.exe copiado
# para dentro de um venv (.venv\Scripts\python.exe) erra o cálculo do
# caminho do Tcl/Tk (procura "lib/tcl8.6" em vez de "tcl/tcl8.6"), mesmo
# com o Tcl/Tk instalado corretamente na instalação base. Definir essas
# variáveis explicitamente antes de importar tkinter contorna o problema
# sem exigir nenhuma mudança de ambiente fora do projeto.
if sys.platform == "win32" and not os.environ.get("TCL_LIBRARY"):
    _tcl_dir = os.path.join(sys.base_prefix, "tcl", "tcl8.6")
    _tk_dir  = os.path.join(sys.base_prefix, "tcl", "tk8.6")
    if os.path.isfile(os.path.join(_tcl_dir, "init.tcl")):
        os.environ["TCL_LIBRARY"] = _tcl_dir
    if os.path.isdir(_tk_dir):
        os.environ["TK_LIBRARY"] = _tk_dir

import tkinter as tk
from tkinter import font as tkfont
import cv2
from PIL import Image, ImageTk, ImageDraw
import threading
import shutil
import json
import math
from datetime import datetime

import theme

try:
    import speech_recognition as sr
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

# ── Paleta ────────────────────────────────────────────────────────────────────
BG       = "#0A0A0A"
SURFACE  = "#1C1C1E"
SURFACE2 = "#2C2C2E"
TEXT     = "#F2F2F2"
TEXT_DIM = "#8E8E93"
BORDER   = "#3A3A3C"
DANGER   = "#FF453A"
SUCCESS  = "#30D158"
ICON_DIM = "#D6D6D6"

MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun",
            "jul", "ago", "set", "out", "nov", "dez"]

# GOLD e a família de fonte vêm de theme.py (fonte única de verdade).
# FONT só ganha o valor definitivo dentro de SnapNoteApp.__init__, depois
# que theme.resolve_fonts() roda (precisa de um root do Tk já existente).
GOLD = theme.GOLD
FONT = theme.FONT_FALLBACK
W, H = 390, 780
CONTENT_H = H


# ── App principal ─────────────────────────────────────────────────────────────
class SnapNoteApp:
    def __init__(self):
        self.root = tk.Tk()
        # Precisa de um root já existente para consultar o banco de fontes
        # do Tk, mas roda antes de qualquer widget de interface ser criado.
        theme.resolve_fonts()
        global FONT
        FONT = theme.FONT_REGULAR

        self.root.title("SnapNote")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
        theme.apply_dark_titlebar(self.root)

        # Estado
        self.galeria: list[dict] = []
        self.palavrasChaves: list[str] = []
        self.pastaFotos = os.path.join(os.getcwd(), "fotos_capturadas")
        self.dataFile   = os.path.join(os.getcwd(), "snapnote_data.json")
        os.makedirs(self.pastaFotos, exist_ok=True)

        # Câmera
        self.cap          = None
        self.cam_running  = False
        self.cam_paused   = False
        self.last_frame   = None
        self.captured_path: str | None = None
        self._photo_ref   = None

        # UI refs
        self._thumb_refs        = []
        self.current_screen: str | None = None
        self.gallery_folder     = "Todas"
        self._gallery_search_open = False
        self._popup_open         = False
        self._popup_text_visible = False
        self._mic_recording      = False
        self._popup_pill_w       = 248
        self._popup_pill_h       = 56
        self._popup_rely         = 0.82

        self._load_data()
        self._build_ui()
        self.show_screen("camera")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Persistência ─────────────────────────────────────────────────────────
    def _load_data(self):
        if os.path.exists(self.dataFile):
            try:
                with open(self.dataFile, encoding="utf-8") as f:
                    d = json.load(f)
                self.galeria        = d.get("galeria", [])
                self.palavrasChaves = d.get("palavrasChaves", [])
            except Exception:
                pass
        self._scan_disk()

    def _scan_disk(self):
        # normcase (minúsculas + separadores) evita duplicar a mesma foto
        # quando a letra do drive vem em case diferente do salvo no JSON
        # (ex.: "C:\..." vs "c:\...") — Windows trata isso como o mesmo
        # arquivo, mas comparar como texto puro não.
        known = {os.path.normcase(os.path.normpath(i["imagem"])) for i in self.galeria}
        if os.path.isdir(self.pastaFotos):
            for name in sorted(os.listdir(self.pastaFotos)):
                if name.lower().endswith((".jpg", ".jpeg", ".png")):
                    p = os.path.join(self.pastaFotos, name)
                    if os.path.normcase(os.path.normpath(p)) not in known:
                        self.galeria.append({"imagem": p, "anotacao": ""})

    def _save_data(self):
        try:
            with open(self.dataFile, "w", encoding="utf-8") as f:
                json.dump(
                    {"galeria": self.galeria, "palavrasChaves": self.palavrasChaves},
                    f, ensure_ascii=False, indent=2,
                )
        except Exception:
            pass

    # ── Construção da UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        self.container = tk.Frame(self.root, bg=BG, width=W, height=CONTENT_H)
        self.container.place(x=0, y=0, width=W, height=CONTENT_H)
        self.container.pack_propagate(False)

        self.screens: dict[str, tk.Frame] = {}
        self._build_camera_screen()
        self._build_gallery_screen()
        self._build_annotation_popup()

    def _draw_icon_search(self, cv, color):
        cv.delete("all")
        cv.create_oval(3, 3, 16, 16, outline=color, width=1.5, fill="")
        cv.create_line(14, 14, 23, 23, fill=color, width=1.5)

    # ── Troca de tela ─────────────────────────────────────────────────────────
    def show_screen(self, name: str):
        if self.current_screen == "camera" and name != "camera":
            self._stop_camera()
        for frame in self.screens.values():
            frame.place_forget()
        self.screens[name].place(x=0, y=0, width=W, height=CONTENT_H)
        self.current_screen = name
        if name == "camera":
            self._start_camera()
            self._refresh_camera_thumb()
        elif name == "gallery":
            self._refresh_gallery()

    # ── Tela de câmera ────────────────────────────────────────────────────────
    def _build_camera_screen(self):
        f = tk.Frame(self.container, bg="black")
        self.screens["camera"] = f

        TOP_H, MODE_H, CTRL_H = 48, 40, 110

        # ── Barra superior de ícones (altura fixa) ───────────────────────────
        top = tk.Frame(f, bg="black", height=TOP_H)
        top.pack(fill="x")
        top.pack_propagate(False)

        left_specs = [(self._draw_icon_scan, 0.07), (self._draw_icon_flash_off, 0.17),
                      (self._draw_icon_motion_off, 0.27)]
        for draw_fn, relx in left_specs:
            cv = tk.Canvas(top, width=22, height=22, bg="black", highlightthickness=0)
            cv.place(relx=relx, rely=0.5, anchor="center")
            draw_fn(cv, ICON_DIM)

        tk.Label(top, text=theme.letter_spaced("ZEISS"), font=theme.type_zeiss(),
                 bg="black", fg=GOLD).place(relx=0.5, rely=0.5, anchor="center")

        right_specs = [(self._draw_icon_video_off, 0.73), (self._draw_icon_settings, 0.83)]
        for draw_fn, relx in right_specs:
            cv = tk.Canvas(top, width=22, height=22, bg="black", highlightthickness=0)
            cv.place(relx=relx, rely=0.5, anchor="center")
            draw_fn(cv, ICON_DIM)

        # ── Preview (ocupa todo o espaço restante) ───────────────────────────
        # Empacotado por último (ver final do método): no packer do Tk, o
        # widget com expand=True precisa ser processado depois de todo mundo
        # que reserva espaço fixo, senão ele consome o espaço antes das
        # linhas de baixo existirem e elas ficam com altura zero.
        preview = tk.Frame(f, bg=SURFACE2)

        self.cam_canvas = tk.Canvas(preview, bg=SURFACE2, highlightthickness=0,
                                    cursor="crosshair")
        self.cam_canvas.pack(fill="both", expand=True)
        self.cam_canvas.create_text(
            0, 0, text="Inicializando câmera…",
            fill=TEXT_DIM, font=(FONT, 13), tags="placeholder", anchor="center",
        )
        self.cam_canvas.bind("<Configure>", self._on_cam_canvas_configure)

        # Pill de zoom (overlay, ancorado ao centro/borda inferior do preview)
        zoom_w, zoom_h = 132, 30
        zoom_cv = tk.Canvas(preview, width=zoom_w, height=zoom_h, bg="#1C1C1C",
                            highlightthickness=0)
        zoom_cv.place(relx=0.5, rely=1.0, y=-16, anchor="s")
        self._draw_zoom_selector(zoom_cv, zoom_w, zoom_h)

        # Botão circular extra (overlay, canto inferior direito do preview)
        fx_size = 40
        fx_cv = tk.Canvas(preview, width=fx_size, height=fx_size, bg="#1C1C1C",
                          highlightthickness=0, cursor="hand2")
        fx_cv.place(relx=1.0, rely=1.0, x=-16, y=-16, anchor="se")
        self._draw_icon_fx(fx_cv, fx_size)

        # ── Linha de modos (altura fixa, carrossel rolável) ──────────────────
        # Empacotado com side="bottom" depois de "ctrl" (ver final do método)
        # para reservar a fatia certa antes do preview absorver o resto.
        mode_outer = tk.Frame(f, bg="black", height=MODE_H)
        mode_outer.pack_propagate(False)

        mode_canvas = tk.Canvas(mode_outer, bg="black", highlightthickness=0)
        mode_canvas.pack(fill="both", expand=True)
        mode_inner = tk.Frame(mode_canvas, bg="black")
        mode_canvas.create_window(0, 0, anchor="nw", window=mode_inner)
        mode_inner.bind("<Configure>",
            lambda e: mode_canvas.configure(scrollregion=mode_canvas.bbox("all")))
        mode_canvas.bind("<MouseWheel>",
            lambda e: mode_canvas.xview_scroll(-1 * (e.delta // 120), "units"))

        modes = [("Noite", False), ("Retrato", False), ("Foto", True),
                 ("Vídeo", False), ("Microfilme", False), ("Câmera lenta", False)]
        for idx, (label, active) in enumerate(modes):
            color = GOLD if active else TEXT
            tk.Label(mode_inner, text=label, font=theme.type_mode(active),
                     bg="black", fg=color).pack(
                         side="left", padx=(14 if idx == 0 else 0, 20))

        # ── Linha de controles (altura fixa) ─────────────────────────────────
        ctrl = tk.Frame(f, bg="black", height=CTRL_H)
        ctrl.pack_propagate(False)

        # Miniatura da galeria (canto inferior esquerdo)
        thumb_size = 52
        self.gallery_thumb_btn = tk.Label(ctrl, bg="black", cursor="hand2",
                                          bd=0, highlightthickness=0)
        self.gallery_thumb_btn.place(x=26, rely=0.5, anchor="w",
                                     width=thumb_size, height=thumb_size)
        self.gallery_thumb_btn.bind("<Button-1>", lambda e: self.show_screen("gallery"))
        self._refresh_camera_thumb()

        # Botão de captura (centro)
        self.shutter = tk.Canvas(ctrl, width=76, height=76, bg="black",
                                 highlightthickness=0, cursor="hand2")
        self.shutter.place(relx=0.5, rely=0.5, anchor="center")
        self._draw_shutter()
        self.shutter.bind("<Button-1>", lambda e: self._on_capture())
        self.shutter.bind("<Enter>",    lambda e: self._draw_shutter(hover=True))
        self.shutter.bind("<Leave>",    lambda e: self._draw_shutter(hover=False))

        # Alternar câmera (canto inferior direito)
        flip_cv = tk.Canvas(ctrl, width=44, height=44, bg="black",
                            highlightthickness=0, cursor="hand2")
        flip_cv.place(x=W - 26, rely=0.5, anchor="e")
        self._draw_icon_flip(flip_cv, TEXT)

        # Ordem de empacotamento importa no Tk: side="bottom" reserva as
        # fatias fixas a partir de baixo, e o preview (fill+expand) é
        # empacotado por último para absorver só o que sobrar no meio.
        ctrl.pack(side="bottom", fill="x")
        mode_outer.pack(side="bottom", fill="x")
        preview.pack(fill="both", expand=True)

    def _on_cam_canvas_configure(self, event):
        self.cam_canvas.coords("placeholder", event.width / 2, event.height / 2)

    def _draw_shutter(self, hover=False):
        self.shutter.delete("all")
        size, ring_w, gap = 72, 5, 6
        inner = "#CCCCCC" if hover else "#FFFFFF"
        self.shutter.create_oval(2, 2, size - 2, size - 2,
                                 outline="#FFFFFF", width=ring_w)
        inset = 2 + ring_w + gap
        self.shutter.create_oval(inset, inset, size - inset, size - inset,
                                 fill=inner, outline="")

    # ── Ícones da barra superior / controles (desenhados em canvas) ─────────
    @staticmethod
    def _pill_points(x0, y0, x1, y1, r):
        return [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
                x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
                x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]

    def _draw_zoom_selector(self, cv, w, h):
        cv.delete("all")
        r = h / 2
        cv.create_polygon(self._pill_points(0, 0, w, h, r),
                          smooth=True, fill="#1C1C1C", outline="")
        labels = ["0.6", "1x", "2"]
        seg = w / 3
        for i, label in enumerate(labels):
            cx = seg * i + seg / 2
            if label == "1x":
                cv.create_oval(cx - h/2 + 3, 3, cx + h/2 - 3, h - 3,
                               fill=GOLD, outline="")
                cv.create_text(cx, h / 2, text=label,
                               fill="black", font=theme.type_zoom(True))
            else:
                cv.create_text(cx, h / 2, text=label,
                               fill=TEXT, font=theme.type_zoom(False))

    def _draw_icon_scan(self, cv, color):
        cv.delete("all")
        L = 6
        corners = [(2, 2), (22, 2), (2, 22), (22, 22)]
        for x, y in corners:
            cv.create_line(x, y, x + L * (1 if x < 12 else -1), y, fill=color, width=1.6)
            cv.create_line(x, y, x, y + L * (1 if y < 12 else -1), fill=color, width=1.6)
        cv.create_oval(9, 9, 15, 15, outline=color, width=1.4)

    def _draw_icon_flash_off(self, cv, color):
        cv.delete("all")
        cv.create_line(13, 2, 6, 14, fill=color, width=1.4)
        cv.create_line(6, 14, 12, 14, fill=color, width=1.4)
        cv.create_line(12, 14, 9, 23, fill=color, width=1.4)
        cv.create_line(9, 23, 19, 11, fill=color, width=1.4)
        cv.create_line(19, 11, 13, 11, fill=color, width=1.4)
        cv.create_line(13, 11, 13, 2, fill=color, width=1.4)
        cv.create_line(2, 2, 23, 23, fill=color, width=1.4)

    def _draw_icon_motion_off(self, cv, color):
        cv.delete("all")
        cv.create_oval(3, 3, 21, 21, outline=color, width=1.4)
        cv.create_oval(9, 9, 15, 15, outline=color, width=1.4)
        cv.create_line(3, 21, 21, 3, fill=color, width=1.4)

    def _draw_icon_video_off(self, cv, color):
        cv.delete("all")
        cv.create_rectangle(2, 7, 16, 18, outline=color, width=1.4)
        cv.create_polygon(16, 10, 22, 6, 22, 19, 16, 15, fill="", outline=color, width=1.4)
        cv.create_line(2, 2, 22, 22, fill=color, width=1.4)

    def _draw_icon_settings(self, cv, color):
        cv.delete("all")
        cx, cy, r_out, r_in, n = 11, 11, 8, 5, 8
        pts = []
        for i in range(n * 2):
            ang = math.radians(i * (360 / (n * 2)))
            rad = r_out if i % 2 == 0 else r_out - 2.4
            pts.extend((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
        cv.create_polygon(pts, outline=color, fill="", width=1.3)
        cv.create_oval(cx - r_in, cy - r_in, cx + r_in, cy + r_in, outline=color, width=1.3)

    def _draw_icon_flip(self, cv, color):
        cv.delete("all")
        size = 44
        cv.create_oval(2, 2, size - 2, size - 2, fill="#2C2C2E", outline="")
        cv.create_arc(7, 7, 37, 37, start=25, extent=130,
                     style="arc", outline=color, width=2.2)
        cv.create_arc(7, 7, 37, 37, start=205, extent=130,
                     style="arc", outline=color, width=2.2)
        cv.create_polygon(32, 9, 37, 11, 33, 17, fill=color, outline="")
        cv.create_polygon(12, 35, 7, 33, 11, 28, fill=color, outline="")

    def _draw_icon_fx(self, cv, size):
        cv.delete("all")
        cv.create_oval(2, 2, size - 2, size - 2, fill="#1C1C1C", outline="")
        s = size / 40
        def pt(x, y):
            return (x - 12) * s + size / 2, (y - 12) * s + size / 2
        path = [(13, 2), (6, 14), (12, 14), (9, 23), (19, 11), (13, 11), (13, 2)]
        for (x0, y0), (x1, y1) in zip(path, path[1:]):
            cv.create_line(*pt(x0, y0), *pt(x1, y1), fill=TEXT, width=1.6)
        cv.create_line(*pt(2, 2), *pt(23, 23), fill=TEXT, width=1.6)

    def _rounded_photo(self, img: Image.Image, size: int, radius: int = 10):
        return self._rounded_image(img, size, size, radius)

    def _rounded_image(self, img: Image.Image, w: int, h: int, radius: int = 10):
        img = img.convert("RGBA").resize((w, h), Image.LANCZOS)
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
        img.putalpha(mask)
        return ImageTk.PhotoImage(img)

    # ── Botões e ícones reutilizáveis (galeria / diálogos) ───────────────────
    def _make_pill_button(self, parent, text, bg, fg, command,
                          w=140, h=40, font_size=11, bold=True):
        cv = tk.Canvas(parent, width=w, height=h, bg=parent["bg"],
                       highlightthickness=0, cursor="hand2")
        r = h / 2
        cv.create_polygon(self._pill_points(0, 0, w, h, r),
                          smooth=True, fill=bg, outline="")
        cv.create_text(w / 2, h / 2, text=text, fill=fg,
                       font=(FONT, font_size, "bold" if bold else "normal"))
        cv.bind("<Button-1>", lambda e: command())
        return cv

    def _make_circle_button(self, parent, size, draw_icon_fn, command=None,
                            bg=None, hover_bg=None):
        bg = bg if bg is not None else parent["bg"]
        hover_bg = hover_bg if hover_bg is not None else bg
        cv = tk.Canvas(parent, width=size, height=size, bg=parent["bg"],
                       highlightthickness=0, cursor="hand2")

        def render(circle_color):
            cv.delete("all")
            draw_icon_fn(cv)
            bbox = cv.bbox("all")
            if bbox:
                bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
                dx = (size - bw) / 2 - bbox[0]
                dy = (size - bh) / 2 - bbox[1]
                cv.move("all", dx, dy)
            cv.create_oval(1, 1, size - 1, size - 1, fill=circle_color,
                          outline="", tags="bg")
            cv.tag_lower("bg")

        render(bg)
        if command:
            cv.bind("<Button-1>", lambda e: command())
        cv.bind("<Enter>", lambda e: render(hover_bg))
        cv.bind("<Leave>", lambda e: render(bg))
        return cv

    def _draw_icon_chevron_left(self, cv, color):
        cv.delete("all")
        cv.create_line(14, 3, 7, 11, fill=color, width=1.8, capstyle="round")
        cv.create_line(7, 11, 14, 19, fill=color, width=1.8, capstyle="round")

    def _draw_icon_dots_vertical(self, cv, color):
        cv.delete("all")
        for cy in (6, 11, 16):
            cv.create_oval(9.4, cy - 1.6, 12.6, cy + 1.6, fill=color, outline="")

    def _draw_icon_plus(self, cv, color):
        cv.delete("all")
        cv.create_line(11, 4, 11, 18, fill=color, width=1.8, capstyle="round")
        cv.create_line(4, 11, 18, 11, fill=color, width=1.8, capstyle="round")

    def _draw_icon_tag(self, cv, color):
        cv.delete("all")
        cv.create_polygon(3, 4, 11, 4, 19, 12, 11, 20, 3, 12,
                          outline=color, fill="", width=1.4, joinstyle="round")
        cv.create_oval(13, 6, 16, 9, outline=color, width=1.2)

    def _draw_icon_trash(self, cv, color):
        cv.delete("all")
        cv.create_line(4, 6, 18, 6, fill=color, width=1.5, capstyle="round")
        cv.create_line(8.5, 6, 9, 3.5, fill=color, width=1.3)
        cv.create_line(13.5, 6, 13, 3.5, fill=color, width=1.3)
        cv.create_line(9, 3.5, 13, 3.5, fill=color, width=1.3)
        cv.create_rectangle(5.5, 6, 16.5, 19, outline=color, width=1.4)
        for x in (8.5, 11, 13.5):
            cv.create_line(x, 9, x, 16, fill=color, width=1.1)

    def _draw_icon_gallery_empty(self, cv, color):
        cv.delete("all")
        cv.create_rectangle(3, 6, 33, 30, outline=color, width=1.6)
        cv.create_oval(9, 12, 15, 18, outline=color, width=1.4)
        cv.create_line(3, 26, 14, 17, 21, 23, 27, 18, 33, 24,
                       fill=color, width=1.6, smooth=True)

    def _refresh_camera_thumb(self):
        if not hasattr(self, "gallery_thumb_btn"):
            return
        latest = self.captured_path if self.captured_path and os.path.exists(self.captured_path) else None
        if not latest:
            for item in reversed(self.galeria):
                if os.path.exists(item["imagem"]):
                    latest = item["imagem"]
                    break
        if not latest and os.path.isdir(self.pastaFotos):
            files = [os.path.join(self.pastaFotos, n) for n in os.listdir(self.pastaFotos)
                     if n.lower().endswith((".jpg", ".jpeg", ".png"))]
            if files:
                latest = max(files, key=os.path.getmtime)
        size = 52
        if latest:
            try:
                img = Image.open(latest)
                ew, eh = img.size
                m = min(ew, eh)
                img = img.crop(((ew - m) // 2, (eh - m) // 2,
                                (ew + m) // 2, (eh + m) // 2))
                ref = self._rounded_photo(img, size, radius=8)
                self.gallery_thumb_btn.configure(image=ref, bg="black")
                self.gallery_thumb_btn._ref = ref
                return
            except Exception:
                pass
        ref = self._rounded_photo(Image.new("RGB", (size, size), SURFACE2), size, radius=8)
        self.gallery_thumb_btn.configure(image=ref, bg="black")
        self.gallery_thumb_btn._ref = ref

    # ── Câmera: captura de frame ──────────────────────────────────────────────
    def _start_camera(self):
        if self.cam_running:
            return
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.cam_canvas.itemconfig("placeholder",
                                       text="Câmera não encontrada", fill=DANGER)
            return
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cam_running = True
        self.cam_canvas.delete("placeholder")
        threading.Thread(target=self._cam_loop, daemon=True).start()
        self._schedule_cam()

    def _stop_camera(self):
        self.cam_running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        self.last_frame = None

    def _cam_loop(self):
        while self.cam_running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self.last_frame = cv2.flip(frame, 1)

    def _schedule_cam(self):
        if not self.cam_running:
            return
        if not self.cam_paused:
            self._draw_cam_frame()
        self.root.after(33, self._schedule_cam)

    def _draw_cam_frame(self):
        if self.last_frame is None:
            return
        cw, ch = self.cam_canvas.winfo_width(), self.cam_canvas.winfo_height()
        if cw < 2 or ch < 2:
            return
        fh, fw = self.last_frame.shape[:2]
        scale  = max(cw / fw, ch / fh)
        nw, nh = int(fw * scale), int(fh * scale)
        rgb    = cv2.cvtColor(self.last_frame, cv2.COLOR_BGR2RGB)
        img    = Image.fromarray(rgb).resize((nw, nh), Image.BILINEAR)
        x0     = (nw - cw) // 2
        y0     = (nh - ch) // 2
        img    = img.crop((x0, y0, x0 + cw, y0 + ch))
        self._photo_ref = ImageTk.PhotoImage(img)
        self.cam_canvas.delete("frame")
        self.cam_canvas.create_image(0, 0, image=self._photo_ref,
                                     anchor="nw", tags="frame")

    def _on_capture(self):
        if self.last_frame is None:
            return
        frame = self.last_frame.copy()
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        path  = os.path.join(self.pastaFotos, f"snapnote_{ts}.jpg")
        cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        self.captured_path = path
        self._flash()
        self._show_annotation_popup()
        self._refresh_camera_thumb()

    def _flash(self):
        flash = tk.Frame(self.screens["camera"], bg="white")
        flash.place(x=0, y=0, width=W, height=CONTENT_H)
        self.root.update()
        self.root.after(110, flash.destroy)

    # ── Annotation popup (modal flutuante) ────────────────────────────────────
    def _build_annotation_popup(self):
        # Fundo escurecido (usa a própria foto capturada, com brilho reduzido)
        self.popup_backdrop = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.popup_backdrop.bind("<Button-1>",
            lambda e: self._save_annotation_with_text(self.annot_entry.get().strip()))

        # Pill com os 5 ícones (recorte, lápis, hashtag, compartilhar, mic)
        self.popup_pill = tk.Canvas(self.root, width=self._popup_pill_w,
                                    height=self._popup_pill_h, bg=BG,
                                    highlightthickness=0)
        self._draw_popup_pill()

        for idx, handler in ((1, self._toggle_popup_text), (4, self._record_audio)):
            tag = f"hit_{idx}"
            self.popup_pill.tag_bind(tag, "<Button-1>", lambda e, h=handler: h())
            self.popup_pill.tag_bind(tag, "<Enter>",
                lambda e: self.popup_pill.configure(cursor="hand2"))
            self.popup_pill.tag_bind(tag, "<Leave>",
                lambda e: self.popup_pill.configure(cursor=""))

        # Bloco de texto (revelado ao tocar no lápis)
        self.popup_text_frame = tk.Frame(self.root, bg=SURFACE2,
                                         highlightbackground=BORDER,
                                         highlightthickness=1)

        self.annot_entry = tk.Entry(
            self.popup_text_frame, font=(FONT, 12), bg=SURFACE2, fg=TEXT,
            insertbackground=TEXT, relief="flat", bd=0,
        )
        self.annot_entry.place(x=12, y=8, width=self._popup_pill_w - 12 - 46, height=32)
        self.annot_entry.bind("<Return>", lambda e: self._confirm_popup_text())

        self.popup_confirm_cv = tk.Canvas(self.popup_text_frame, width=34, height=34,
                                          bg=SURFACE2, highlightthickness=0,
                                          cursor="hand2")
        self.popup_confirm_cv.place(relx=1.0, x=-10, rely=0.5, anchor="e")
        self._draw_confirm_check(self.popup_confirm_cv)
        self.popup_confirm_cv.bind("<Button-1>", lambda e: self._confirm_popup_text())

    def _draw_popup_backdrop(self):
        cv = self.popup_backdrop
        cv.delete("all")
        src = None
        if self.last_frame is not None:
            rgb = cv2.cvtColor(self.last_frame, cv2.COLOR_BGR2RGB)
            src = Image.fromarray(rgb)
        elif self.captured_path and os.path.exists(self.captured_path):
            src = Image.open(self.captured_path)
        if src is not None:
            fw, fh = src.size
            scale  = max(W / fw, H / fh)
            nw, nh = int(fw * scale), int(fh * scale)
            img    = src.resize((nw, nh), Image.BILINEAR)
            x0, y0 = (nw - W) // 2, (nh - H) // 2
            img    = img.crop((x0, y0, x0 + W, y0 + H)).convert("RGB")
            img    = img.point(lambda p: int(p * 0.35))
            self._popup_bg_ref = ImageTk.PhotoImage(img)
            cv.create_image(0, 0, image=self._popup_bg_ref, anchor="nw")
        else:
            cv.create_rectangle(0, 0, W, H, fill=BG, outline="")

    def _draw_popup_pill(self):
        cv = self.popup_pill
        cv.delete("all")
        w, h = self._popup_pill_w, self._popup_pill_h
        r = h / 2
        cv.create_polygon(self._pill_points(0, 0, w, h, r),
                          smooth=True, fill=SURFACE2, outline="")

        slots = w / 5
        y = h / 2
        for i in range(5):
            cx = slots * i + slots / 2
            cv.create_rectangle(cx - slots / 2, 0, cx + slots / 2, h,
                                fill="", outline="", tags=(f"hit_{i}",))

        self._draw_popup_icon_crop(slots * 0 + slots / 2, y)
        self._draw_popup_icon_pencil(slots * 1 + slots / 2, y)
        self._draw_popup_icon_hashtag(slots * 2 + slots / 2, y)
        self._draw_popup_icon_share(slots * 3 + slots / 2, y)
        mic_color = DANGER if self._mic_recording else ICON_DIM
        self._draw_popup_icon_mic(slots * 4 + slots / 2, y, mic_color)

    def _draw_popup_icon_crop(self, cx, cy):
        cv, c = self.popup_pill, ICON_DIM
        cv.create_line(cx - 5, cy - 9, cx - 5, cy + 6, fill=c, width=1.6)
        cv.create_line(cx - 9, cy - 5, cx + 6, cy - 5, fill=c, width=1.6)
        cv.create_line(cx + 5, cy - 6, cx + 5, cy + 9, fill=c, width=1.6)
        cv.create_line(cx - 6, cy + 5, cx + 9, cy + 5, fill=c, width=1.6)

    def _draw_popup_icon_pencil(self, cx, cy):
        cv, c = self.popup_pill, ICON_DIM
        ox, oy = cx - 12, cy - 12
        pts = [(15, 5), (19, 9), (9, 19), (5, 19), (5, 15)]
        flat = [coord for x, y in pts for coord in (ox + x, oy + y)]
        cv.create_polygon(flat, fill=c, outline="")

    def _draw_popup_icon_hashtag(self, cx, cy):
        cv, c = self.popup_pill, ICON_DIM
        cv.create_line(cx - 3, cy - 8, cx - 3, cy + 8, fill=c, width=1.6)
        cv.create_line(cx + 3, cy - 8, cx + 3, cy + 8, fill=c, width=1.6)
        cv.create_line(cx - 8, cy - 3, cx + 8, cy - 3, fill=c, width=1.6)
        cv.create_line(cx - 8, cy + 3, cx + 8, cy + 3, fill=c, width=1.6)

    def _draw_popup_icon_share(self, cx, cy):
        cv, c = self.popup_pill, ICON_DIM
        cv.create_oval(cx + 2, cy - 9, cx + 8, cy - 3, outline=c, width=1.4)
        cv.create_oval(cx + 2, cy + 3, cx + 8, cy + 9, outline=c, width=1.4)
        cv.create_oval(cx - 9, cy - 3, cx - 3, cy + 3, outline=c, width=1.4)
        cv.create_line(cx - 4, cy - 2, cx + 3, cy - 6, fill=c, width=1.3)
        cv.create_line(cx - 4, cy + 2, cx + 3, cy + 6, fill=c, width=1.3)

    def _draw_popup_icon_mic(self, cx, cy, color):
        cv = self.popup_pill
        bw, bh = 8, 13
        x0, y0 = cx - bw / 2, cy - 9
        x1, y1 = cx + bw / 2, y0 + bh
        cv.create_polygon(self._pill_points(x0, y0, x1, y1, bw / 2),
                          smooth=True, fill=color, outline="")
        cv.create_arc(cx - 8, cy - 3, cx + 8, cy + 9, start=200, extent=140,
                      style="arc", outline=color, width=1.5)
        cv.create_line(cx, cy + 7, cx, cy + 10, fill=color, width=1.5,
                       capstyle="round")
        cv.create_line(cx - 4, cy + 10, cx + 4, cy + 10, fill=color, width=1.5,
                       capstyle="round")

    def _draw_confirm_check(self, cv):
        cv.delete("all")
        cv.create_oval(2, 2, 32, 32, fill=GOLD, outline="")
        cv.create_line(10, 17, 14, 22, fill="black", width=2.4, capstyle="round")
        cv.create_line(14, 22, 24, 10, fill="black", width=2.4, capstyle="round")

    def _show_annotation_popup(self):
        if self._popup_open:
            return
        self._popup_open = True
        self.cam_paused  = True
        self._popup_text_visible = False
        self._mic_recording      = False
        self.annot_entry.delete(0, "end")
        self.popup_text_frame.place_forget()

        self._draw_popup_backdrop()
        self._draw_popup_pill()

        self.popup_backdrop.place(x=0, y=0, width=W, height=H)
        self.popup_pill.place(relx=0.5, rely=self._popup_rely, anchor="center")

    def _hide_annotation_popup(self):
        self.popup_pill.place_forget()
        self.popup_text_frame.place_forget()
        self.popup_backdrop.place_forget()
        self._popup_open = False
        self.cam_paused  = False

    def _toggle_popup_text(self):
        if self._popup_text_visible:
            self.annot_entry.focus_set()
            return
        self._popup_text_visible = True
        pill_top = int(H * self._popup_rely) - self._popup_pill_h // 2
        self.popup_text_frame.place(relx=0.5, y=pill_top - 12, anchor="s",
                                    width=self._popup_pill_w, height=48)
        self.popup_text_frame.tkraise()
        self.annot_entry.focus_set()

    def _confirm_popup_text(self):
        self._save_annotation_with_text(self.annot_entry.get().strip())

    def _save_annotation_with_text(self, text: str):
        if self.captured_path:
            self.galeria.append({"imagem": self.captured_path, "anotacao": text})
            for kw in self.palavrasChaves:
                if kw.lower() in text.lower():
                    folder = os.path.join(os.getcwd(), kw)
                    os.makedirs(folder, exist_ok=True)
                    dest   = os.path.join(folder, os.path.basename(self.captured_path))
                    try:
                        shutil.copy2(self.captured_path, dest)
                    except Exception:
                        pass
            self._save_data()
        self.captured_path = None
        self._hide_annotation_popup()
        self._refresh_camera_thumb()

    def _record_audio(self):
        if not AUDIO_AVAILABLE or self._mic_recording:
            return
        self._mic_recording = True
        self._draw_popup_pill()

        def run():
            try:
                rec = sr.Recognizer()
                with sr.Microphone() as src:
                    rec.adjust_for_ambient_noise(src, duration=0.5)
                    audio = rec.listen(src, timeout=6, phrase_time_limit=12)
                text = rec.recognize_google(audio, language="pt-BR")
                self.root.after(0, lambda: self._save_annotation_with_text(text))
            except Exception:
                pass
            finally:
                self._mic_recording = False
                self.root.after(0, self._draw_popup_pill)

        threading.Thread(target=run, daemon=True).start()

    # ── Tela de galeria ───────────────────────────────────────────────────────
    def _build_gallery_screen(self):
        f = tk.Frame(self.container, bg=BG)
        self.screens["gallery"] = f

        # Grid ocupa a tela inteira; as ilhas flutuam por cima, sem reservar
        # uma faixa fixa de cabeçalho — igual ao modelo de referência.
        grid_frame = tk.Frame(f, bg=BG)
        grid_frame.place(x=0, y=0, width=W, height=H)

        self.gal_canvas = tk.Canvas(grid_frame, bg=BG, highlightthickness=0, bd=0)
        self.gal_canvas.pack(fill="both", expand=True)

        self.gal_inner = tk.Frame(self.gal_canvas, bg=BG)
        self._gal_win  = self.gal_canvas.create_window(
            0, 0, anchor="nw", window=self.gal_inner)

        self.gal_inner.bind("<Configure>",
            lambda e: self.gal_canvas.configure(
                scrollregion=self.gal_canvas.bbox("all")))
        self._bind_wheel(self.gal_canvas)
        self._bind_wheel(self.gal_inner)

        # Ilha flutuante: voltar (canto superior esquerdo)
        back_btn = self._make_circle_button(
            f, 38, lambda cv: self._draw_icon_chevron_left(cv, TEXT),
            command=lambda: self.show_screen("camera"), bg=SURFACE2, hover_bg=SURFACE)
        back_btn.place(x=12, y=14)

        # Ilha flutuante: busca + menu (canto superior direito)
        self._build_top_island(f)

        # Barra de busca (some por baixo da ilha do topo, oculta por padrão)
        sb_w, sb_h = W - 32, 44
        self._gallery_search_wrap = tk.Canvas(f, width=sb_w, height=sb_h, bg=BG,
                                              highlightthickness=0)

        self._gallery_search_wrap.create_polygon(
            self._pill_points(0, 0, sb_w, sb_h, sb_h / 2),
            smooth=True, fill=SURFACE2, outline="")
        self._gallery_search_wrap.create_oval(16, 14, 26, 24, outline=TEXT_DIM, width=1.5)
        self._gallery_search_wrap.create_line(24, 22, 30, 28, fill=TEXT_DIM, width=1.5)

        self.gal_search_entry = tk.Entry(
            self._gallery_search_wrap, font=(FONT, 11), bg=SURFACE2, fg=TEXT,
            insertbackground=TEXT, relief="flat", bd=0, highlightthickness=0,
        )
        self._gallery_search_wrap.create_window(
            40, sb_h / 2, anchor="w", window=self.gal_search_entry,
            width=sb_w - 40 - 36)
        self.gal_search_entry.bind("<KeyRelease>", lambda e: self._render_grid())

        cx, cy = sb_w - 22, sb_h / 2
        self._gallery_search_wrap.create_line(cx - 5, cy - 5, cx + 5, cy + 5,
                                              fill=TEXT_DIM, width=1.5, tags="close")
        self._gallery_search_wrap.create_line(cx - 5, cy + 5, cx + 5, cy - 5,
                                              fill=TEXT_DIM, width=1.5, tags="close")
        self._gallery_search_wrap.create_rectangle(cx - 14, 0, cx + 14, sb_h,
                                                    fill="", outline="", tags="close")
        self._gallery_search_wrap.tag_bind(
            "close", "<Button-1>", lambda e: self._toggle_gallery_search(force_close=True))
        self._gallery_search_wrap.tag_bind(
            "close", "<Enter>", lambda e: self._gallery_search_wrap.configure(cursor="hand2"))
        self._gallery_search_wrap.tag_bind(
            "close", "<Leave>", lambda e: self._gallery_search_wrap.configure(cursor=""))

        # Ilha flutuante: palavras-chave (inferior, centralizada)
        self._kw_island = tk.Canvas(f, bg=BG, highlightthickness=0)
        self._kw_island.place(relx=0.5, rely=1.0, y=-14, anchor="s")

    def _build_top_island(self, parent):
        island_w, island_h = 84, 40
        cv = tk.Canvas(parent, width=island_w, height=island_h, bg=BG,
                       highlightthickness=0)
        cv.place(relx=1.0, x=-12, y=14, anchor="ne")
        cv.create_polygon(self._pill_points(0, 0, island_w, island_h, island_h / 2),
                          smooth=True, fill=SURFACE2, outline="")

        search_cv = tk.Canvas(cv, width=22, height=22, bg=SURFACE2,
                              highlightthickness=0, cursor="hand2")
        self._draw_icon_search(search_cv, TEXT)
        cv.create_window(island_h / 2, island_h / 2, window=search_cv)
        search_cv.bind("<Button-1>", lambda e: self._toggle_gallery_search())

        menu_cv = tk.Canvas(cv, width=22, height=22, bg=SURFACE2,
                            highlightthickness=0, cursor="hand2")
        self._draw_icon_dots_vertical(menu_cv, TEXT)
        cv.create_window(island_w - island_h / 2, island_h / 2, window=menu_cv)
        menu_cv.bind("<Button-1>", lambda e: self._show_gallery_menu(None))

    def _bind_wheel(self, widget):
        widget.bind("<MouseWheel>",
                    lambda e: self.gal_canvas.yview_scroll(-1 * (e.delta // 120), "units"))

    def _refresh_gallery(self):
        self._redraw_keywords_island()
        self._render_grid()

    def _toggle_gallery_search(self, force_close: bool = False):
        if self._gallery_search_open or force_close:
            self._gallery_search_wrap.place_forget()
            self._gallery_search_open = False
            self.gal_search_entry.delete(0, "end")
        else:
            self._gallery_search_wrap.place(relx=1.0, x=-12, y=62, anchor="ne")
            self._gallery_search_open = True
            self.gal_search_entry.focus_set()
        self._render_grid()

    def _redraw_keywords_island(self):
        cv = self._kw_island
        cv.delete("all")

        folders = ["Todas"] + self.palavrasChaves
        fnt     = tkfont.Font(family=FONT, size=10, weight="bold")
        seg_w   = max(70, max(fnt.measure(fo) for fo in folders) + 34)
        island_h = 58
        island_w = min(W - 24, seg_w * len(folders))
        cv.configure(width=island_w, height=island_h)
        cv.create_polygon(self._pill_points(0, 0, island_w, island_h, island_h / 2),
                          smooth=True, fill=SURFACE2, outline="")

        seg = island_w / len(folders)
        for i, folder in enumerate(folders):
            active = folder == self.gallery_folder
            cx = seg * i + seg / 2
            tag = f"kwseg{i}"
            if active:
                pad = 6
                cv.create_polygon(
                    self._pill_points(cx - seg / 2 + pad, pad,
                                      cx + seg / 2 - pad, island_h - pad,
                                      (island_h - 2 * pad) / 2),
                    smooth=True, fill=GOLD, outline="", tags=tag)
                fg = "#1A1400"
            else:
                fg = TEXT_DIM
            cv.create_text(cx, island_h / 2, text=folder, fill=fg,
                           font=(FONT, 10, "bold" if active else "normal"), tags=tag)
            cv.create_rectangle(cx - seg / 2, 0, cx + seg / 2, island_h,
                                fill="", outline="", tags=tag)
            cv.tag_bind(tag, "<Button-1>", lambda e, fo=folder: self._select_tab(fo))

    def _select_tab(self, folder: str):
        self.gallery_folder = folder
        self._refresh_gallery()

    def _parse_capture_dt(self, path: str):
        name = os.path.basename(path)
        try:
            stem = name.rsplit(".", 1)[0]
            ts_part = stem.split("_", 1)[1]
            return datetime.strptime(ts_part, "%Y%m%d_%H%M%S")
        except Exception:
            return None

    def _format_date_header(self, dt) -> str:
        return f"{dt.day} de {MESES_PT[dt.month - 1]}."

    def _render_grid(self):
        for w in self.gal_inner.winfo_children():
            w.destroy()
        self._thumb_refs = []

        images = self._get_folder_images()
        query = self.gal_search_entry.get().strip().lower() if self._gallery_search_open else ""
        if query:
            images = [i for i in images if query in i.get("anotacao", "").lower()]

        images.sort(key=lambda i: self._parse_capture_dt(i["imagem"]) or datetime.min,
                   reverse=True)

        if not images:
            empty = tk.Frame(self.gal_inner, bg=BG, pady=70)
            empty.pack(fill="x")
            tk.Frame(empty, bg=BG, height=40).pack()
            icon_cv = tk.Canvas(empty, width=36, height=36, bg=BG,
                                highlightthickness=0)
            icon_cv.pack()
            self._draw_icon_gallery_empty(icon_cv, TEXT_DIM)
            msg = "Nenhum resultado" if query else "Nenhuma foto ainda"
            tk.Label(empty, text=msg, font=(FONT, 12), bg=BG, fg=TEXT_DIM,
                     pady=10).pack()
            return

        # Atualiza largura interna
        self.gal_canvas.itemconfig(self._gal_win, width=W)

        ncols   = 3
        thumb_w = W // ncols
        thumb_h = thumb_w
        cap_h   = 32
        cell_h  = thumb_h + cap_h

        last_date_label = None
        row_frame = None
        col = 0
        for item in images:
            dt = self._parse_capture_dt(item["imagem"])
            date_label = self._format_date_header(dt) if dt else "Sem data"

            if date_label != last_date_label:
                hdr = tk.Frame(self.gal_inner, bg=BG)
                hdr.pack(fill="x")
                self._bind_wheel(hdr)
                top_pad = 60 if last_date_label is None else 20
                tk.Label(hdr, text=date_label, font=(FONT, 13, "bold"),
                         bg=BG, fg=TEXT, anchor="w").pack(
                             fill="x", padx=14, pady=(top_pad, 8))
                last_date_label = date_label
                row_frame = None
                col = 0

            if col == 0:
                row_frame = tk.Frame(self.gal_inner, bg=BG)
                row_frame.pack(fill="x")
                self._bind_wheel(row_frame)

            cell = tk.Frame(row_frame, bg=BG, width=thumb_w, height=cell_h,
                            cursor="hand2")
            cell.pack(side="left")
            cell.pack_propagate(False)
            self._bind_wheel(cell)

            img_lbl = tk.Label(cell, bg=SURFACE2, cursor="hand2")
            img_lbl.place(x=0, y=0, width=thumb_w, height=thumb_h)
            self._load_thumb(item["imagem"], img_lbl, thumb_w, thumb_h, radius=0)
            self._bind_wheel(img_lbl)

            path  = item["imagem"]
            annot = item.get("anotacao", "")
            cap_text = (annot[:18] + "…") if len(annot) > 18 else annot
            cap_lbl = tk.Label(cell, text=cap_text or "Sem legenda", font=(FONT, 7),
                               bg=BG, fg=TEXT_DIM if annot else "#3A3A3C",
                               anchor="w")
            cap_lbl.place(x=3, y=thumb_h + 3, width=thumb_w - 6, height=cap_h - 4)
            self._bind_wheel(cap_lbl)

            for widget in (cell, img_lbl, cap_lbl):
                widget.bind("<Button-1>",
                    lambda e, p=path, a=annot: self._open_detail(p, a))

            col = (col + 1) % ncols

        # Espaçador final para poder rolar as últimas fotos para além da
        # ilha de palavras-chave, que flutua fixa na parte inferior.
        tk.Frame(self.gal_inner, bg=BG, height=88).pack(fill="x")

    def _get_folder_images(self) -> list[dict]:
        if self.gallery_folder == "Todas":
            return [i for i in self.galeria if os.path.exists(i["imagem"])]
        folder = os.path.join(os.getcwd(), self.gallery_folder)
        if not os.path.isdir(folder):
            return []
        result = []
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith((".jpg", ".jpeg", ".png")):
                p     = os.path.join(folder, name)
                annot = next(
                    (i.get("anotacao", "") for i in self.galeria
                     if os.path.basename(i["imagem"]) == name),
                    "",
                )
                result.append({"imagem": p, "anotacao": annot})
        return result

    def _load_thumb(self, path: str, label: tk.Label, w: int, h: int, radius: int = 16):
        try:
            img = Image.open(path)
            ew, eh = img.size
            m   = min(ew, eh)
            img = img.crop(((ew - m) // 2, (eh - m) // 2,
                            (ew + m) // 2, (eh + m) // 2))
            ref = self._rounded_image(img, w, h, radius=radius)
            self._thumb_refs.append(ref)
            label.configure(image=ref)
        except Exception:
            label.configure(text="?", fg=TEXT_DIM, font=(FONT, 20))

    # ── Detalhe da imagem ─────────────────────────────────────────────────────
    def _format_capture_meta(self, path: str) -> str:
        dt = self._parse_capture_dt(path)
        if dt:
            return dt.strftime("%d/%m/%Y às %H:%M")
        return os.path.basename(path)

    def _open_detail(self, path: str, annotation: str):
        win = tk.Toplevel(self.root)
        win.title("SnapNote")
        win.geometry(f"{W}x{CONTENT_H}+{self.root.winfo_x()}+{self.root.winfo_y()}")
        win.configure(bg=BG)
        win.resizable(False, False)
        theme.apply_dark_titlebar(win)
        win.grab_set()
        win.bind("<Escape>", lambda e: win.destroy())

        # Header
        header = tk.Frame(win, bg=BG, height=54)
        header.pack(fill="x")
        header.pack_propagate(False)
        back_btn = self._make_circle_button(
            header, 36, lambda cv: self._draw_icon_chevron_left(cv, TEXT),
            command=win.destroy, bg=BG, hover_bg=SURFACE2)
        back_btn.place(x=10, rely=0.5, anchor="w")
        tk.Label(header, text="Detalhes", font=(FONT, 13, "bold"),
                 bg=BG, fg=TEXT).place(relx=0.5, rely=0.5, anchor="center")

        # Imagem (cantos arredondados)
        img_wrap = tk.Frame(win, bg=BG)
        img_wrap.pack(fill="x", padx=16)
        try:
            img = Image.open(path)
            img.thumbnail((W - 32, W - 32))
            ref      = self._rounded_image(img, img.width, img.height, radius=18)
            win._ref = ref
            tk.Label(img_wrap, image=ref, bg=BG).pack()
        except Exception:
            tk.Label(img_wrap, text="Imagem inválida", bg=SURFACE, fg=TEXT_DIM,
                     font=(FONT, 12), pady=40).pack(fill="x")

        # Anotação
        annot_frame = tk.Frame(win, bg=SURFACE, padx=20, pady=16)
        annot_frame.pack(fill="x", padx=16, pady=16)
        tk.Label(annot_frame, text="ANOTAÇÃO", font=(FONT, 9, "bold"),
                 bg=SURFACE, fg=GOLD).pack(anchor="w")
        msg = annotation if annotation else "Sem anotação"
        tk.Label(annot_frame, text=msg, font=(FONT, 11),
                 bg=SURFACE, fg=TEXT if annotation else TEXT_DIM,
                 wraplength=W - 72, justify="left", anchor="w").pack(
                     fill="x", pady=(6, 0))

        tk.Label(win, text=self._format_capture_meta(path), font=(FONT, 8),
                 bg=BG, fg=TEXT_DIM, padx=20, pady=6).pack(anchor="w")

    # ── Menu ⋮ da galeria ─────────────────────────────────────────────────────
    def _show_gallery_menu(self, event=None):
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.configure(bg=BG)

        menu_w, row_h = 236, 50
        options = [
            (self._draw_icon_plus, "Nova palavra-chave",    self._add_keyword),
            (self._draw_icon_tag,  "Gerenciar palavras-chave", self._manage_keywords),
        ]
        total_h = row_h * len(options) + 8
        mx = self.root.winfo_x() + W - menu_w - 12
        my = self.root.winfo_y() + 62
        popup.geometry(f"{menu_w}x{total_h}+{mx}+{my}")

        cv = tk.Canvas(popup, width=menu_w, height=total_h, bg=BG,
                       highlightthickness=0)
        cv.pack(fill="both", expand=True)
        cv.create_polygon(self._pill_points(0, 0, menu_w, total_h, 16),
                          smooth=True, fill=SURFACE2, outline=BORDER)

        for i, (icon_fn, label, cmd) in enumerate(options):
            y0, y1 = 4 + i * row_h, 4 + (i + 1) * row_h
            tag = f"row{i}"
            cv.create_rectangle(2, y0, menu_w - 2, y1, fill="", outline="",
                                tags=tag)
            if i > 0:
                cv.create_line(16, y0, menu_w - 16, y0, fill=BORDER)

            icon_cv = tk.Canvas(cv, width=22, height=22, bg=SURFACE2,
                                highlightthickness=0)
            icon_fn(icon_cv, TEXT)
            cv.create_window(20, (y0 + y1) / 2, anchor="w", window=icon_cv)
            cv.create_text(50, (y0 + y1) / 2, text=label, fill=TEXT,
                           anchor="w", font=(FONT, 10), tags=tag)

            def on_click(e, c=cmd):
                popup.destroy()
                c()

            cv.tag_bind(tag, "<Button-1>", on_click)
            cv.tag_bind(tag, "<Enter>", lambda e, t=tag: cv.itemconfig(t, fill=SURFACE))
            cv.tag_bind(tag, "<Leave>", lambda e, t=tag: cv.itemconfig(t, fill=""))

        popup.focus_set()
        popup.bind("<FocusOut>", lambda e: popup.destroy())

    # ── Diálogos estilizados (substituem simpledialog/messagebox nativos) ────
    def _center_dialog(self, win, dw, dh):
        win.geometry(f"{dw}x{dh}+{self.root.winfo_x() + (W - dw) // 2}+"
                     f"{self.root.winfo_y() + (H - dh) // 2}")

    def _finalize_dialog(self, win, card, dw):
        """Mede a altura real do conteúdo e só então posiciona/mostra a
        janela — evita cortar botões quando o texto ocupa mais espaço do
        que uma altura fixa "chutada" previa."""
        win.update_idletasks()
        self._center_dialog(win, dw, card.winfo_reqheight())
        win.deiconify()
        win.grab_set()
        win.focus_set()

    def _info_dialog(self, title: str, message: str):
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.overrideredirect(True)
        win.configure(bg=BG)
        win.bind("<Escape>", lambda e: win.destroy())

        card = tk.Frame(win, bg=SURFACE2, padx=20, pady=18)
        card.pack(fill="both", expand=True)
        tk.Label(card, text=title, font=(FONT, 13, "bold"),
                 bg=SURFACE2, fg=TEXT).pack(anchor="w")
        tk.Label(card, text=message, font=(FONT, 10), bg=SURFACE2, fg=TEXT_DIM,
                 justify="left", wraplength=240).pack(anchor="w", pady=(6, 16))

        btn_row = tk.Frame(card, bg=SURFACE2)
        btn_row.pack(fill="x", side="bottom")
        self._make_pill_button(btn_row, "OK", GOLD, "black", win.destroy,
                               w=100, h=36, font_size=10).pack(side="right")

        self._finalize_dialog(win, card, 280)

    def _confirm_dialog(self, title: str, message: str, on_confirm,
                        confirm_label="Remover"):
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.overrideredirect(True)
        win.configure(bg=BG)
        win.bind("<Escape>", lambda e: win.destroy())

        card = tk.Frame(win, bg=SURFACE2, padx=20, pady=18)
        card.pack(fill="both", expand=True)
        tk.Label(card, text=title, font=(FONT, 13, "bold"),
                 bg=SURFACE2, fg=TEXT).pack(anchor="w")
        tk.Label(card, text=message, font=(FONT, 10), bg=SURFACE2, fg=TEXT_DIM,
                 justify="left", wraplength=260).pack(anchor="w", pady=(6, 16))

        def yes():
            win.destroy()
            on_confirm()

        btn_row = tk.Frame(card, bg=SURFACE2)
        btn_row.pack(fill="x", side="bottom")
        self._make_pill_button(btn_row, "Cancelar", SURFACE, TEXT_DIM, win.destroy,
                               w=118, h=38, font_size=10, bold=False).pack(side="left")
        self._make_pill_button(btn_row, confirm_label, DANGER, "white", yes,
                               w=118, h=38, font_size=10).pack(side="right")

        self._finalize_dialog(win, card, 300)

    # ── Gerenciamento de palavras-chave ───────────────────────────────────────
    def _add_keyword(self):
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.overrideredirect(True)
        win.configure(bg=BG)

        card = tk.Frame(win, bg=SURFACE2, padx=20, pady=18)
        card.pack(fill="both", expand=True)
        tk.Label(card, text="Nova palavra-chave", font=(FONT, 13, "bold"),
                 bg=SURFACE2, fg=TEXT).pack(anchor="w")
        tk.Label(card, text="Fotos com essa palavra na anotação são\n"
                            "organizadas automaticamente numa pasta.",
                 font=(FONT, 9), bg=SURFACE2, fg=TEXT_DIM,
                 justify="left").pack(anchor="w", pady=(4, 12))

        entry_bg = tk.Frame(card, bg=SURFACE,
                            highlightbackground=BORDER, highlightthickness=1)
        entry_bg.pack(fill="x")
        entry = tk.Entry(entry_bg, font=(FONT, 11), bg=SURFACE, fg=TEXT,
                         insertbackground=TEXT, relief="flat", bd=8)
        entry.pack(fill="x")
        entry.focus_set()

        def confirm():
            kw = entry.get().strip().replace(" ", "_")
            win.destroy()
            if not kw or kw in self.palavrasChaves:
                return
            self.palavrasChaves.append(kw)
            folder = os.path.join(os.getcwd(), kw)
            os.makedirs(folder, exist_ok=True)
            for item in self.galeria:
                if kw.lower() in item.get("anotacao", "").lower():
                    dest = os.path.join(folder, os.path.basename(item["imagem"]))
                    try:
                        shutil.copy2(item["imagem"], dest)
                    except Exception:
                        pass
            self._save_data()
            self._refresh_gallery()

        entry.bind("<Return>", lambda e: confirm())
        win.bind("<Escape>", lambda e: win.destroy())

        btn_row = tk.Frame(card, bg=SURFACE2)
        btn_row.pack(fill="x", pady=(16, 0))
        self._make_pill_button(btn_row, "Cancelar", SURFACE, TEXT_DIM, win.destroy,
                               w=118, h=38, font_size=10, bold=False).pack(side="left")
        self._make_pill_button(btn_row, "Adicionar", GOLD, "black", confirm,
                               w=118, h=38, font_size=10).pack(side="right")

        self._finalize_dialog(win, card, 300)

    def _manage_keywords(self):
        if not self.palavrasChaves:
            self._info_dialog("Palavras-chave", "Nenhuma palavra-chave cadastrada.")
            return

        win = tk.Toplevel(self.root)
        win.withdraw()
        win.title("Palavras-chave")
        win.configure(bg=BG)
        win.resizable(False, False)
        theme.apply_dark_titlebar(win)

        body = tk.Frame(win, bg=BG)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Palavras-chave", font=(FONT, 14, "bold"),
                 bg=BG, fg=TEXT, pady=16).pack()
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", padx=18)

        list_frame = tk.Frame(body, bg=BG)
        list_frame.pack(fill="both", expand=True, padx=18, pady=(12, 14))

        for kw in list(self.palavrasChaves):
            row = tk.Frame(list_frame, bg=SURFACE2)
            row.pack(fill="x", pady=(0, 8))
            tk.Label(row, text=f"#{kw}", font=(FONT, 11), bg=SURFACE2, fg=TEXT,
                     padx=14, pady=12).pack(side="left")
            del_btn = self._make_circle_button(
                row, 30, lambda cv: self._draw_icon_trash(cv, DANGER),
                command=lambda k=kw, w=win: self._confirm_delete_keyword(k, w),
                bg=SURFACE2, hover_bg=SURFACE)
            del_btn.pack(side="right", padx=10)

        win.update_idletasks()
        dw, dh = 320, min(460, body.winfo_reqheight())
        win.geometry(f"{dw}x{dh}+{self.root.winfo_x() + 35}+{self.root.winfo_y() + 90}")
        win.deiconify()
        win.grab_set()

    def _confirm_delete_keyword(self, kw: str, manage_win: tk.Toplevel):
        def do_delete():
            self._delete_keyword(kw)
            manage_win.destroy()
            self._manage_keywords()

        self._confirm_dialog(
            "Remover palavra-chave",
            f'Remover "{kw}" e apagar a pasta com as fotos organizadas nela?',
            do_delete)

    def _delete_keyword(self, kw: str):
        if kw in self.palavrasChaves:
            self.palavrasChaves.remove(kw)
        folder = os.path.join(os.getcwd(), kw)
        if os.path.isdir(folder):
            try:
                shutil.rmtree(folder)
            except Exception:
                pass
        if self.gallery_folder == kw:
            self.gallery_folder = "Todas"
        self._save_data()
        self._refresh_gallery()

    # ── Encerramento ──────────────────────────────────────────────────────────
    def _on_close(self):
        self._stop_camera()
        self._save_data()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    theme.register_fonts()
    app = SnapNoteApp()
    app.run()
