# image2video

Утилита, которая собирает вертикальное видео (1080×1920) из набора изображений. Есть **GUI на Tkinter** с превью и ручной подстройкой crop-offsets (для `cover`), а также **CLI на Click** для пакетных прогонов.

## Возможности

- Вход: набор изображений (jpg/jpeg/png/webp)
- Выход: `.mp4 (H.264 + AAC)`
- Режимы вписывания:
  - `cover` — заполняем кадр, лишнее обрезаем (в GUI доступны `offset_x/offset_y`)
  - `fit` — вписываем целиком + фон (однотонный или “fancy” размытие)
- Движение:
  - `none` — статика
  - `kenburns` — плавный zoom/pan
- Переходы: `crossfade` между слайдами
- Аудио (опционально): `trim` или `loop` до длины видео
- Длительность:
  - `sec_per` (длина кадра)
  - или `total_duration` (общая длина — `sec_per` пересчитывается)

---

## Установка

### 1) Виртуальное окружение
```bash
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows
```

### 2) Зависимости
```bash
pip install -r requirements.txt
```

### 3) FFmpeg (обязателен для moviepy)
✅ macOS: проверено 
```bash
brew install ffmpeg
```
⚠️ Linux (Ubuntu/Debian): не проверял, но обычно так
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
```
⚠️ Windows: не проверял, но обычно так (через Chocolatey)
```bash
choco install ffmpeg
```

⸻

## Запуск GUI
```bash
python -m vv.gui
```
Что есть в GUI:
* выбор изображений (несколько файлов)
* опциональное аудио
* fit/cover
* длительность: либо per-frame, либо total
* transitions
* kenburns (чекбокс “Зум/сдвиг кадра”)
* справа — превью 9:16, стрелки навигации по hover
* в cover появляются слайдеры Смещение X/Y (сохраняются per-image в crop_offsets)

⸻

## Запуск CLI
```bash
python -m vv.cli -i path/to/img1.jpg -i path/to/img2.png -o output/video.mp4
```
Примеры

1) Простой рендер пачки
```bash
python -m vv.cli \
  -i images/ \
  -o output/video.mp4 \
  --sec-per 4 \
  --fps 30 \
  --fit-mode cover
```
2) Общая длина ролика (sec_per будет пересчитан)
```bash
python -m vv.cli \
  -i images/ \
  -o output/video.mp4 \
  --total 60 \
  --transitions
```
3) Fit + fancy background
```bash
python -m vv.cli \
  -i images/ \
  -o output/video.mp4 \
  --fit-mode fit \
  --fancy-bg
```
4) С музыкой + loop
```bash
python -m vv.cli \
  -i images/ \
  -a music.mp3 \
  -o output/video.mp4 \
  --audio-adjust loop
```
Посмотреть полный help
```bash
python -m vv.cli --help
```

⸻

## Тесты

Запуск всех тестов:
```bash
pytest
```

⸻

## Примечания

* Видео пишется через libx264, аудио — aac.
* transitions=True уменьшает “эффективную” длительность каждого кадра из-за overlap (это учтено через sec_per_for_total(...) и fade_for(...)).
* В GUI offset_x/offset_y имеет смысл только в cover. В fit offsets скрываются и не применяются.

⸻

## Структура проекта 
* vv/pipeline.py — сборка клипов, переходы, аудио, рендер
* vv/gui.py — Tkinter GUI, превью, offsets
* vv/cli.py — Click CLI
* vv/image.py — fit_to_canvas(...)
* vv/audio.py — prepare_audio(...)
* vv/duration.py — расчеты длительностей/фейдов
* tests/ — pytest

