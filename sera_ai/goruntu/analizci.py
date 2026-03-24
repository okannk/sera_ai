"""
Claude Vision ile sera bitki sağlığı analizi.

Kullanım:
    from sera_ai.goruntu.analizci import goruntu_analiz_et
    sonuc = goruntu_analiz_et(bytes_data, "image/jpeg", "Domates Sera 1")
"""
from __future__ import annotations

import base64
import json

import anthropic

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def goruntu_analiz_et(goruntu_bytes: bytes, mime_type: str, sera_isim: str) -> dict:
    """Claude Vision ile bitki sağlığı analizi yap.

    Args:
        goruntu_bytes: Ham görüntü verisi (JPEG/PNG/WebP).
        mime_type:     MIME tipi, ör. "image/jpeg".
        sera_isim:     Sera adı (prompt'a dahil edilir).

    Returns:
        Analiz sonucu dict:
            saglik_skoru  (0-100)
            genel_durum   ("İyi" | "Orta" | "Kötü")
            bulgular      [str, ...]
            oneriler      [str, ...]
            acil_mudahale bool
            ozet          str
    """
    b64 = base64.standard_b64encode(goruntu_bytes).decode("utf-8")

    mesaj = _get_client().messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": b64,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        f"Sen bir tarım uzmanısın. Bu fotoğraf '{sera_isim}' serasından.\n\n"
                        "Fotoğrafı analiz et ve sadece JSON formatında yanıt ver (başka hiçbir şey yazma):\n"
                        "{\n"
                        '  "saglik_skoru": <0-100 arası sayı>,\n'
                        '  "genel_durum": "<İyi/Orta/Kötü>",\n'
                        '  "bulgular": ["<bulgu 1>", "<bulgu 2>"],\n'
                        '  "oneriler": ["<öneri 1>", "<öneri 2>"],\n'
                        '  "acil_mudahale": <true/false>,\n'
                        '  "ozet": "<1-2 cümle özet>"\n'
                        "}\n\n"
                        "Şunlara bak: yaprak rengi, hastalık belirtileri, "
                        "nem stresi, zararlı böcek, büyüme durumu."
                    ),
                },
            ],
        }],
    )

    icerik = mesaj.content[0].text.strip()

    # Markdown kod bloğu varsa soyul
    if "```" in icerik:
        parcalar = icerik.split("```")
        icerik = parcalar[1] if len(parcalar) > 1 else parcalar[0]
        if icerik.startswith("json"):
            icerik = icerik[4:]

    return json.loads(icerik.strip())
