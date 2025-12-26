"""
Corrige as bounding boxes de 2021 mantendo os textos do Gemini Vision.
Substitui bboxes incorretas do Gemini por bboxes determinísticas do PyMuPDF.
"""
import json
import os
import sys
import fitz
from PIL import Image
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ingest import build_question_rect_index, _auto_trim_whitespace

PROJECT_ROOT = Path(__file__).parent.parent.parent
PROVAS_DIR = PROJECT_ROOT / "provas"
ASSETS_DIR = PROJECT_ROOT / "public" / "assets" / "questions"
OUTPUT_DIR = PROJECT_ROOT / "tools" / "questions" / "out"
DATA_DIR = PROJECT_ROOT / "public" / "data" / "questions"

print("[*] Carregando JSON de 2021...")
json_path = DATA_DIR / "fuvest-2021.json"
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"[OK] {len(data['questions'])} questões carregadas")

# Construir índice de bboxes determinísticas
pdf_path = PROVAS_DIR / "p21.pdf"
print("[*] Construindo índice de bboxes determinísticas (PyMuPDF)...")
rect_index = build_question_rect_index(str(pdf_path), dpi=200)
print(f"[OK] {len(rect_index)} bboxes detectadas")

# Carregar imagens renderizadas
year_output_dir = OUTPUT_DIR / "2021" / "pages"
page_images = sorted(year_output_dir.glob("page_*.png"))
print(f"[OK] {len(page_images)} páginas renderizadas")

# Corrigir bboxes e recriar imagens
padding = 15
corrected = 0
failed = []

print("\n[*] Corrigindo bboxes e recriando imagens...")
for q in data["questions"]:
    qnum = q["number"]
    
    # Verificar se tem bbox determinística
    if qnum not in rect_index:
        print(f"[WARN] Q{qnum}: não encontrada no índice PyMuPDF")
        failed.append(qnum)
        continue
    
    # Obter bbox determinística
    info = rect_index[qnum]
    new_bbox = info["bbox"]
    new_page = info["page"]
    
    # Atualizar metadados no JSON (não sobrescrever stem/options do Gemini!)
    # Apenas adicionar/atualizar campos internos para referência
    if "page" not in q or q["page"] != new_page:
        q["page"] = new_page
    
    # Recriar imagem com bbox correta
    page_idx = new_page - 1
    if page_idx < 0 or page_idx >= len(page_images):
        print(f"[WARN] Q{qnum}: página {new_page} inválida")
        failed.append(qnum)
        continue
    
    try:
        with Image.open(page_images[page_idx]) as img:
            img_w, img_h = img.size
            x = max(0, new_bbox['x'] - padding)
            y = max(0, new_bbox['y'] - padding)
            w = min(img_w - x, new_bbox['w'] + (padding * 2))
            h = min(img_h - y, new_bbox['h'] + (padding * 2))
            
            cropped_img = img.crop((x, y, x + w, y + h))
            cropped_img = _auto_trim_whitespace(cropped_img, pad=12)
            
            asset_dir = ASSETS_DIR / "2021" / f"q{qnum:02d}"
            asset_dir.mkdir(parents=True, exist_ok=True)
            asset_path = asset_dir / "image.png"
            cropped_img.save(asset_path, "PNG")
            
            corrected += 1
            if qnum % 10 == 0:
                print(f"[OK] Q{qnum}: imagem corrigida ({corrected}/90)")
    except Exception as e:
        print(f"[ERRO] Q{qnum}: {e}")
        failed.append(qnum)

# Salvar JSON atualizado (com páginas corretas)
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n[DONE] Processo concluído!")
print(f"[OK] {corrected} imagens corrigidas")
if failed:
    print(f"[WARN] {len(failed)} questões falharam: {failed}")
else:
    print(f"[OK] Todas as 90 questões têm imagens corretas!")
