import json
import os
import sys
import fitz
from PIL import Image
from pathlib import Path

# Adicionar o diretório tools/questions ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Importar funções do ingest
from ingest import build_question_rect_index, _auto_trim_whitespace

PROJECT_ROOT = Path(__file__).parent.parent.parent
PROVAS_DIR = PROJECT_ROOT / "provas"
ASSETS_DIR = PROJECT_ROOT / "public" / "assets" / "questions"
OUTPUT_DIR = PROJECT_ROOT / "tools" / "questions" / "out"

# Carregar JSON
json_path = PROJECT_ROOT / "public" / "data" / "questions" / "fuvest-2021.json"
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Identificar questões sem imagem própria (as que faltavam)
missing_images = []
for q in data["questions"]:
    qnum = q["number"]
    asset_path = PROJECT_ROOT / "public" / q["assets"]["questionImage"].lstrip("/")
    if not asset_path.exists():
        missing_images.append(qnum)

if not missing_images:
    print("[OK] Todas as questões já têm imagens!")
    sys.exit(0)

print(f"[*] Questões sem imagem: {len(missing_images)}")
print(f"[*] Números: {missing_images}")

# Carregar imagens renderizadas
year = 2021
year_output_dir = OUTPUT_DIR / str(year) / "pages"
page_images = sorted(year_output_dir.glob("page_*.png"))

if not page_images:
    print("[ERRO] Imagens das páginas não encontradas. Execute ingest primeiro.")
    sys.exit(1)

print(f"[OK] {len(page_images)} páginas renderizadas encontradas")

# Construir índice de bboxes
pdf_path = PROVAS_DIR / "p21.pdf"
print("[*] Construindo índice de bboxes...")
rect_index = build_question_rect_index(str(pdf_path), dpi=200)

# Recriar imagens faltantes
print(f"\n[*] Recriando {len(missing_images)} imagens...")
padding = 15

for qnum in missing_images:
    if qnum not in rect_index:
        print(f"[WARN] Q{qnum}: não encontrada no índice PDF")
        continue
    
    info = rect_index[qnum]
    bbox = info["bbox"]
    page_idx = info["page"] - 1
    
    if page_idx < 0 or page_idx >= len(page_images):
        print(f"[WARN] Q{qnum}: página {info['page']} inválida")
        continue
    
    try:
        with Image.open(page_images[page_idx]) as img:
            img_w, img_h = img.size
            x = max(0, bbox['x'] - padding)
            y = max(0, bbox['y'] - padding)
            w = min(img_w - x, bbox['w'] + (padding * 2))
            h = min(img_h - y, bbox['h'] + (padding * 2))
            
            cropped_img = img.crop((x, y, x + w, y + h))
            cropped_img = _auto_trim_whitespace(cropped_img, pad=12)
            
            asset_dir = ASSETS_DIR / str(year) / f"q{qnum:02d}"
            asset_dir.mkdir(parents=True, exist_ok=True)
            asset_path = asset_dir / "image.png"
            cropped_img.save(asset_path, "PNG")
            
            print(f"[OK] Q{qnum}: imagem criada")
    except Exception as e:
        print(f"[ERRO] Q{qnum}: {e}")

print(f"\n[DONE] Processo concluído!")
