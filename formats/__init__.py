from .pdf_converter import PDFConverter
from .excel_converter import ExcelConverter

# Реестр конвертеров
_converters = {
    "pdf": PDFConverter,
    "xlsx": ExcelConverter,
    "xls": ExcelConverter,
}

def get_converter(ext: str):
    return _converters.get(ext)
