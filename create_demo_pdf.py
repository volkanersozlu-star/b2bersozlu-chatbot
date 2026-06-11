"""
Minimal PDF olusturucu - standart kutuphaneler haric bagimlilik gerektirmez.
Sirket demo bilgilerini docs/sirket_bilgileri.pdf olarak kaydeder.
"""

import struct
import zlib
from pathlib import Path

COMPANY_TEXT = """\
TECHNOVA YAZILIM A.S. - SIRKET TANITIM DOKUMANI
================================================

GENEL BILGILER
--------------
Sirket Adi   : TechNova Yazilim A.S.
Kurulus Yili : 2015
Merkez       : Istanbul, Maslak Teknokent
Sektor       : Kurumsal Yazilim ve Yapay Zeka Cozumleri
Calisan Sayisi: 320 kisi
Web Sitesi   : www.technova.com.tr
E-posta      : info@technova.com.tr
Telefon      : +90 212 555 0100

MISYON
------
TechNova olarak misyonumuz; Turk sirkerlerin dijital donusumunu
hizlandirmak, yapay zeka ve otomasyon cozumleriyle is surecleri
daha verimli hale getirmektir.

VIZYON
------
2030 yilina kadar Orta Dogu ve Avrupa pazarinda en guclu
yapay zeka odakli yazilim sirketi olmak.

URUNLER VE HIZMETLER
--------------------
1. TechNova CRM Pro
   - Musterilerinizi 360 derece yonetin
   - Yapay zeka destekli satis tahmini
   - Fiyat: Aylik 499 TL / kullanici

2. TechNova ERP Suite
   - Muhasebe, stok, insan kaynaklari entegre modulleri
   - Bulut ve on-premise secenek
   - Fiyat: Yillik lisans, sirket buyuklugune gore

3. TechNova AI Chatbot
   - Sirket belgelerinizden beslenen yapay zeka asistani
   - Cok dilli destek (Turkce, Ingilizce, Almanca)
   - Fiyat: Aylik 1.200 TL / 1.000 sorgu

4. TechNova Analytics
   - Gercek zamanli is zekasi panelleri
   - Otomatik rapor uretimi
   - Fiyat: Aylik 799 TL

ORTAKLIKLAR VE SERTIFIKALAR
----------------------------
- Microsoft Gold Partner
- ISO 27001 Bilgi Guvenligi Sertifikasi
- ISO 9001 Kalite Yonetim Sertifikasi
- AWS Advanced Consulting Partner
- TUBITAK TEYDEB Destekli AR-GE Merkezi

REFERANS MUSTERILER
-------------------
- Akbank - CRM Pro ve Analytics entegrasyonu
- Turk Telekom - ERP Suite kurumsal lisansi
- Migros - AI Chatbot musteri hizmetleri
- Koc Holding - Analitik ve raporlama platformu
- Petrol Ofisi - ERP ve AI chatbot entegrasyonu

INSAN KAYNAKLARI
----------------
Acik Pozisyonlar:
  - Senior Backend Gelistirici (Python/Go)
  - Yapay Zeka Muhendisi (LLM / RAG)
  - Bulut Mimarisi Uzmani (AWS/Azure)
  - Satis Muduru (Kurumsal)

Yan Haklar:
  - Ozel saglik sigortasi
  - Ulasim + yemek yardimi
  - Yillik egitim butcesi: 5.000 TL/kisi
  - Esnek calisma saatleri ve uzaktan calisma

ILETISIM BILGILERI
------------------
Genel Mudurluk : Buyukdere Cad. No:123, Maslak, Istanbul
Destek Hatti   : 0850 222 8686 (hafta ici 09:00-18:00)
Satis Ekibi    : satis@technova.com.tr
Teknik Destek  : destek@technova.com.tr
LinkedIn       : linkedin.com/company/technova-yazilim
"""


