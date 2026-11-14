"""Validação das fotos PELO CONTEÚDO (RF07). O nome e o Content-Type enviados são ignorados.

Um arquivo `virus.exe` renomeado para `foto.jpg` é recusado porque o Pillow não reconhece
uma imagem nele. Um JPEG enviado como `foto.png` é aceito e gravado como `.jpg`.
"""

import io
import warnings

from django.core.files.base import ContentFile
from PIL import Image

# Formato detectado pelo Pillow -> (tipo MIME, extensão gravada no disco)
KNOWN_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}
MAX_PIXELS = 40_000_000  # ~ 7000 x 5700: acima disso é ataque ("bomba de descompressão")


class PhotoError(ValueError):
    """Mensagem pronta para mostrar ao usuário."""


def validate_photo(uploaded, *, max_bytes: int, accepted_types: list[str]) -> ContentFile:
    """Devolve um arquivo novo, com nome `foto.<ext do conteúdo>`, ou levanta PhotoError."""
    if uploaded.size > max_bytes:
        raise PhotoError(f"maior que o limite de {max_bytes // (1024 * 1024)} MB")
    data = uploaded.read()

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                detected = image.format
                width, height = image.size
                image.verify()  # confere a estrutura do arquivo (truncado, corrompido)
    except Exception as exc:  # o Pillow levanta vários tipos diferentes para "não é imagem"
        raise PhotoError("não é uma imagem válida") from exc

    if detected not in KNOWN_FORMATS or KNOWN_FORMATS[detected][0] not in accepted_types:
        names = ", ".join(t.removeprefix("image/") for t in accepted_types)
        raise PhotoError(f"tipo não aceito (aceitos: {names})")
    if width * height > MAX_PIXELS:
        raise PhotoError("imagem grande demais em pixels")

    return ContentFile(data, name=f"foto.{KNOWN_FORMATS[detected][1]}")
