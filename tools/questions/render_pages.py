"""Renderizador determinístico de páginas.

Objetivo:
- Gerar /tools/questions/out/<ano>/pages/page_XX.png com TODAS as páginas do PDF (incluindo capa)
- Copiar para /public/assets/pages/<ano>/page_XX.png (modo "Ver Página")

Isso padroniza o site para sempre ter page_01.png e elimina offsets.
"""

import os
import argparse
import fitz


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "tools", "questions", "out")
PROVAS_DIR = os.path.join(PROJECT_ROOT, "provas")


def render_year(year: int, dpi: int = 200) -> list[str]:
    pdf_path = os.path.join(PROVAS_DIR, f"p{str(year)[-2:]}.pdf")
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")

    year_output_dir = os.path.join(OUTPUT_DIR, str(year), "pages")
    os.makedirs(year_output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    out_paths: list[str] = []
    try:
        for page_idx in range(len(doc)):
            page = doc.load_page(page_idx)
            pix = page.get_pixmap(dpi=dpi)
            out_path = os.path.join(year_output_dir, f"page_{page_idx + 1:02d}.png")
            pix.save(out_path)
            out_paths.append(out_path)
    finally:
        doc.close()
    return out_paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    pages = render_year(args.year, dpi=args.dpi)
    print(f"[OK] {len(pages)} páginas renderizadas: {args.year}")


if __name__ == "__main__":
    main()

