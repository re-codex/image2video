from __future__ import annotations
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sv_ttk
from datetime import datetime

from .pipeline import build_video, _collect_images
from .config import WIDTH, HEIGHT, FPS, SEC_PER, BG  # просто подтягиваем дефолты
from PIL import Image, ImageTk
from .image import fit_to_canvas
from .duration import sec_per_for_total, total_for

CropOffsets = dict[str, tuple[float, float]]   # путь → (ox, oy) в [-1, 1]

class App(tk.Tk):
    MIN_LEFT_W = 640
    MIN_ROOT_W = 640
    START_ROOT_W = 700

    MIN_ROOT_H = 660
    START_ROOT_H = 660

    MIN_ROOT_W_WITH_PREVIEW = 975

    # просто чтобы у тебя не было магических чисел 40/20 по всему коду
    PREVIEW_EXTRA_W = 40

    def __init__(self):
        super().__init__()
        self.title("image2video")

        # ВКЛЮЧАЕМ ТЕМУ: Можно "dark" или "light"
        sv_ttk.set_theme("light")

        # стили
        style = ttk.Style(self)
        # Главная кнопка
        style.configure(
            "Primary.TButton",
            padding=(18, 10),
            font=("", 12, "bold")
        )
        # Вторичная
        style.configure(
            "Secondary.TButton",
            padding=(12, 8),
            font=("", 11)
        )

        # --- state ---
        self.image_inputs: list[str] = []
        self.audio_path: str | None = None
        self.out_path: str = "output/video.mp4"

        # --- vars ---
        self.sec_per = tk.DoubleVar(value=float(SEC_PER))
        self.fps     = tk.IntVar(value=int(FPS))
        self.bg      = tk.StringVar(value=str(BG))
        self.transitions = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="")

        # русские подписи в комбобоксах
        self.audio_mode_ui = tk.StringVar(value="обрезать по ролику")
        self.fit_mode_ui   = tk.StringVar(value="обрезать лишнее")

        # реагируем на смену режима кадрирования
        self.fit_mode_ui.trace_add("write", self._on_fit_mode_changed)

        # превью
        self.preview_paths: list[Path] = []
        self.preview_index = tk.IntVar(value=0)
        self._is_hovering = False

        self.crop_offsets: CropOffsets = {}
        self._offset_syncing = False

        # режим длительности
        self.duration_mode = tk.StringVar(value="per_frame")
        self.total_duration = tk.DoubleVar(value=0.0)
        self._duration_syncing = False

        # (твои trace_add...)
        self.sec_per.trace_add("write", self._recalc_duration)
        self.total_duration.trace_add("write", self._recalc_duration)
        self.duration_mode.trace_add("write", self._update_duration_state)
        self.duration_mode.trace_add("write", self._recalc_duration)

        self.offset_x = tk.DoubleVar(value=0.0)
        self.offset_y = tk.DoubleVar(value=0.0)
        self.motion = tk.BooleanVar(value=False)

        # --- layout: left (settings) + right (preview) ---
        self.rowconfigure(0, weight=1)

        # Левый контейнер — ИЗМЕНЕНИЕ: добавляем weight=1 для строки
        left_container = ttk.Frame(self)
        left_container.grid(row=0, column=0, sticky="nsew")
        left_container.rowconfigure(0, weight=1)  # ← левая панель растягивается
        left_container.columnconfigure(0, weight=1)

        self.frm_left = ttk.Frame(left_container)
        self.frm_left.grid(row=0, column=0, sticky="nsew")  # ← ИЗМЕНЕНИЕ: sticky="nsew"

        # Правый контейнер
        self.frm_preview_root = ttk.Frame(self)
        # Он сам растягивается внутри своей ячейки
        self.frm_preview_root.rowconfigure(0, weight=1)
        self.frm_preview_root.columnconfigure(0, weight=1)

        # --- UI ---
        self._build_ui(self.frm_left)
        self._build_preview_ui(self.frm_preview_root)

        self.update_idletasks()

        # --- layout grid ---
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1, minsize=self.MIN_LEFT_W)
        self.columnconfigure(1, weight=0, minsize=0)

        # --- старт без превью ---
        self.minsize(self.MIN_ROOT_W, self.MIN_ROOT_H)
        self.geometry(f"{self.START_ROOT_W}x{self.START_ROOT_H}")

        self._preview_padx = (4, 10)

        self._preview_visible = False
        self._geo_lock = False
        self._set_preview_visible(False)

    def _min_w_with_preview(self, preview_h: int) -> int:
        preview_h = max(1, int(preview_h))
        preview_w = int(preview_h * (WIDTH / HEIGHT))
        return max(self.MIN_ROOT_W_WITH_PREVIEW, self.MIN_LEFT_W + preview_w + self.PREVIEW_EXTRA_W)

    def _reserved_offsets_h(self) -> int:
        """
        Сколько высоты 'съедают' XY offsets в режиме cover.
        Важно: в cover offsets стоят grid(..., pady=4) => это +8px сверху/снизу.
        """
        try:
            return int(self.frm_offsets.winfo_reqheight())
        except Exception:
            return 0

    def _build_ui(self, parent: tk.Widget):
        pad = dict(padx=15, pady=10)

        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)  # content растёт
        parent.grid_rowconfigure(1, weight=0)  # bottom фикс снизу

        content = ttk.Frame(parent)
        content.grid(row=0, column=0, sticky="nsew")

        bottom = ttk.Frame(parent)
        bottom.grid(row=1, column=0, sticky="ew")

        # Images
        frm_in = ttk.LabelFrame(content, text="Изображения")
        frm_in.pack(fill="x", **pad)

        self.lbl_imgs = ttk.Label(frm_in, text="—")
        self.lbl_imgs.pack(side="left", padx=6)

        self.btn_imgs_files = ttk.Button(
            frm_in,
            text="Добавить изображения…",
            command=self.pick_images_files,
        )
        self.btn_imgs_files.pack(side="right")

        self.btn_imgs_clear = ttk.Button(
            frm_in,
            text="Очистить",
            command=self.clear_images,
        )

        # Audio
        frm_audio = ttk.LabelFrame(content, text="Аудио")
        frm_audio.pack(fill="x", **pad)

        self.lbl_audio = ttk.Label(frm_audio, text="—")
        self.lbl_audio.pack(side="left", padx=6)

        self.btn_audio_choose = ttk.Button(frm_audio, text="Добавить аудио…", command=self.pick_audio)
        self.btn_audio_choose.pack(side="right")

        self.btn_audio_clear = ttk.Button(frm_audio, text="Очистить", command=self.clear_audio)

        # Output
        frm_out = ttk.LabelFrame(content, text="Куда сохранить видео")
        frm_out.pack(fill="x", **pad)

        self.ent_out = ttk.Entry(frm_out)
        self.ent_out.insert(0, self.out_path)
        self.ent_out.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(frm_out, text="Сохранить как…", command=self.pick_out).pack(side="right")

        # Options
        frm_opts = ttk.LabelFrame(content, text="Параметры")
        frm_opts.pack(fill="x", **pad)


        # ---- Длительность ----
        frm_dur = ttk.Frame(frm_opts)
        frm_dur.pack(fill="x", pady=(4, 0))

        # строка: длина кадра
        row_dur1 = ttk.Frame(frm_dur)
        row_dur1.pack(fill="x", pady=(0, 2))
        ttk.Radiobutton(
            row_dur1,
            text="Длина каждого кадра, сек",
            variable=self.duration_mode,
            value="per_frame",
        ).pack(side="left", padx=(6, 4))
        self.ent_sec_per = ttk.Entry(row_dur1, textvariable=self.sec_per, width=8)
        self.ent_sec_per.pack(side="left")

        # строка: общая длина ролика
        row_dur2 = ttk.Frame(frm_dur)
        row_dur2.pack(fill="x", pady=(0, 2))
        ttk.Radiobutton(
            row_dur2,
            text="Общая длина ролика, сек",
            variable=self.duration_mode,
            value="total",
        ).pack(side="left", padx=(6, 4))
        self.ent_total_duration = ttk.Entry(row_dur2, textvariable=self.total_duration, width=8)
        self.ent_total_duration.pack(side="left")

        # ---- FPS ----
        row_fps = ttk.Frame(frm_opts)
        row_fps.pack(fill="x", pady=(8, 0))
        ttk.Label(row_fps, text="FPS").pack(side="left", padx=(6, 6))
        ttk.Combobox(
            row_fps,
            textvariable=self.fps,
            values=(24, 30, 60),
            width=5,
            state="readonly",
        ).pack(side="left")

        # ---- Аудио ----
        frm_audio_opts = ttk.Frame(frm_opts)
        frm_audio_opts.pack(fill="x", pady=(10, 0))

        ttk.Label(frm_audio_opts, text="Как подогнать трек по длине").pack(
            anchor="w", padx=6
        )
        ttk.Combobox(
            frm_audio_opts,
            textvariable=self.audio_mode_ui,
            values=("обрезать по ролику", "зациклить"),
            state="readonly",
        ).pack(fill="x", padx=6, pady=(2, 0))

        # ---- Кадрирование ----
        frm_fit_opts = ttk.Frame(frm_opts)
        frm_fit_opts.pack(fill="x", pady=(10, 0))

        ttk.Label(frm_fit_opts, text="Как вписать изображения в кадр").pack(
            anchor="w", padx=6
        )
        ttk.Combobox(
            frm_fit_opts,
            textvariable=self.fit_mode_ui,
            values=("добавить поля", "обрезать лишнее"),
            state="readonly",
        ).pack(fill="x", padx=6, pady=(2, 0))

        # ---- Флажки ----
        frm_flags = ttk.Frame(frm_opts)
        frm_flags.pack(fill="x", pady=(10, 0))

        ttk.Checkbutton(
            frm_flags,
            text="Плавные переходы",
            variable=self.transitions,
            command=self._recalc_duration,
        ).pack(side="left", padx=(6, 16))
        ttk.Checkbutton(
            frm_flags, text="Зум/сдвиг кадра", variable=self.motion
        ).pack(side="left")

        # divider ДОЛЖЕН быть тут, в content, и идти ПОСЛЕ секций
        divider = ttk.Frame(content, style="Divider.TFrame", height=1)
        divider.pack(fill="x", padx=15, pady=(10, 0))
        divider.pack_propagate(False)

        # spacer съедает лишнюю высоту, чтобы divider не ехал
        spacer = ttk.Frame(content)
        spacer.pack(fill="both", expand=True)

        # ---- прогресс + кнопки pack'аем в bottom ----
        frm_prog = ttk.Frame(bottom)
        frm_prog.pack(fill="x", padx=15, pady=(0, 10))
        self.pbar = ttk.Progressbar(frm_prog, mode="determinate", maximum=100)
        self.pbar.pack(fill="x")
        self.lbl_status = ttk.Label(frm_prog, textvariable=self.status)
        self.lbl_status.pack(anchor="w", pady=4)

        frm_btn = ttk.Frame(bottom)
        frm_btn.pack(fill="x", padx=15, pady=(0, 10))
        frm_btn.columnconfigure(0, weight=1)

        self.btn_render = ttk.Button(
            frm_btn,
            text="Собрать видео",
            command=self.start_render,
            style="Primary.TButton",
        )
        self.btn_render.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self.btn_open_dir = ttk.Button(
            frm_btn,
            text="Открыть папку с видео",
            command=self.open_out_dir,
            style="Secondary.TButton",
            state="disabled",
        )
        self.btn_open_dir.grid(row=1, column=0, sticky="e")

    def _build_preview_ui(self, parent: tk.Widget):
        # Настраиваем сетку родителя (frm_preview_root)
        # row=0: Канва (растягивается)
        # row=1: Слайдеры (фиксированы снизу)
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=0)
        parent.columnconfigure(0, weight=1)

        # Контейнер именно для превью (чтобы ловить его ресайз)
        self.frm_prev_container = ttk.Frame(parent)
        self.frm_prev_container.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 0))

        # ВАЖНО: Биндимся на изменение размера КОНТЕЙНЕРА, а не канвы
        self.frm_prev_container.bind("<Configure>", self._on_container_resize)

        # Канва внутри контейнера.
        # Мы НЕ задаем ей width/height здесь жестко. Мы будем менять их программно.
        self.preview_canvas = tk.Canvas(
            self.frm_prev_container,
            highlightthickness=0,
            bd=0,
            bg="#f0f0f0",  # Можно цвет фона окна, чтобы сливалось
        )
        # Канва просто лежит в центре
        self.preview_canvas.place(relx=0.5, rely=0.5, anchor="center")

        # события мыши
        self.preview_canvas.bind("<Enter>", self._on_enter_preview)
        self.preview_canvas.bind("<Leave>", self._on_leave_preview)

        self.preview_photo = None

        assets_dir = Path(__file__).resolve().parent / "assets"
        self.icon_prev = ImageTk.PhotoImage(Image.open(assets_dir / "nav_left.png"))
        self.icon_next = ImageTk.PhotoImage(Image.open(assets_dir / "nav_right.png"))

        self.canvas_img_id: int | None = None
        self.arrow_prev_id: int | None = None
        self.arrow_next_id: int | None = None

        # Блок XY (кладём в row=1 родителя)
        self.frm_offsets = ttk.Frame(parent, padding=(0, 8, 0, 4))

        row_x = ttk.Frame(self.frm_offsets)
        row_x.pack(fill="x", pady=(0, 2))
        ttk.Label(row_x, text="Смещение по X").pack(side="left", padx=6)
        self.scale_offset_x = ttk.Scale(
            row_x, from_=-100, to=100, orient="horizontal",
            variable=self.offset_x, command=self._on_offset_x_changed,
        )
        self.scale_offset_x.pack(side="left", fill="x", expand=True, padx=(0, 6))

        row_y = ttk.Frame(self.frm_offsets)
        row_y.pack(fill="x")
        ttk.Label(row_y, text="Смещение по Y").pack(side="left", padx=6)
        self.scale_offset_y = ttk.Scale(
            row_y, from_=-100, to=100, orient="horizontal",
            variable=self.offset_y, command=self._on_offset_y_changed,
        )
        self.scale_offset_y.pack(side="left", fill="x", expand=True, padx=(0, 6))

    def _on_container_resize(self, event):
        """
        Вызывается при изменении размера правого блока.
        1. Считаем идеальную ширину превью (9:16) от текущей высоты.
        2. Если изображения есть, автоматически расширяем окно по ширине при росте высоты.
        3. Применяем размеры к canvas и перерисовываем.
        """
        h = event.height
        if h < 100:
            return

        target_ratio = WIDTH / HEIGHT
        fit_mode = self._get_fit_mode()

        # cover_h — это "эталонная" высота для вычисления ШИРИНЫ (9:16)
        if fit_mode == "cover":
            cover_h = h
            canvas_h = h
        else:
            # fit: контейнер стал выше, потому что offsets скрылись,
            # но ширину мы хотим как в cover => отнимаем высоту offsets
            cover_h = max(1, h - self._reserved_offsets_h())
            canvas_h = h  # fit занимает всю высоту полотна справа

        canvas_w = int(cover_h * target_ratio)

        # 2. ИЗМЕНЕНИЕ: Автоматическое расширение окна при росте высоты
        if self._preview_visible:
            need_root_w = max(
                self.MIN_ROOT_W_WITH_PREVIEW,
                self.MIN_LEFT_W + canvas_w + self.PREVIEW_EXTRA_W,
            )
            self.minsize(need_root_w, self.MIN_ROOT_H)

            win_w = self.winfo_width()
            win_h = self.winfo_height()
            if win_w < need_root_w and not self._geo_lock:
                self._geo_lock = True
                self.geometry(f"{need_root_w}x{win_h}")
                self.after(0, lambda: setattr(self, "_geo_lock", False))

        # 3. Применяем размеры к контейнеру и canvas
        if int(self.frm_prev_container.cget("width") or 0) != canvas_w:
            self.frm_prev_container.configure(width=canvas_w, height=canvas_h)

        self.preview_canvas.place(
            relx=0.5, rely=0.5, anchor="center",
            width=canvas_w, height=canvas_h,
        )

        # 4. Перерисовываем картинку
        if self.preview_paths:
            self._update_preview_content(canvas_w, canvas_h)

    def _on_preview_resize(self, event):
        # если картинок нет — просто игнорируем
        if not self.preview_paths:
            return
        # пересобираем кадр под новый размер канвы
        self._update_preview()

    def _on_enter_preview(self, event):
        """Показываем стрелки при наведении мыши."""
        self._is_hovering = True  # <--- ЗАПОМИНАЕМ
        if not self.preview_paths:
            return
        if self.arrow_prev_id:
            self.preview_canvas.itemconfigure(self.arrow_prev_id, state="normal")
        if self.arrow_next_id:
            self.preview_canvas.itemconfigure(self.arrow_next_id, state="normal")

    def _on_leave_preview(self, event):
        """Прячем стрелки, когда мышь уходит."""
        self._is_hovering = False  # <--- ЗАПОМИНАЕМ
        if not self.preview_paths:
            return
        if self.arrow_prev_id:
            self.preview_canvas.itemconfigure(self.arrow_prev_id, state="hidden")
        if self.arrow_next_id:
            self.preview_canvas.itemconfigure(self.arrow_next_id, state="hidden")

    def _sync_sliders_with_current_offset(self):
        if not self.preview_paths or self._get_fit_mode() != "cover":
            return

        idx = self.preview_index.get()
        path = self.preview_paths[idx]
        key = str(path)

        ox, oy = self.crop_offsets.get(key, (0.0, 0.0))

        self._offset_syncing = True
        self.offset_x.set(ox * 100.0)
        self.offset_y.set(oy * 100.0)
        self._offset_syncing = False

    def _set_preview_visible(self, visible: bool):
        if visible and not self._preview_visible:
            self._preview_visible = True
            self.frm_preview_root.grid(
                row=0, column=1, sticky="nsew",
                padx=self._preview_padx, pady=10
            )

            self.update_idletasks()

            preview_h = self.frm_prev_container.winfo_height() or (self.winfo_height() - 20)
            need_w = self._min_w_with_preview(preview_h)

            self.minsize(need_w, self.MIN_ROOT_H)

            w = self.winfo_width()
            h = self.winfo_height()
            need_w2 = max(w, need_w)
            need_h2 = max(h, self.MIN_ROOT_H)
            if (w, h) != (need_w2, need_h2):
                self.geometry(f"{need_w2}x{need_h2}")

            return  # <-- тут ОК: показали превью и закончили

        if (not visible) and self._preview_visible:
            self.update_idletasks()
            win_w = self.winfo_width()
            win_h = self.winfo_height()

            prev_w = self.frm_preview_root.winfo_width()
            prev_pad = sum(self._preview_padx)  # (4,10) -> 14
            target_w = max(self.MIN_ROOT_W, win_w - (prev_w + prev_pad))

            self._preview_visible = False
            self.frm_preview_root.grid_remove()

            self.minsize(self.MIN_ROOT_W, self.MIN_ROOT_H)
            self.update_idletasks()

            if not self._geo_lock:
                self._geo_lock = True
                self.geometry(f"{target_w}x{win_h}")
                self.after(0, lambda: setattr(self, "_geo_lock", False))

    def _update_preview(self):
        # Просто берем текущие размеры канвы и рисуем
        w = self.preview_canvas.winfo_width()
        h = self.preview_canvas.winfo_height()
        if w > 1 and h > 1:
            self._update_preview_content(w, h)

    def _update_preview_content(self, w, h):
        if not self.preview_paths:
            self.preview_canvas.delete("all")
            return

        self._update_offset_state()

        n = len(self.preview_paths)
        idx = max(0, min(self.preview_index.get(), n - 1))
        self.preview_index.set(idx)
        path = self.preview_paths[idx]

        fit_mode = self._get_fit_mode()
        bg = self.bg.get()

        if fit_mode == "cover":
            key = str(path)
            ox, oy = self.crop_offsets.get(key, (0.0, 0.0))
            self.crop_offsets.setdefault(key, (ox, oy))
            offset = (ox, oy)
            fancy_bg = False
        else:
            offset = None
            fancy_bg = True

        # Генерируем кадр РОВНО под размер канвы (w, h)
        # Так как w/h мы сами высчитали по пропорции 9:16,
        # fit_to_canvas вернет идеальную картинку без полей.
        frame = fit_to_canvas(
            path,
            size=(w, h),
            bg=bg,
            mode=fit_mode,
            fancy_bg=fancy_bg,
            offset=offset,
        )

        self.preview_photo = ImageTk.PhotoImage(frame)
        self.preview_canvas.delete("all")

        # Рисуем по центру (канва и так ровно такого размера, так что 0,0 или центр - неважно)
        self.canvas_img_id = self.preview_canvas.create_image(
            w // 2, h // 2,
            image=self.preview_photo,
            anchor="center",
        )

        # Стрелки
        initial_state = "normal" if self._is_hovering else "hidden"
        padding = 20

        self.arrow_prev_id = self.preview_canvas.create_image(
            padding, h // 2, image=self.icon_prev, anchor="w", state=initial_state
        )
        self.arrow_next_id = self.preview_canvas.create_image(
            w - padding, h // 2, image=self.icon_next, anchor="e", state=initial_state
        )

        self.preview_canvas.tag_bind(self.arrow_prev_id, "<Button-1>", lambda e: self.prev_image())
        self.preview_canvas.tag_bind(self.arrow_next_id, "<Button-1>", lambda e: self.next_image())

    # ---- pickers ----
    # def pick_images_dir(self):
    #     d = filedialog.askdirectory(title="Папка с изображениями")
    #     if d:
    #         self.image_inputs = [d]
    #         self.lbl_imgs.config(text=f"Папка: {Path(d).name}")
    #
    #         imgs_input = self.image_inputs[0]
    #         self.preview_paths = _collect_images(imgs_input)
    #         self.preview_index.set(0)
    #         self._sync_sliders_with_current_offset()
    #         self._update_preview()

    def pick_images_files(self):
        files = filedialog.askopenfilenames(
            title="Выбрать изображения",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")]
        )
        if not files:
            return

        # добавляем новые файлы к уже выбранным, без дублей
        new_files = [f for f in files if f not in self.image_inputs]
        self.image_inputs.extend(new_files)

        if not self.image_inputs:
            self.lbl_imgs.config(text="—")
            return

        self.lbl_imgs.config(text=f"Выбрано файлов: {len(self.image_inputs)}")
        # как только есть изображения — показываем правый блок
        self._set_preview_visible(True)

        # превью всегда строим по всему списку файлов
        imgs_input = self.image_inputs
        self.preview_paths = _collect_images(imgs_input)
        self.preview_index.set(0)
        self._sync_sliders_with_current_offset()
        self._update_preview()
        self._recalc_duration()

        if not self.btn_imgs_clear.winfo_ismapped():
            self.btn_imgs_clear.pack(
                side="right",
                padx=(6, 0),
                before=self.btn_imgs_files,
            )

        # --- ФИКС ФОКУСА ---
        # 1. Принудительно возвращаем фокус нашему окну
        self.focus_force()

        # 2. Даем системе пару миллисекунд обработать события
        self.update_idletasks()

        # 3. Проверяем, где сейчас мышь
        x, y = self.winfo_pointerx(), self.winfo_pointery()
        widget_under_mouse = self.winfo_containing(x, y)

        # Если мышь висит над нашей канвой — вручную запускаем "ховер"
        if widget_under_mouse is self.preview_canvas:
            self._on_enter_preview(None)

    def clear_images(self):
        # сбрасываем стейт по картинкам
        self.image_inputs = []
        self.preview_paths = []
        self.preview_index.set(0)
        self.crop_offsets.clear()
        self.offset_x.set(0.0)
        self.offset_y.set(0.0)

        self.lbl_imgs.config(text="—")

        # прячем кнопку Очистить
        if self.btn_imgs_clear.winfo_ismapped():
            self.btn_imgs_clear.pack_forget()

        # очищаем превью
        self._update_preview()

        # прячем правый блок
        self._set_preview_visible(False)

        self.total_duration.set(0.0)
        self._recalc_duration()

    def pick_audio(self):
        f = filedialog.askopenfilename(
            title="Выбрать аудио",
            filetypes=[("Audio", "*.mp3 *.wav")]
        )
        if f:
            self.audio_path = f
            self.lbl_audio.config(text=Path(f).name)
            if not self.btn_audio_clear.winfo_ismapped():
                self.btn_audio_clear.pack(
                    side="right",
                    padx=(6, 0),
                    before=self.btn_audio_choose,
                )

    def clear_audio(self):
        self.audio_path = None
        self.lbl_audio.config(text="—")
        if self.btn_audio_clear.winfo_ismapped():
            self.btn_audio_clear.pack_forget()

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

    def _get_fit_mode(self) -> str:
        mapping = {
            "обрезать лишнее": "cover",
            "добавить поля": "fit",
        }
        return mapping.get(self.fit_mode_ui.get(), "cover")

    def _get_audio_mode(self) -> str:
        mapping = {
            "обрезать по ролику": "trim",
            "зациклить": "loop",
        }
        return mapping.get(self.audio_mode_ui.get(), "trim")

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

    def _on_fit_mode_changed(self, *args):
        self._update_offset_state()
        if self._get_fit_mode() == "cover":
            self._sync_sliders_with_current_offset()
        self._update_preview()

    def _update_offset_state(self, *args):
        if not self.preview_paths:
            return  # пока нет картинок – не показываем

        if self._get_fit_mode() == "cover":
            # показываем XY под канвой
            if not self.frm_offsets.winfo_ismapped():
                self.frm_offsets.grid(
                    row=1, column=0,
                    sticky="ew",
                    padx=0,
                    pady=0,
                )
        else:
            # скрываем XY
            if self.frm_offsets.winfo_ismapped():
                self.frm_offsets.grid_remove()

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

    def _recalc_duration(self, *args):
        if self._duration_syncing:
            return

        n = len(self.preview_paths) or len(self.image_inputs)
        if n <= 0:
            return

        mode = self.duration_mode.get()

        self._duration_syncing = True
        try:
            if mode == "per_frame":
                sec_per = float(self.sec_per.get() or 0.0)
                if sec_per <= 0:
                    return
                total = total_for(n, sec_per, transitions=bool(self.transitions.get()))
                self.total_duration.set(round(max(0.0, total), 2))
            else:
                total = float(self.total_duration.get() or 0.0)
                if total <= 0:
                    return
                sec_per = sec_per_for_total(n, total, transitions=bool(self.transitions.get()))
                self.sec_per.set(round(sec_per, 3))

        finally:
            self._duration_syncing = False

    # ---- rendering ----
    def start_render(self):
        try:
            if not self.image_inputs:
                raise ValueError("Выбери изображения")

            out_raw = self.ent_out.get().strip()
            if not out_raw:
                # дефолт с меткой времени
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_raw = f"output/video_{stamp}.mp4"
                self.ent_out.delete(0, "end")
                self.ent_out.insert(0, out_raw)

            out_path = Path(out_raw).expanduser()
            out_path.parent.mkdir(parents=True, exist_ok=True)

            if out_path.exists():
                overwrite = messagebox.askyesno(
                    "Такой файл уже существует",
                    f"Файл с именем «{out_path.name}» уже есть в этой папке.\nХотите его перезаписать?"
                )
                if not overwrite:
                    return  # просто выходим, ничего не делаем

            self.out_path = str(out_path)
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
                    fit_mode = self._get_fit_mode()

                    # offset имеет смысл только в cover
                    if fit_mode == "cover":
                        crop_offsets: CropOffsets = {}
                        for p in img_paths:
                            key = str(p)
                            crop_offsets[key] = self.crop_offsets.get(key, (0.0, 0.0))
                        fancy_bg = False
                    else:
                        crop_offsets = None
                        fancy_bg = True

                    # режим длительности
                    duration_mode = self.duration_mode.get()
                    sec_per = float(self.sec_per.get())
                    fps = int(self.fps.get())
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
                        sec_per=sec_per,
                        fps=fps,
                        bg=self.bg.get(),  # технический, по сути не используется при fancy_bg
                        audio=self.audio_path,
                        transitions=bool(self.transitions.get()),
                        audio_adjust=self._get_audio_mode(),
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
            self.status.set("Кодирую видео… Процесс может занять несколько минут…")

    def _on_done(self, result_path: str):
        self._set_running(False)
        self.status.set("Готово.")
        self.btn_open_dir.configure(state="normal")   # теперь есть что открывать
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
