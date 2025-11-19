from .pdf_converter import PDFConverter

# Реестр конвертеров
_converters = {
    "pdf": PDFConverter
}


def get_converter(ext: str):
    return _converters.get(ext)