def create_pdf(text: str, output_path: str):
    lines = text.split("\n")

    # Build content stream
    content_lines = []
    content_lines.append("BT")
    content_lines.append("/F1 10 Tf")
    content_lines.append("50 780 Td")
    content_lines.append("14 TL")

    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        encoded = safe.encode("latin-1", errors="replace").decode("latin-1")
        content_lines.append(f"({encoded}) Tj")
        content_lines.append("T*")

    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("latin-1")

    objects = []

    # obj 1: Catalog
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

    # obj 2: Pages
    objects.append(b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>")

    # Split content into two pages
    half = len(lines) // 2
    for page_lines in [lines[:half], lines[half:]]:
        page_content_lines = []
        page_content_lines.append("BT")
        page_content_lines.append("/F1 10 Tf")
        page_content_lines.append("50 780 Td")
        page_content_lines.append("14 TL")
        for line in page_lines:
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            encoded = safe.encode("latin-1", errors="replace").decode("latin-1")
            page_content_lines.append(f"({encoded}) Tj")
            page_content_lines.append("T*")
        page_content_lines.append("ET")
        page_stream = "\n".join(page_content_lines).encode("latin-1")
        objects.append(page_stream)

    font_obj = (
        b"<< /Type /Font /Subtype /Type1 "
        b"/BaseFont /Courier "
        b"/Encoding /WinAnsiEncoding >>"
    )

    pdf_parts = [b"%PDF-1.4\n"]
    offsets = []

    obj_num = 1
    obj_data = []

    # obj 1: Catalog
    offsets.append(len(b"".join(pdf_parts)))
    part = f"{obj_num} 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n".encode()
    pdf_parts.append(part)
    obj_num += 1

    # page streams and page objects will be: stream at obj 3,4 and page dicts at 5,6
    # Let's redo with proper numbering:
    # 1 = Catalog, 2 = Pages, 3 = Page1, 4 = Content1, 5 = Page2, 6 = Content2, 7 = Font

    half = len(lines) // 2
    page_line_groups = [lines[:half], lines[half:]]
    streams = []
    for page_lines in page_line_groups:
        parts_c = ["BT", "/F1 10 Tf", "50 780 Td", "14 TL"]
        for ln in page_lines:
            safe = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            enc = safe.encode("latin-1", errors="replace").decode("latin-1")
            parts_c.append(f"({enc}) Tj")
            parts_c.append("T*")
        parts_c.append("ET")
        streams.append("\n".join(parts_c).encode("latin-1"))

    out = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    xref = {}

    def add_obj(n, raw_header, stream=None):
        xref[n] = len(b"".join(out))
        if stream is not None:
            obj_bytes = (
                f"{n} 0 obj\n{raw_header}\n"
                f"stream\n"
            ).encode() + stream + b"\nendstream\nendobj\n"
        else:
            obj_bytes = f"{n} 0 obj\n{raw_header}\nendobj\n".encode()
        out.append(obj_bytes)

    add_obj(1, "<< /Type /Catalog /Pages 2 0 R >>")
    add_obj(2, "<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>")

    for i, (stream_data, content_obj_num, page_obj_num) in enumerate(
        [(streams[0], 4, 3), (streams[1], 6, 5)]
    ):
        add_obj(
            page_obj_num,
            f"<< /Type /Page /Parent 2 0 R "
            f"/Resources << /Font << /F1 7 0 R >> >> "
            f"/MediaBox [0 0 612 842] "
            f"/Contents {content_obj_num} 0 R >>",
        )
        add_obj(
            content_obj_num,
            f"<< /Length {len(stream_data)} >>",
            stream=stream_data,
        )

    add_obj(
        7,
        "<< /Type /Font /Subtype /Type1 /BaseFont /Courier "
        "/Encoding /WinAnsiEncoding >>",
    )

    xref_offset = len(b"".join(out))
    n_objects = 8

    xref_table = [b"xref\n", f"0 {n_objects}\n".encode(), b"0000000000 65535 f \n"]
    for i in range(1, n_objects):
        xref_table.append(f"{xref.get(i, 0):010d} 00000 n \n".encode())

    out.extend(xref_table)
    out.append(
        f"trailer\n<< /Size {n_objects} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(b"".join(out))
    print(f"PDF olusturuldu: {output_path}")


if __name__ == "__main__":
    create_pdf(COMPANY_TEXT, "docs/sirket_bilgileri.pdf")
