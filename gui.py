import tkinter as tk
from tkinter import messagebox, simpledialog
import cv2
from PIL import Image, ImageTk
import os
import threading
import shutil
import json
from datetime import datetime

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
NAV_BG   = "#111111"
DANGER   = "#FF453A"
SUCCESS  = "#30D158"

FONT     = "Segoe UI"
W, H, NAV_H = 390, 780, 65
CONTENT_H    = H - NAV_H


# ── App principal ─────────────────────────────────────────────────────────────
class SnapNoteApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SnapNote")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

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
        self._search_refs       = []
        self.current_screen: str | None = None
        self.gallery_folder     = "Todas"
        self._sheet_open        = False
        self._sheet_h           = 310

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
        known = {i["imagem"] for i in self.galeria}
        if os.path.isdir(self.pastaFotos):
            for name in sorted(os.listdir(self.pastaFotos)):
                if name.lower().endswith((".jpg", ".jpeg", ".png")):
                    p = os.path.join(self.pastaFotos, name)
                    if p not in known:
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
        self._build_search_screen()
        self._build_annotation_sheet()
        self._build_nav()

    # ── Nav bar ───────────────────────────────────────────────────────────────
    def _build_nav(self):
        nav = tk.Frame(self.root, bg=NAV_BG, height=NAV_H)
        nav.place(x=0, y=CONTENT_H, width=W, height=NAV_H)
        tk.Frame(nav, bg=BORDER, height=1).pack(fill="x")

        items = [
            ("camera",  self._draw_icon_camera,  "Câmera"),
            ("gallery", self._draw_icon_gallery, "Galeria"),
            ("search",  self._draw_icon_search,  "Busca"),
        ]
        self._nav_icons  = {}
        self._nav_labels = {}
        btn_w = W // 3

        for idx, (name, draw_fn, label) in enumerate(items):
            frame = tk.Frame(nav, bg=NAV_BG, cursor="hand2")
            frame.place(x=idx * btn_w, y=1, width=btn_w, height=NAV_H - 1)

            cv = tk.Canvas(frame, width=26, height=26, bg=NAV_BG,
                           highlightthickness=0, cursor="hand2")
            cv.place(relx=0.5, rely=0.32, anchor="center")
            draw_fn(cv, TEXT_DIM)

            lbl = tk.Label(frame, text=label, font=(FONT, 7),
                           bg=NAV_BG, fg=TEXT_DIM, cursor="hand2")
            lbl.place(relx=0.5, rely=0.76, anchor="center")

            for w in (frame, cv, lbl):
                w.bind("<Button-1>", lambda e, n=name: self.show_screen(n))

            self._nav_icons[name]  = (cv, draw_fn)
            self._nav_labels[name] = lbl

    def _draw_icon_camera(self, cv, color):
        cv.delete("all")
        cv.create_rectangle(2, 7, 24, 22, outline=color, width=1.5, fill="")
        cv.create_oval(8, 10, 18, 19, outline=color, width=1.5, fill="")
        cv.create_rectangle(9, 4, 15, 8, outline=color, width=1.5, fill="")

    def _draw_icon_gallery(self, cv, color):
        cv.delete("all")
        for r in range(2):
            for c in range(2):
                x1, y1 = 3 + c * 12, 3 + r * 12
                cv.create_rectangle(x1, y1, x1 + 9, y1 + 9,
                                    outline=color, width=1.5, fill="")

    def _draw_icon_search(self, cv, color):
        cv.delete("all")
        cv.create_oval(3, 3, 16, 16, outline=color, width=1.5, fill="")
        cv.create_line(14, 14, 23, 23, fill=color, width=1.5)

    def _update_nav(self, active: str):
        for name, (cv, draw_fn) in self._nav_icons.items():
            color = TEXT if name == active else TEXT_DIM
            draw_fn(cv, color)
            self._nav_labels[name].configure(fg=color)

    # ── Troca de tela ─────────────────────────────────────────────────────────
    def show_screen(self, name: str):
        if self.current_screen == "camera" and name != "camera":
            self._stop_camera()
        for frame in self.screens.values():
            frame.place_forget()
        self.screens[name].place(x=0, y=0, width=W, height=CONTENT_H)
        self.current_screen = name
        self._update_nav(name)
        if name == "camera":
            self._start_camera()
        elif name == "gallery":
            self._refresh_gallery()
        elif name == "search":
            self._render_search_results(self.galeria)

    # ── Tela de câmera ────────────────────────────────────────────────────────
    def _build_camera_screen(self):
        f = tk.Frame(self.container, bg="black")
        self.screens["camera"] = f

        cam_h = CONTENT_H - 100
        self.cam_canvas = tk.Canvas(f, bg="#0D0D0D", highlightthickness=0,
                                    cursor="crosshair")
        self.cam_canvas.place(x=0, y=0, width=W, height=cam_h)
        self._cam_h = cam_h

        # Placeholder enquanto câmera carrega
        self.cam_canvas.create_text(
            W // 2, cam_h // 2,
            text="Inicializando câmera…",
            fill="#2A2A2A", font=(FONT, 13), tags="placeholder",
        )

        # Área de controles
        ctrl = tk.Frame(f, bg="black", height=100)
        ctrl.place(x=0, y=cam_h, width=W, height=100)

        # Botão de captura
        self.shutter = tk.Canvas(ctrl, width=72, height=72, bg="black",
                                 highlightthickness=0, cursor="hand2")
        self.shutter.place(relx=0.5, rely=0.5, anchor="center")
        self._draw_shutter()
        self.shutter.bind("<Button-1>", lambda e: self._on_capture())
        self.shutter.bind("<Enter>",    lambda e: self._draw_shutter(hover=True))
        self.shutter.bind("<Leave>",    lambda e: self._draw_shutter(hover=False))

    def _draw_shutter(self, hover=False):
        self.shutter.delete("all")
        inner = "#CCCCCC" if hover else "#FFFFFF"
        self.shutter.create_oval(4,  4,  68, 68, outline="#FFFFFF", width=2.5, fill="")
        self.shutter.create_oval(11, 11, 61, 61, fill=inner, outline="")

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
        cw, ch = W, self._cam_h
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
        self._show_annotation_sheet()

    def _flash(self):
        flash = tk.Frame(self.screens["camera"], bg="white")
        flash.place(x=0, y=0, width=W, height=CONTENT_H)
        self.root.update()
        self.root.after(110, flash.destroy)

    # ── Annotation sheet (slide-up) ───────────────────────────────────────────
    def _build_annotation_sheet(self):
        sh = self._sheet_h
        self.sheet = tk.Frame(self.root, bg=SURFACE, bd=0)
        self.sheet.place(x=0, y=H, width=W, height=sh)

        # Handle
        tk.Frame(self.sheet, bg=BORDER, width=36, height=4).place(relx=0.5, y=10, anchor="n")

        # Título
        tk.Label(self.sheet, text="Nova anotação", font=(FONT, 13, "bold"),
                 bg=SURFACE, fg=TEXT).place(x=20, y=30)

        # Miniatura
        self.sheet_thumb = tk.Label(self.sheet, bg=SURFACE2)
        self.sheet_thumb.place(x=20, y=62, width=64, height=48)

        # Campo de texto
        entry_bg = tk.Frame(self.sheet, bg=SURFACE2,
                            highlightbackground=BORDER, highlightthickness=1)
        entry_bg.place(x=96, y=62, width=W - 116, height=48)

        self.annot_entry = tk.Entry(
            entry_bg, font=(FONT, 11), bg=SURFACE2, fg=TEXT,
            insertbackground=TEXT, relief="flat", bd=8,
        )
        self.annot_entry.pack(side="left", fill="both", expand=True)

        if AUDIO_AVAILABLE:
            self._mic_btn = tk.Label(entry_bg, text="🎤", font=(FONT, 15),
                                     bg=SURFACE2, fg=TEXT_DIM, cursor="hand2", padx=6)
            self._mic_btn.pack(side="right", pady=4)
            self._mic_btn.bind("<Button-1>", lambda e: self._record_audio())

        # Botões
        cancel = tk.Label(self.sheet, text="Descartar", font=(FONT, 11),
                          bg=SURFACE2, fg=TEXT_DIM, cursor="hand2",
                          pady=10, anchor="center")
        cancel.place(x=20, y=128, width=165, height=38)
        cancel.bind("<Button-1>", lambda e: self._discard())

        save = tk.Label(self.sheet, text="Salvar", font=(FONT, 11, "bold"),
                        bg=TEXT, fg="black", cursor="hand2",
                        pady=10, anchor="center")
        save.place(x=195, y=128, width=175, height=38)
        save.bind("<Button-1>", lambda e: self._save_annotation())

        # Hover effects
        for btn, normal_bg, hover_bg in [
            (cancel, SURFACE2, "#3A3A3C"),
            (save,   TEXT,     "#DDDDDD"),
        ]:
            btn.bind("<Enter>", lambda e, b=btn, c=hover_bg: b.configure(bg=c))
            btn.bind("<Leave>", lambda e, b=btn, c=normal_bg: b.configure(bg=c))

    def _show_annotation_sheet(self):
        if self._sheet_open:
            return
        self._sheet_open = True
        self.cam_paused = True
        self._refresh_sheet_thumb()
        self.annot_entry.delete(0, "end")
        self._anim_sheet(H, H - self._sheet_h, 0)

    def _hide_annotation_sheet(self):
        self._anim_sheet(H - self._sheet_h, H, 0,
                         on_done=self._after_sheet_close)

    def _after_sheet_close(self):
        self._sheet_open = False
        self.cam_paused  = False

    def _anim_sheet(self, y0, y1, step, on_done=None):
        steps = 14
        y     = y0 + (y1 - y0) * step / steps
        self.sheet.place(x=0, y=int(y), width=W, height=self._sheet_h)
        self.sheet.lift()
        if step < steps:
            self.root.after(14, lambda: self._anim_sheet(y0, y1, step + 1, on_done))
        else:
            self.sheet.place(x=0, y=y1, width=W, height=self._sheet_h)
            if on_done:
                on_done()

    def _refresh_sheet_thumb(self):
        if not self.captured_path or not os.path.exists(self.captured_path):
            return
        try:
            img = Image.open(self.captured_path)
            img.thumbnail((128, 96))
            ref = ImageTk.PhotoImage(img)
            self.sheet_thumb.configure(image=ref)
            self.sheet_thumb._ref = ref
        except Exception:
            pass

    def _save_annotation(self):
        text = self.annot_entry.get().strip()
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
        self._hide_annotation_sheet()

    def _discard(self):
        if self.captured_path and os.path.exists(self.captured_path):
            try:
                os.remove(self.captured_path)
            except Exception:
                pass
        self.captured_path = None
        self._hide_annotation_sheet()

    def _record_audio(self):
        if not AUDIO_AVAILABLE:
            return
        self._mic_btn.configure(fg=DANGER, text="⏺")

        def run():
            try:
                rec = sr.Recognizer()
                with sr.Microphone() as src:
                    rec.adjust_for_ambient_noise(src, duration=0.5)
                    audio = rec.listen(src, timeout=6, phrase_time_limit=12)
                text = rec.recognize_google(audio, language="pt-BR")
                self.root.after(0, lambda: self.annot_entry.delete(0, "end"))
                self.root.after(0, lambda: self.annot_entry.insert(0, text))
            except Exception:
                pass
            finally:
                self.root.after(0, lambda: self._mic_btn.configure(fg=TEXT_DIM, text="🎤"))

        threading.Thread(target=run, daemon=True).start()

    # ── Tela de galeria ───────────────────────────────────────────────────────
    def _build_gallery_screen(self):
        f = tk.Frame(self.container, bg=BG)
        self.screens["gallery"] = f

        # Header
        header = tk.Frame(f, bg=BG, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="Galeria", font=(FONT, 18, "bold"),
                 bg=BG, fg=TEXT).place(x=20, rely=0.5, anchor="w")

        menu_lbl = tk.Label(header, text="⋮", font=(FONT, 21),
                            bg=BG, fg=TEXT, cursor="hand2", padx=12, pady=4)
        menu_lbl.place(relx=1.0, x=-4, rely=0.5, anchor="e")
        menu_lbl.bind("<Button-1>", self._show_gallery_menu)

        # Separador
        tk.Frame(f, bg=BORDER, height=1).pack(fill="x")

        # Tabs de pastas
        tabs_outer = tk.Frame(f, bg=BG, height=44)
        tabs_outer.pack(fill="x")
        tabs_outer.pack_propagate(False)

        self._tabs_canvas = tk.Canvas(tabs_outer, bg=BG,
                                      highlightthickness=0, height=44)
        self._tabs_canvas.pack(fill="x", padx=12, pady=4)

        self._tabs_inner = tk.Frame(self._tabs_canvas, bg=BG)
        self._tabs_win   = self._tabs_canvas.create_window(
            0, 0, anchor="nw", window=self._tabs_inner)
        self._tabs_inner.bind("<Configure>",
            lambda e: self._tabs_canvas.configure(
                scrollregion=self._tabs_canvas.bbox("all")))
        self._tabs_canvas.bind("<MouseWheel>",
            lambda e: self._tabs_canvas.xview_scroll(-1 * (e.delta // 120), "units"))

        # Grid de imagens
        grid_frame = tk.Frame(f, bg=BG)
        grid_frame.pack(fill="both", expand=True)

        self.gal_canvas  = tk.Canvas(grid_frame, bg=BG,
                                     highlightthickness=0, bd=0)
        gal_scroll       = tk.Scrollbar(grid_frame, orient="vertical",
                                        command=self.gal_canvas.yview)
        self.gal_canvas.configure(yscrollcommand=gal_scroll.set)
        self.gal_canvas.pack(side="left", fill="both", expand=True)
        gal_scroll.pack(side="right", fill="y")

        self.gal_inner = tk.Frame(self.gal_canvas, bg=BG)
        self._gal_win  = self.gal_canvas.create_window(
            0, 0, anchor="nw", window=self.gal_inner)

        self.gal_inner.bind("<Configure>",
            lambda e: self.gal_canvas.configure(
                scrollregion=self.gal_canvas.bbox("all")))
        self.gal_canvas.bind("<MouseWheel>",
            lambda e: self.gal_canvas.yview_scroll(-1 * (e.delta // 120), "units"))

    def _refresh_gallery(self):
        self._update_tabs()
        self._render_grid()

    def _update_tabs(self):
        for w in self._tabs_inner.winfo_children():
            w.destroy()

        for folder in ["Todas"] + self.palavrasChaves:
            active   = folder == self.gallery_folder
            bg_color = SURFACE2 if active else SURFACE
            fg_color = TEXT     if active else TEXT_DIM
            weight   = "bold"   if active else "normal"

            tab = tk.Label(self._tabs_inner, text=folder,
                           font=(FONT, 9, weight),
                           bg=bg_color, fg=fg_color,
                           padx=14, pady=6, cursor="hand2")
            tab.pack(side="left", padx=(0, 6))
            tab.bind("<Button-1>",
                     lambda e, fo=folder: self._select_tab(fo))

    def _select_tab(self, folder: str):
        self.gallery_folder = folder
        self._refresh_gallery()

    def _render_grid(self):
        for w in self.gal_inner.winfo_children():
            w.destroy()
        self._thumb_refs = []

        images = self._get_folder_images()
        if not images:
            tk.Label(self.gal_inner, text="Nenhuma foto ainda",
                     font=(FONT, 12), bg=BG, fg=TEXT_DIM,
                     pady=60).pack()
            return

        # Calcula largura do thumb (2 colunas, sem scrollbar ~15px)
        gap    = 2
        ncols  = 2
        thumb_w = (W - 15 - gap * (ncols - 1)) // ncols
        thumb_h = thumb_w

        # Atualiza largura interna
        self.gal_canvas.itemconfig(self._gal_win, width=W - 15)

        row_frame = None
        for idx, item in enumerate(images):
            col = idx % ncols
            if col == 0:
                row_frame = tk.Frame(self.gal_inner, bg=BG)
                row_frame.pack(fill="x", pady=(0, gap))

            cell = tk.Frame(row_frame, bg=SURFACE2,
                            width=thumb_w, height=thumb_h,
                            cursor="hand2")
            cell.pack(side="left", padx=(0 if col > 0 else 0, gap if col == 0 else 0))
            cell.pack_propagate(False)

            img_lbl = tk.Label(cell, bg=SURFACE2, cursor="hand2")
            img_lbl.place(x=0, y=0, width=thumb_w, height=thumb_h)
            self._load_thumb(item["imagem"], img_lbl, thumb_w, thumb_h)

            # Faixa de anotação na parte inferior
            annot = item.get("anotacao", "")
            if annot:
                strip = tk.Frame(cell, bg="#111111")
                strip.place(x=0, y=thumb_h - 22, width=thumb_w, height=22)
                tk.Label(strip, text=annot[:32], font=(FONT, 7),
                         bg="#111111", fg="#DDDDDD",
                         anchor="w", padx=4).place(x=0, y=3)

            path = item["imagem"]
            for widget in (cell, img_lbl):
                widget.bind("<Button-1>",
                    lambda e, p=path, a=annot: self._open_detail(p, a))

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

    def _load_thumb(self, path: str, label: tk.Label, w: int, h: int):
        try:
            img = Image.open(path)
            ew, eh = img.size
            m   = min(ew, eh)
            img = img.crop(((ew - m) // 2, (eh - m) // 2,
                            (ew + m) // 2, (eh + m) // 2))
            img = img.resize((w, h), Image.LANCZOS)
            ref = ImageTk.PhotoImage(img)
            self._thumb_refs.append(ref)
            label.configure(image=ref)
        except Exception:
            label.configure(text="?", fg=TEXT_DIM, font=(FONT, 20))

    # ── Detalhe da imagem ─────────────────────────────────────────────────────
    def _open_detail(self, path: str, annotation: str):
        win = tk.Toplevel(self.root)
        win.title("")
        win.geometry(f"{W}x{CONTENT_H}+{self.root.winfo_x()}+{self.root.winfo_y()}")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        # Header
        header = tk.Frame(win, bg=BG, height=50)
        header.pack(fill="x")
        back = tk.Label(header, text="← Voltar", font=(FONT, 11),
                        bg=BG, fg=TEXT, cursor="hand2", padx=16)
        back.place(x=0, rely=0.5, anchor="w")
        back.bind("<Button-1>", lambda e: win.destroy())
        win.bind("<Escape>", lambda e: win.destroy())

        # Imagem
        try:
            img = Image.open(path)
            img.thumbnail((W, W))
            ref       = ImageTk.PhotoImage(img)
            win._ref  = ref
            tk.Label(win, image=ref, bg="black").pack(fill="x")
        except Exception:
            tk.Label(win, text="Imagem inválida", bg=BG, fg=TEXT_DIM,
                     font=(FONT, 12), pady=20).pack()

        # Anotação
        annot_frame = tk.Frame(win, bg=SURFACE, padx=20, pady=14)
        annot_frame.pack(fill="x")
        tk.Label(annot_frame, text="Anotação", font=(FONT, 11, "bold"),
                 bg=SURFACE, fg=TEXT).pack(anchor="w")
        msg = annotation if annotation else "Sem anotação"
        tk.Label(annot_frame, text=msg, font=(FONT, 11),
                 bg=SURFACE, fg=TEXT_DIM, wraplength=W - 40,
                 justify="left", anchor="w").pack(fill="x", pady=(4, 0))

        # Nome do arquivo
        tk.Label(win, text=os.path.basename(path), font=(FONT, 8),
                 bg=BG, fg=TEXT_DIM, padx=20, pady=6).pack(anchor="w")

    # ── Menu ⋮ da galeria ─────────────────────────────────────────────────────
    def _show_gallery_menu(self, event):
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.configure(bg=SURFACE2,
                        highlightbackground=BORDER, highlightthickness=1)
        menu_w = 210
        mx     = self.root.winfo_x() + W - menu_w - 8
        my     = self.root.winfo_y() + 58
        popup.geometry(f"{menu_w}x0+{mx}+{my}")

        options = [
            ("  Nova palavra-chave",    self._add_keyword),
            ("  Gerenciar palavras-chave", self._manage_keywords),
        ]

        for i, (label, cmd) in enumerate(options):
            if i > 0:
                tk.Frame(popup, bg=BORDER, height=1).pack(fill="x")
            item = tk.Label(popup, text=label, font=(FONT, 10),
                            bg=SURFACE2, fg=TEXT, anchor="w",
                            pady=12, cursor="hand2")
            item.pack(fill="x")
            item.bind("<Enter>", lambda e, w=item: w.configure(bg=SURFACE))
            item.bind("<Leave>", lambda e, w=item: w.configure(bg=SURFACE2))

            def on_click(e, c=cmd):
                popup.destroy()
                c()

            item.bind("<Button-1>", on_click)

        popup.update_idletasks()
        total_h = sum(w.winfo_reqheight() for w in popup.winfo_children())
        popup.geometry(f"{menu_w}x{total_h}+{mx}+{my}")
        popup.focus_set()
        popup.bind("<FocusOut>", lambda e: popup.destroy())

    # ── Gerenciamento de palavras-chave ───────────────────────────────────────
    def _add_keyword(self):
        kw = simpledialog.askstring(
            "Nova palavra-chave",
            "Digite a palavra-chave (sem espaços):",
            parent=self.root,
        )
        if not kw:
            return
        kw = kw.strip().replace(" ", "_")
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

    def _manage_keywords(self):
        if not self.palavrasChaves:
            messagebox.showinfo("Palavras-chave",
                                "Nenhuma palavra-chave cadastrada.", parent=self.root)
            return

        win = tk.Toplevel(self.root)
        win.title("Palavras-chave")
        win.geometry(f"360x{min(400, 60 + len(self.palavrasChaves) * 56)}+"
                     f"{self.root.winfo_x() + 15}+{self.root.winfo_y() + 80}")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Palavras-chave", font=(FONT, 14, "bold"),
                 bg=BG, fg=TEXT, pady=14).pack()
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=16)

        for kw in list(self.palavrasChaves):
            row = tk.Frame(win, bg=SURFACE, padx=16, pady=12)
            row.pack(fill="x", padx=16, pady=(4, 0))
            tk.Label(row, text=kw, font=(FONT, 11),
                     bg=SURFACE, fg=TEXT).pack(side="left")
            del_btn = tk.Label(row, text="✕", font=(FONT, 12),
                               bg=SURFACE, fg=DANGER, cursor="hand2")
            del_btn.pack(side="right")

            def on_del(e, k=kw, w=win):
                if messagebox.askyesno("Remover",
                                       f"Remover a palavra-chave '{k}' e sua pasta?",
                                       parent=w):
                    self._delete_keyword(k)
                    w.destroy()
                    self._manage_keywords()

            del_btn.bind("<Button-1>", on_del)

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

    # ── Tela de busca ─────────────────────────────────────────────────────────
    def _build_search_screen(self):
        f = tk.Frame(self.container, bg=BG)
        self.screens["search"] = f

        # Barra de busca
        search_wrap = tk.Frame(f, bg=BG, pady=14)
        search_wrap.pack(fill="x", padx=16)

        input_bg = tk.Frame(search_wrap, bg=SURFACE2,
                            highlightbackground=BORDER, highlightthickness=1)
        input_bg.pack(fill="x", ipady=2)

        icon_cv = tk.Canvas(input_bg, width=20, height=20, bg=SURFACE2,
                            highlightthickness=0)
        icon_cv.pack(side="left", padx=(10, 0))
        icon_cv.create_oval(3, 3, 14, 14, outline=TEXT_DIM, width=1.5)
        icon_cv.create_line(13, 13, 18, 18, fill=TEXT_DIM, width=1.5)

        self.search_entry = tk.Entry(
            input_bg, font=(FONT, 12), bg=SURFACE2, fg=TEXT_DIM,
            insertbackground=TEXT, relief="flat", bd=8,
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.insert(0, "Buscar anotações…")
        self.search_entry.bind("<FocusIn>",  self._search_focus_in)
        self.search_entry.bind("<FocusOut>", self._search_focus_out)
        self.search_entry.bind("<KeyRelease>", self._do_search)

        # Resultados
        res_wrap = tk.Frame(f, bg=BG)
        res_wrap.pack(fill="both", expand=True)

        self.res_canvas = tk.Canvas(res_wrap, bg=BG,
                                    highlightthickness=0, bd=0)
        res_scroll      = tk.Scrollbar(res_wrap, orient="vertical",
                                       command=self.res_canvas.yview)
        self.res_canvas.configure(yscrollcommand=res_scroll.set)
        self.res_canvas.pack(side="left", fill="both", expand=True)
        res_scroll.pack(side="right", fill="y")

        self.res_inner = tk.Frame(self.res_canvas, bg=BG)
        self._res_win  = self.res_canvas.create_window(
            0, 0, anchor="nw", window=self.res_inner)
        self.res_inner.bind("<Configure>",
            lambda e: self.res_canvas.configure(
                scrollregion=self.res_canvas.bbox("all")))
        self.res_canvas.bind("<MouseWheel>",
            lambda e: self.res_canvas.yview_scroll(
                -1 * (e.delta // 120), "units"))

        self._search_refs: list = []

    def _search_focus_in(self, _):
        if self.search_entry.get() == "Buscar anotações…":
            self.search_entry.delete(0, "end")
            self.search_entry.configure(fg=TEXT)

    def _search_focus_out(self, _):
        if not self.search_entry.get():
            self.search_entry.insert(0, "Buscar anotações…")
            self.search_entry.configure(fg=TEXT_DIM)

    def _do_search(self, _=None):
        query = self.search_entry.get().strip().lower()
        if not query or query == "buscar anotações…":
            self._render_search_results(self.galeria)
        else:
            hits = [i for i in self.galeria
                    if query in i.get("anotacao", "").lower()]
            self._render_search_results(hits)

    def _render_search_results(self, items: list[dict]):
        for w in self.res_inner.winfo_children():
            w.destroy()
        self._search_refs = []
        self.res_canvas.itemconfig(self._res_win, width=W - 15)

        valid = [i for i in items if os.path.exists(i["imagem"])]
        if not valid:
            tk.Label(self.res_inner, text="Nenhum resultado",
                     font=(FONT, 12), bg=BG, fg=TEXT_DIM,
                     pady=40).pack()
            return

        for item in valid:
            row = tk.Frame(self.res_inner, bg=SURFACE, cursor="hand2")
            row.pack(fill="x", padx=12, pady=(0, 2))

            thumb = tk.Label(row, bg=SURFACE2)
            thumb.pack(side="left", padx=8, pady=8)
            self._load_thumb_small(item["imagem"], thumb)

            txt = tk.Frame(row, bg=SURFACE)
            txt.pack(side="left", fill="both", expand=True, padx=10, pady=10)

            annot = item.get("anotacao", "") or "Sem anotação"
            tk.Label(txt, text=annot[:70], font=(FONT, 10),
                     bg=SURFACE, fg=TEXT, anchor="w",
                     wraplength=240, justify="left").pack(anchor="w")
            tk.Label(txt, text=os.path.basename(item["imagem"]),
                     font=(FONT, 8), bg=SURFACE,
                     fg=TEXT_DIM, anchor="w").pack(anchor="w", pady=(2, 0))

            path = item["imagem"]
            annot_full = item.get("anotacao", "")
            for widget in row.winfo_children() + [row]:
                widget.bind("<Button-1>",
                    lambda e, p=path, a=annot_full: self._open_detail(p, a))

            row.bind("<Enter>", lambda e, r=row: r.configure(bg=SURFACE2))
            row.bind("<Leave>", lambda e, r=row: r.configure(bg=SURFACE))

    def _load_thumb_small(self, path: str, label: tk.Label, size: int = 56):
        try:
            img = Image.open(path)
            ew, eh = img.size
            m   = min(ew, eh)
            img = img.crop(((ew - m) // 2, (eh - m) // 2,
                            (ew + m) // 2, (eh + m) // 2))
            img = img.resize((size, size), Image.LANCZOS)
            ref = ImageTk.PhotoImage(img)
            self._search_refs.append(ref)
            label.configure(image=ref, width=size, height=size)
        except Exception:
            label.configure(text="?", fg=TEXT_DIM, font=(FONT, 16),
                            width=4, height=2)

    # ── Encerramento ──────────────────────────────────────────────────────────
    def _on_close(self):
        self._stop_camera()
        self._save_data()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = SnapNoteApp()
    app.run()
