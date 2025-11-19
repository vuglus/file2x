# formats/pdf_converter.py
import math
import itertools
import pdfplumber
from .base import BaseConverter


def _group_by_y(chars, y_tol=3):
    """
    Группирует символы по близким координатам Y (строки).
    Возвращает список строк: каждая — список символов.
    chars: список page.chars (каждый имеет 'text', 'x0','x1','top','bottom','size')
    """
    # сортируем по top (y)
    chars_sorted = sorted(chars, key=lambda c: c["top"])
    groups = []
    for c in chars_sorted:
        if not groups:
            groups.append([c])
            continue
        last = groups[-1]
        # сравниваем с первой буквой в группе (можно улучшить)
        if abs(c["top"] - last[0]["top"]) <= y_tol:
            last.append(c)
        else:
            groups.append([c])
    return groups


def _line_from_chars(chars):
    """Собирает строку текста и усреднённый размер шрифта из символов."""
    if not chars:
        return {"text": "", "size": 0, "x0": 0}

    # сортируем по x0
    chars_sorted = sorted(chars, key=lambda c: c["x0"])

    # собираем текст
    text = "".join(c["text"] for c in chars_sorted).replace("\x00", "").strip()

    # средний размер шрифта
    size = sum(c.get("size", 0) for c in chars_sorted) / len(chars_sorted)

    # минимальный x0 (отступ слева)
    x0 = min(c.get("x0", 0) for c in chars_sorted)

    return {"text": text, "size": size, "x0": x0}

class PDFConverter(BaseConverter):
    def convert(self, path: str) -> str:
        md_pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                md_pages.append(self._page_to_md(page))
        return "\n\n".join(p for p in md_pages if p.strip())

    def _page_to_md(self, page):
        md_blocks = []

        # 1) Таблицы: сначала более "жёсткий" способ через find_tables с линиями
        table_blocks = []
        try:
            table_settings = {
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                # "intersection_tolerance": 3.0,
            }
            tables = page.find_tables(table_settings=table_settings)
            for t in tables:
                table_blocks.append(self._table_obj_to_md(t))
        except Exception:
            tables = []

        # Fall back на extract_tables (stream)
        if not table_blocks:
            try:
                for tbl in page.extract_tables():
                    if tbl and any(any(cell for cell in row) for row in tbl):
                        table_blocks.append(self._simple_table_to_md(tbl))
            except Exception:
                pass

        # 2) Заголовки и основной текст: анализируем page.chars чтобы детектить размеры по строкам
        chars = page.chars  # список символов с координатами и size
        if chars:
            # Группируем символы в строки по top (y)
            y_tol = 3  # пиксели допуска
            lines_chars = _group_by_y(chars, y_tol=y_tol)
            # Конвертируем в линии с текстом и avg size
            lines = [ _line_from_chars(lc) for lc in lines_chars ]
            # Вычисляем средний и максимальный size на странице
            sizes = [ln["size"] for ln in lines if ln["size"] > 0]
            avg_size = sum(sizes) / len(sizes) if sizes else 10
            max_size = max(sizes) if sizes else avg_size

            # Проходим по линиям и классифицируем
            text_lines_md = []
            for ln in lines:
                txt = ln["text"].strip()
                if not txt:
                    continue

                # --- попытка определить заголовок ---
                lvl = self._estimate_heading_level(ln["size"], avg_size, max_size)
                if lvl > 0:
                    text_lines_md.append(f"{'#'*lvl} {txt}")
                    continue

                # --- попытка определить список (марки или нумерация) ---
                list_md = self._try_detect_list_item(txt, ln["x0"])
                if list_md is not None:
                    text_lines_md.append(list_md)
                    continue

                # --- обычная строка ---
                text_lines_md.append(txt)

            body_md = "\n".join(text_lines_md)
        else:
            # fallback: простой текст
            body_md = (page.extract_text() or "").strip()

        # Объединяем: сначала текст, затем таблицы (если таблицы визуально были отдельными блоками,
        # можно вставлять между, но это простая стратегия)
        if body_md:
            md_blocks.append(body_md)
        if table_blocks:
            md_blocks.append("\n\n".join(table_blocks))

        return "\n\n".join(md_blocks)

    def _estimate_heading_level(self, size, avg, max_size):
        """
        Простая эвристика:
         - самый большой текст на странице -> H1
         - >= 1.4 * avg -> H2
         - >= 1.2 * avg -> H3
        """
        if size >= max_size * 0.95:
            return 1
        if size >= avg * 1.4:
            return 2
        if size >= avg * 1.2:
            return 3
        return 0

    def _try_detect_list_item(self, text_line, x0):
        """
        Простая детекция маркеров списка:
         - начинает с '-', '•', '*', '–' -> маркер
         - начинается с '1.' 'a)' '1)' и т.д. -> нумерованный
         - иначе по смещению x0 (indent) можно вернуть маркер '-' если сильно отступлено
        Возвращает строку markdown или None.
        """
        stripped = text_line.lstrip()
        # маркерные
        if stripped.startswith(("-", "•", "*", "–", "—")):
            # убираем символ и пробел
            rest = stripped[1:].lstrip()
            return f"- {rest}"
        # нумерация
        if stripped and (stripped[0].isdigit() or (len(stripped) > 1 and stripped[1] in ").")):
            # вырезаем префикс "1." или "1)"
            parts = stripped.split(None, 1)
            if parts:
                # просто вернуть нумерованный маркер как обычный '- ' (md ограничен)
                rest = parts[1] if len(parts) > 1 else ""
                return f"1. {rest}"
        # по отступу (если x0 больше среднего — вложенный список)
        # простая эвристика: если x0 > 50 px (можно настроить) — считаем списком
        if x0 and x0 > 40:
            return f"- {stripped}"
        return None

    def _simple_table_to_md(self, table):
        # table — список рядов (каждый ряд — список ячеек)
        if not table or not any(table):
            return ""
        headers = table[0]
        rows = table[1:] if len(table) > 1 else []
        # очистка ячеек
        def clean(cell):
            if cell is None:
                return ""
            return " ".join(str(cell).split()).strip()
        md = []
        md.append("| " + " | ".join(clean(h) for h in headers) + " |")
        md.append("| " + " | ".join("---" for _ in headers) + " |")
        for r in rows:
            md.append("| " + " | ".join(clean(c) for c in r) + " |")
        return "\n".join(md)

    def _table_obj_to_md(self, table_obj):
        """
        Преобразует результат page.find_tables(...) (Table объект)
        table_obj.rows даёт список рядов (каждый — список клеток)
        """
        try:
            rows = table_obj.rows
        except Exception:
            # fallback
            return self._simple_table_to_md(table_obj)
        if not rows:
            return ""
        # Приводим все ячейки в строки
        def clean(cell):
            if cell is None:
                return ""
            # cell может быть либо строкой, либо dict/obj с text
            if isinstance(cell, (list, tuple)):
                # объединяем многострочные ячейки
                return " ".join(" ".join(str(x).split()) for x in cell).strip()
            return " ".join(str(cell).split()).strip()

        headers = rows[0]
        rest = rows[1:] if len(rows) > 1 else []
        md = []
        md.append("| " + " | ".join(clean(h) for h in headers) + " |")
        md.append("| " + " | ".join("---" for _ in headers) + " |")
        for r in rest:
            md.append("| " + " | ".join(clean(c) for c in r) + " |")
        return "\n".join(md)
