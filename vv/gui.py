from __future__ import annotations
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, Tuple

from .pipeline import build_video, _collect_images
from .config import WIDTH, HEIGHT, FPS, SEC_PER, BG  # просто подтягиваем дефолты
from PIL import ImageTk
from .image import fit_to_canvas

CropOffsets = Dict[str, Tuple[float, float]]   # путь → (ox, oy) в [-1, 1]

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("image2video")

        # --- state ---
        self.image_inputs: list[str] = []
        self.audio_path: str | None = None
        self.out_path: str = "output/video.mp4"

        # --- vars ---
        self.sec_per = tk.DoubleVar(value=float(SEC_PER))
        self.fps     = tk.IntVar(value=int(FPS))
        self.bg      = tk.StringVar(value=str(BG))
        self.audio_mode = tk.StringVar(value="trim")
        self.transitions = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="")

        # превью
        self.preview_paths: list[Path] = []
        self.preview_index = tk.IntVar(value=0)

        # размер превью (пропорционально финальному ролику)
        self.preview_width = int(WIDTH / 3)          # например 360 при 1080
        self.preview_height = int(self.preview_width * HEIGHT / WIDTH)

        self.crop_offsets: CropOffsets = {}
        self._offset_syncing = False   # флаг, чтобы отличать программное обновление от пользовательского

        # режим длительности: по кадру или по ролику
        self.duration_mode = tk.StringVar(value="per_frame")  # "per_frame" | "total"
        self.total_duration = tk.DoubleVar(value=0.0)

        # режим кадрирования и фон
        self.fit_mode   = tk.StringVar(value="cover")   # "fit" | "cover"

        # смещения кадра
        self.offset_x = tk.DoubleVar(value=0.0)
        self.offset_y = tk.DoubleVar(value=0.0)

        # реакция на смену режима: при "fit" отключаем слайдеры offset
        self.fit_mode.trace_add("write", self._on_fit_mode_changed)
        self.duration_mode.trace_add("write", self._update_duration_state)

        self.motion = tk.BooleanVar(value=False)

        # --- layout: left (scrollable UI) + right (preview) ---
        self.rowconfigure(0, weight=1)

        left_min = 600
        right_min = self.preview_width + 40  # +паддинги, чтобы точно влезло

        self.columnconfigure(0, weight=3, minsize=left_min)
        self.columnconfigure(1, weight=1, minsize=right_min)

        # контейнер для левой части
        left_container = ttk.Frame(self)
        left_container.grid(row=0, column=0, sticky="nsew")

        left_container.rowconfigure(0, weight=1)
        left_container.columnconfigure(0, weight=1)
        left_container.columnconfigure(1, weight=0)

        # скроллируемый canvas слева
        self.left_canvas = tk.Canvas(
            left_container,
            borderwidth=0,
            highlightthickness=0,
            width=500,  # или 480, или хоть 400 — просто не 1px
        )
        self.left_canvas.grid(row=0, column=0, sticky="nsew")
        self.left_canvas.bind("<MouseWheel>", self._on_mousewheel)

        self.left_scrollbar = ttk.Scrollbar(
            left_container,
            orient="vertical",
            command=self.left_canvas.yview,
        )
        self.left_scrollbar.grid(row=0, column=1, sticky="ns")

        self.left_canvas.configure(yscrollcommand=self.left_scrollbar.set)

        # внутренний фрейм, в который будем строить весь левый UI
        self.frm_left = ttk.Frame(self.left_canvas)
        self._left_window_id = self.left_canvas.create_window(
            (0, 0),
            window=self.frm_left,
            anchor="nw",
        )

        # обновляем scrollregion и подгоняем ширину фрейма под ширину canvas
        def _on_left_config(event):
            # event.width — это ширина canvas
            self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
            self.left_canvas.itemconfigure(self._left_window_id, width=event.width)

        # ВАЖНО: биндим на canvas, а не на frm_left
        self.left_canvas.bind("<Configure>", _on_left_config)

        # контейнер для правой колонки (превью)
        self.frm_preview_root = ttk.Frame(self)
        self.frm_preview_root.grid(row=0, column=1, sticky="nsew", padx=(4, 10), pady=10)

        # чтобы превью внутри тоже растягивалось
        self.frm_preview_root.rowconfigure(0, weight=1)
        self.frm_preview_root.columnconfigure(0, weight=1)

        # --- UI ---
        self._build_ui(self.frm_left)
        self._build_preview_ui(self.frm_preview_root)

        # после построения UI — подгоняем размер
        self.update_idletasks()

        min_w = left_min + right_min + 40  # ещё немного на внешние отступы
        min_h = 600

        self.minsize(min_w, min_h)
        self.geometry(f"{min_w}x{min_h}")

    def _build_ui(self, parent: tk.Widget):
        pad = dict(padx=10, pady=8)

        # Images
        frm_in = ttk.LabelFrame(parent, text="Изображения")
        frm_in.pack(fill="x", **pad)

        self.lbl_imgs = ttk.Label(frm_in, text="Не выбрано")
        self.lbl_imgs.pack(side="left", padx=6)
        ttk.Button(frm_in, text="Папка…", command=self.pick_images_dir).pack(side="right")
        ttk.Button(frm_in, text="Файлы…", command=self.pick_images_files).pack(side="right", padx=6)

        # Audio
        frm_audio = ttk.LabelFrame(parent, text="Аудио (опционально)")
        frm_audio.pack(fill="x", **pad)

        self.lbl_audio = ttk.Label(frm_audio, text="—")
        self.lbl_audio.pack(side="left", padx=6)
        ttk.Button(frm_audio, text="Выбрать…", command=self.pick_audio).pack(side="right")
        ttk.Button(frm_audio, text="Очистить", command=self.clear_audio).pack(side="right", padx=6)

        # Output
        frm_out = ttk.LabelFrame(parent, text="Выходной файл")
        frm_out.pack(fill="x", **pad)

        self.ent_out = ttk.Entry(frm_out)
        self.ent_out.insert(0, self.out_path)
        self.ent_out.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(frm_out, text="Сохранить как…", command=self.pick_out).pack(side="right")

        # Options
        frm_opts = ttk.LabelFrame(parent, text="Параметры")
        frm_opts.pack(fill="x", **pad)

        # row_dur — режим длительности
        row_dur = ttk.Frame(frm_opts); row_dur.pack(fill="x", pady=4)

        # по кадру
        ttk.Radiobutton(
            row_dur,
            text="Кадр, сек",
            variable=self.duration_mode,
            value="per_frame",
        ).pack(side="left", padx=(6, 4))

        self.ent_sec_per = ttk.Entry(row_dur, textvariable=self.sec_per, width=8)
        self.ent_sec_per.pack(side="left")

        # по ролику
        ttk.Radiobutton(
            row_dur,
            text="Ролик, сек",
            variable=self.duration_mode,
            value="total",
        ).pack(side="left", padx=(16, 4))

        self.ent_total_duration = ttk.Entry(row_dur, textvariable=self.total_duration, width=8)
        self.ent_total_duration.pack(side="left")

        # row_fps — FPS + фон
        row_fps = ttk.Frame(frm_opts); row_fps.pack(fill="x", pady=4)
        ttk.Label(row_fps, text="FPS").pack(side="left", padx=(6,6))
        ttk.Combobox(
            row_fps,
            textvariable=self.fps,
            values=(24, 30, 60),
            width=5,
            state="readonly",
        ).pack(side="left")


        row2 = ttk.Frame(frm_opts); row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="Аудио режим").pack(side="left", padx=6)
        ttk.Combobox(row2, textvariable=self.audio_mode, values=("trim","loop"), width=8, state="readonly").pack(side="left")
        ttk.Checkbutton(row2, text="Переходы (WIP)", variable=self.transitions).pack(side="left", padx=(16,0))

        row_mode = ttk.Frame(frm_opts); row_mode.pack(fill="x", pady=4)

        ttk.Label(row_mode, text="Кадрирование").pack(side="left", padx=6)
        ttk.Combobox(
            row_mode,
            textvariable=self.fit_mode,
            values=("fit", "cover"),
            width=8,
            state="readonly",
        ).pack(side="left")
        ttk.Checkbutton(row_mode, text="Лёгкое движение кадра", variable=self.motion).pack(side="left", padx=(16,0))


        self.frm_offsets = ttk.Frame(frm_opts)
        self.frm_offsets.pack(fill="x", pady=4)

        ttk.Label(self.frm_offsets, text="Смещение X (cover)").pack(side="left", padx=6)
        self.scale_offset_x = ttk.Scale(
            self.frm_offsets,
            from_=-100,
            to=100,
            orient="horizontal",
            variable=self.offset_x,
            command=self._on_offset_x_changed,
        )
        self.scale_offset_x.pack(side="left", fill="x", expand=True)

        ttk.Label(self.frm_offsets, text="Смещение Y (cover)").pack(side="left", padx=6)
        self.scale_offset_y = ttk.Scale(
            self.frm_offsets,
            from_=-100,
            to=100,
            orient="horizontal",
            variable=self.offset_y,
            command=self._on_offset_y_changed,
        )
        self.scale_offset_y.pack(side="left", fill="x", expand=True, padx=(0, 6))

        # сразу привести состояние слайдеров в соответствие с начальным режимом
        self._update_offset_state()
        self._update_duration_state()

        # Progress
        frm_prog = ttk.Frame(parent); frm_prog.pack(fill="x", **pad)
        self.pbar = ttk.Progressbar(frm_prog, mode="determinate", maximum=100)
        self.pbar.pack(fill="x")
        self.lbl_status = ttk.Label(frm_prog, textvariable=self.status)
        self.lbl_status.pack(anchor="w", pady=4)

        # Actions
        frm_btn = ttk.Frame(parent); frm_btn.pack(fill="x", **pad)

        self.btn_render = ttk.Button(frm_btn, text="Собрать видео", command=self.start_render)
        self.btn_render.pack(side="left")

        self.btn_open_dir = ttk.Button(frm_btn, text="Открыть папку выхода", command=self.open_out_dir)
        self.btn_open_dir.pack(side="right")

    def _build_preview_ui(self, parent: tk.Widget):
        frm_prev = ttk.Frame(parent)
        frm_prev.grid(row=0, column=0, sticky="nsew")
        self.frm_prev = frm_prev

        self.btn_prev_img = ttk.Button(frm_prev, text="◀", width=3, command=self.prev_image)
        self.btn_next_img = ttk.Button(frm_prev, text="▶", width=3, command=self.next_image)

        self.btn_prev_img.place_forget()
        self.btn_next_img.place_forget()

        self.preview_label = ttk.Label(frm_prev, anchor="center")
        self.preview_label.pack(fill="both", expand=True)

        self.preview_photo = None

        # hover на всём, включая сами кнопки
        for w in (frm_prev, self.preview_label, self.btn_prev_img, self.btn_next_img):
            w.bind("<Enter>", self._show_nav)
            w.bind("<Leave>", self._hide_nav)

    def _show_nav(self, event=None):
        if not self.preview_paths:
            return
        # размещаем стрелки по краям кадра
        self.btn_prev_img.place(relx=0.0, rely=0.5, anchor="w", x=8)
        self.btn_next_img.place(relx=1.0, rely=0.5, anchor="e", x=-8)

        # убедиться, что они поверх лейбла
        self.btn_prev_img.lift()
        self.btn_next_img.lift()

    def _hide_nav(self, event=None):
        # если нет картинок – просто не показываем
        if not self.preview_paths:
            self.btn_prev_img.place_forget()
            self.btn_next_img.place_forget()
            return
        # лёгкий delay можно не делать — достаточно убрать
        self.btn_prev_img.place_forget()
        self.btn_next_img.place_forget()

    def _on_mousewheel(self, event):
        # на Mac delta обычно ±1/±2, на Windows — ±120
        self.left_canvas.yview_scroll(-int(event.delta / 120), "units")

    def _sync_sliders_with_current_offset(self):
        if not self.preview_paths or self.fit_mode.get() != "cover":
            return

        idx = self.preview_index.get()
        path = self.preview_paths[idx]
        key = str(path)

        if key in self.crop_offsets:
            ox, oy = self.crop_offsets[key]
        else:
            ox, oy = 0.0, 0.0

        self._offset_syncing = True
        self.offset_x.set(ox * 100.0)
        self.offset_y.set(oy * 100.0)
        self._offset_syncing = False

    # ---- pickers ----
    def pick_images_dir(self):
        d = filedialog.askdirectory(title="Папка с изображениями")
        if d:
            self.image_inputs = [d]
            self.lbl_imgs.config(text=f"Папка: {Path(d).name}")

            imgs_input = self.image_inputs[0]
            self.preview_paths = _collect_images(imgs_input)
            self.preview_index.set(0)
            self._sync_sliders_with_current_offset()
            self._update_preview()

    def pick_images_files(self):
        files = filedialog.askopenfilenames(
            title="Выбрать изображения",
            filetypes=[("Images","*.jpg *.jpeg *.png *.webp")]
        )
        if files:
            self.image_inputs = list(files)
            self.lbl_imgs.config(text=f"Файлов: {len(files)}")

            imgs_input = self.image_inputs if len(self.image_inputs) > 1 else self.image_inputs[0]
            self.preview_paths = _collect_images(imgs_input)
            self.preview_index.set(0)
            self._sync_sliders_with_current_offset()
            self._update_preview()

    def prev_image(self):
        if not self.preview_paths:
            return
        n = len(self.preview_paths)
        i = self.preview_index.get()
        # шаг назад по кругу
        self.preview_index.set((i - 1) % n)
        self._sync_sliders_with_current_offset()
        self._update_preview()

    def next_image(self):
        if not self.preview_paths:
            return
        n = len(self.preview_paths)
        i = self.preview_index.get()
        # шаг вперёд по кругу
        self.preview_index.set((i + 1) % n)
        self._sync_sliders_with_current_offset()
        self._update_preview()

    def pick_audio(self):
        f = filedialog.askopenfilename(
            title="Выбрать аудио",
            filetypes=[("Audio","*.mp3 *.wav")]
        )
        if f:
            self.audio_path = f
            self.lbl_audio.config(text=Path(f).name)

    def clear_audio(self):
        self.audio_path = None
        self.lbl_audio.config(text="—")

    def pick_out(self):
        f = filedialog.asksaveasfilename(
            title="Сохранить как",
            defaultextension=".mp4",
            filetypes=[("MP4","*.mp4")]
        )
        if f:
            self.out_path = f
            self.ent_out.delete(0, "end")
            self.ent_out.insert(0, f)

    def open_out_dir(self):
        p = Path(self.ent_out.get()).expanduser()
        d = p.parent
        if d.exists():
            import subprocess, platform
            if platform.system() == "Darwin":
                subprocess.run(["open", d])
            elif platform.system() == "Windows":
                subprocess.run(["explorer", str(d)])
            else:
                subprocess.run(["xdg-open", str(d)])

    def _update_preview(self):
        if not self.preview_paths:
            self.preview_photo = None
            self.preview_label.config(image="", text="Здесь будет превью кадра")
            self.btn_prev_img.place_forget()
            self.btn_next_img.place_forget()
            return

        n = len(self.preview_paths)
        idx = self.preview_index.get()
        idx = max(0, min(idx, n - 1))
        self.preview_index.set(idx)
        path = self.preview_paths[idx]

        self.btn_prev_img.config(state="normal")
        self.btn_next_img.config(state="normal")

        fit_mode = self.fit_mode.get()
        bg = self.bg.get()

        if fit_mode == "cover":
            key = str(path)

            if key in self.crop_offsets:
                ox, oy = self.crop_offsets[key]
            else:
                ox = max(-100.0, min(100.0, self.offset_x.get())) / 100.0
                oy = max(-100.0, min(100.0, self.offset_y.get())) / 100.0

            offset = (ox, oy)
            fancy_bg = False
        else:
            offset = None
            fancy_bg = True

        frame = fit_to_canvas(
            path,
            size=(self.preview_width, self.preview_height),
            bg=bg,
            mode=fit_mode,
            fancy_bg=fancy_bg,
            offset=offset,
        )

        self.preview_photo = ImageTk.PhotoImage(frame)
        self.preview_label.config(image=self.preview_photo, text="")

        # если мышь уже над превью — подсветим стрелки
        self._show_nav()

    def _on_fit_mode_changed(self, *args):
        # старое поведение — прятать/показывать слайдеры
        self._update_offset_state()
        # и сразу перерисовать превью
        self._update_preview()

    def _update_offset_state(self, *args):
        """Обновить видимость слайдеров смещения и чекбокса fancy_bg."""
        mode = self.fit_mode.get()

        if mode == "cover":
            # показать, если вдруг спрятан
            if not self.frm_offsets.winfo_ismapped():
                self.frm_offsets.pack(fill="x", pady=4)
        else:
            # спрятать, если виден
            if self.frm_offsets.winfo_ismapped():
                self.frm_offsets.pack_forget()

    def _on_offset_x_changed(self, value: str):
        if self._offset_syncing or not self.preview_paths:
            return
        self.offset_x.set(float(value))
        self._store_current_offset()
        self._update_preview()

    def _on_offset_y_changed(self, value: str):
        if self._offset_syncing or not self.preview_paths:
            return
        self.offset_y.set(float(value))
        self._store_current_offset()
        self._update_preview()

    def _store_current_offset(self):
        if not self.preview_paths:
            return
        idx = self.preview_index.get()
        path = self.preview_paths[idx]
        # из диапазона [-100,100] -> [-1,1]
        ox = max(-100.0, min(100.0, self.offset_x.get())) / 100.0
        oy = max(-100.0, min(100.0, self.offset_y.get())) / 100.0
        self.crop_offsets[str(path)] = (ox, oy)

    def _update_duration_state(self, *args):
        """Включать/отключать поля длительности в зависимости от режима."""
        mode = self.duration_mode.get()
        if mode == "per_frame":
            self.ent_sec_per.configure(state="normal")
            self.ent_total_duration.configure(state="disabled")
        else:
            self.ent_sec_per.configure(state="disabled")
            self.ent_total_duration.configure(state="normal")

    # ---- rendering ----
    def start_render(self):
        try:
            if not self.image_inputs:
                raise ValueError("Выбери изображения (папку или файлы).")
            self.out_path = self.ent_out.get().strip() or "output/video.mp4"
            Path(self.out_path).parent.mkdir(parents=True, exist_ok=True)
            self._set_running(True)
            self.status.set("Подготовка…")
            self.pbar.config(value=0, maximum=100)

            # прогресс — безопасно в GUI-поток через after()
            def progress_cb(current: int, total: int):
                self.after(0, self._on_progress, current, total)

            def worker():
                try:
                    # либо список, либо одна строка
                    imgs_input = self.image_inputs if len(self.image_inputs) > 1 else self.image_inputs[0]
                    # развернуть в реальные пути к файлам
                    img_paths = _collect_images(imgs_input)

                    # режимы кадрирования
                    fit_mode = self.fit_mode.get()

                    # нормализуем слайдеры из [-100, 100] в [-1.0, 1.0]
                    ox = max(-1.0, min(1.0, self.offset_x.get() / 100.0))
                    oy = max(-1.0, min(1.0, self.offset_y.get() / 100.0))

                    # offset имеет смысл только в cover
                    if fit_mode == "cover":
                        # используем то, что набралось в GUI; если для каких-то картинок нет — просто 0,0
                        crop_offsets: CropOffsets = {}
                        for p in img_paths:
                            key = str(p)
                            if key in self.crop_offsets:
                                crop_offsets[key] = self.crop_offsets[key]
                            else:
                                crop_offsets[key] = (0.0, 0.0)
                        fancy_bg = False
                    else:
                        crop_offsets = None
                        fancy_bg = True

                    # режим длительности
                    duration_mode = self.duration_mode.get()
                    sec_per = float(self.sec_per.get())
                    total_duration = None

                    if duration_mode == "total":
                        total_duration = float(self.total_duration.get())

                    if self.motion.get():
                        motion = "kenburns"
                    else:
                        motion = "none"

                    result = build_video(
                        images=imgs_input,
                        out=self.out_path,
                        sec_per=float(self.sec_per.get()),
                        fps=int(self.fps.get()),
                        bg=self.bg.get(),  # технический, по сути не используется при fancy_bg
                        audio=self.audio_path,
                        transitions=bool(self.transitions.get()),
                        audio_adjust=self.audio_mode.get(),
                        progress_cb=progress_cb,
                        total_duration=total_duration,
                        fit_mode=fit_mode,
                        fancy_bg=fancy_bg,
                        crop_offsets=crop_offsets,
                        motion=motion,
                    )
                    self.after(0, self._on_done, result)
                except Exception as e:
                    self.after(0, self._on_error, e)

            threading.Thread(target=worker, daemon=True).start()

        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _on_progress(self, current: int, total: int):
        # total приходит из pipeline — ставим максимум
        if total > 0:
            self.pbar.config(maximum=total)

        if current <= total:
            # этап обработки кадров
            self.pbar.config(value=current)
            self.status.set(f"Обработка кадров: {current}/{total}")
        else:
            # специальный сигнал "кодирование видео"
            # бар просто держим на 100%
            self.pbar.config(value=total)
            self.status.set("Кодирование видео…")

    def _on_done(self, result_path: str):
        self._set_running(False)
        self.status.set("Готово.")
        messagebox.showinfo("Готово", f"Видео сохранено:\n{result_path}")

    def _on_error(self, err: Exception):
        self._set_running(False)
        self.status.set("Ошибка.")
        messagebox.showerror("Ошибка", str(err))

    def _set_running(self, running: bool):
        state = "disabled" if running else "normal"

        # 1) рекурсивно глушим все интерактивные элементы
        def walk(widget: tk.Misc):
            for child in widget.winfo_children():
                # сначала идём вглубь по фреймам
                if isinstance(child, (ttk.Frame, ttk.LabelFrame, tk.Frame)):
                    walk(child)
                # потом пробуем задать state
                try:
                    child.configure(state=state)
                except tk.TclError:
                    # не все виджеты имеют state — их просто пропускаем
                    pass

        walk(self)

        # 2) Явно управляем основными кнопками,
        #    чтобы точно не было рассинхрона.
        if hasattr(self, "btn_render"):
            if running:
                self.btn_render.configure(state="disabled", text="Сборка…")
                # для ttk на всякий случай дублируем через state()
                self.btn_render.state(["disabled"])
            else:
                self.btn_render.configure(state="normal", text="Собрать видео")
                self.btn_render.state(["!disabled"])

        if hasattr(self, "btn_open_dir"):
            # тут уже по вкусу — можно оставлять кнопку живой во время рендера
            if running:
                self.btn_open_dir.configure(state="disabled")
                self.btn_open_dir.state(["disabled"])
            else:
                self.btn_open_dir.configure(state="normal")
                self.btn_open_dir.state(["!disabled"])

def main():
    App().mainloop()

if __name__ == "__main__":
    main()