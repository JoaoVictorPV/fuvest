"""
Completa questões faltantes usando PyMuPDF (determinístico) + OCR local.
Fallback robusto quando Gemini Vision falha.
"""
import os
import sys
import json
import argparse
import fitz
from PIL import Image

if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PROVAS_DIR = os.path.join(PROJECT_ROOT, "provas")
DATA_DIR = os.path.join(PROJECT_ROOT, "public", "data", "questions")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "public", "assets", "questions")
OUT_DIR = os.path.join(PROJECT_ROOT, "tools", "questions", "out")

# Importa módulo OCR local
try:
    from ocr import ocr_image, parse_alternatives_from_ocr, extract_stem_from_ocr, init_ocr
    OCR_AVAILABLE = init_ocr()
except:
    OCR_AVAILABLE = False

def detect_question_markers(page):
    """Detecta marcadores numéricos na página."""
    import re
    words = page.get_text("words") or []
    rect = page.rect
    mid_x = rect.width / 2.0
    
    num_re = re.compile(r"^\{?(\d{1,2})\}?(?:[\.)])?$")
    candidates = []
    
    for w in words:
        x0, y0, x1, y1, txt = w[0], w[1], w[2], w[3], w[4]
        txt = (txt or "").strip()
        if not txt or len(txt) > 4:
            continue
        m = num_re.match(txt)
        if m:
            qnum = int(m.group(1))
            if 1 <= qnum <= 90:
                candidates.append((qnum, x0, y0, x1, y1))
    
    return candidates

def build_bbox_for_question(doc, qnum, dpi=200):
    """Constrói bbox para uma questão específica."""
    scale = dpi / 72.0
    
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        rect = page.rect
        page_w, page_h = rect.width, rect.height
        mid_x = page_w / 2.0
        
        markers = detect_question_markers(page)
        
        for q, x0, y0, x1, y1 in markers:
            if q == qnum:
                # Encontrou o número da questão
                col = 0 if x0 < mid_x else 1
                col_x0, col_x1 = (0, mid_x) if col == 0 else (mid_x, page_w)
                
                # Encontra onde termina (próxima questão ou fim da página)
                y_end = page_h
                for q2, x2, y2, _, _ in markers:
                    same_col = (x2 < mid_x) == (x0 < mid_x)
                    if same_col and y2 > y0 and y2 < y_end:
                        y_end = y2
                
                # Adiciona padding
                pad = 8
                rect_pt = [max(0, col_x0 - pad), max(0, y0 - pad), 
                          min(page_w, col_x1 + pad), min(page_h, y_end + pad)]
                
                bbox_px = {
                    "x": int(rect_pt[0] * scale),
                    "y": int(rect_pt[1] * scale),
                    "w": max(1, int((rect_pt[2] - rect_pt[0]) * scale)),
                    "h": max(1, int((rect_pt[3] - rect_pt[1]) * scale))
                }
                
                return page_idx + 1, rect_pt, bbox_px
    
    return None, None, None

def extract_text_from_rect(doc, page_num, rect_pt):
    """Extrai texto de uma região do PDF."""
    page = doc[page_num - 1]
    clip = fitz.Rect(*rect_pt)
    text = page.get_text("text", clip=clip)
    return text.strip()

def crop_question_image(year, page_num, bbox, qnum, padding=15):
    """Recorta imagem da questão."""
    # Páginas renderizadas pulam a capa, então page_02.png = página 2 do PDF
    page_path = os.path.join(OUT_DIR, str(year), "pages", f"page_{page_num:02d}.png")
    if not os.path.exists(page_path):
        # Tenta page_num + 1 (ajuste de offset da capa)
        page_path = os.path.join(OUT_DIR, str(year), "pages", f"page_{(page_num+1):02d}.png")
        if not os.path.exists(page_path):
            return None, None
    
    try:
        with Image.open(page_path) as img:
            img_w, img_h = img.size
            x = max(0, bbox['x'] - padding)
            y = max(0, bbox['y'] - padding)
            w = min(img_w - x, bbox['w'] + padding * 2)
            h = min(img_h - y, bbox['h'] + padding * 2)
            
            cropped = img.crop((x, y, x + w, y + h))
            
            # Salva
            asset_dir = os.path.join(ASSETS_DIR, str(year), f"q{qnum:02d}")
            os.makedirs(asset_dir, exist_ok=True)
            asset_path = os.path.join(asset_dir, "image.png")
            cropped.save(asset_path, "PNG")
            
            return f"/assets/questions/{year}/q{qnum:02d}/image.png", cropped
    except Exception as e:
        print(f"[ERRO] Falha ao recortar Q{qnum}: {e}")
        return None, None

def complete_missing_questions(year):
    """Completa questões faltantes para um ano."""
    json_path = os.path.join(DATA_DIR, f"fuvest-{year}.json")
    pdf_path = os.path.join(PROVAS_DIR, f"p{str(year)[-2:]}.pdf")
    gabarito_path = os.path.join(PROVAS_DIR, f"g{str(year)[-2:]}.pdf")
    
    if not os.path.exists(json_path):
        print(f"[ERRO] JSON não encontrado: {json_path}")
        return
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    questions = data.get("questions", [])
    existing_nums = set(q.get("number", 0) for q in questions)
    missing_nums = [n for n in range(1, 91) if n not in existing_nums]
    
    if not missing_nums:
        print(f"[OK] {year}: Todas as 90 questões já existem!")
        return
    
    print(f"[INFO] {year}: Faltam {len(missing_nums)} questões: {missing_nums}")
    
    # Carrega gabarito
    gabarito = {}
    try:
        gab_doc = fitz.open(gabarito_path)
        gab_text = "\n".join(p.get_text() for p in gab_doc)
        gab_doc.close()
        import re
        for m in re.findall(r'(\d{1,2})\s*[-–—]\s*([A-E])', gab_text):
            gabarito[int(m[0])] = m[1]
    except Exception as e:
        print(f"[WARN] Erro ao ler gabarito: {e}")
    
    doc = fitz.open(pdf_path)
    added = 0
    
    for qnum in missing_nums:
        page_num, rect_pt, bbox = build_bbox_for_question(doc, qnum)
        
        if not page_num:
            print(f"  [WARN] Q{qnum}: Não encontrada no PDF")
            continue
        
        print(f"  [*] Q{qnum}: página {page_num}...", end="", flush=True)
        
        # Extrai texto do PDF
        text = extract_text_from_rect(doc, page_num, rect_pt)
        
        # Recorta imagem
        asset_path, cropped_img = crop_question_image(year, page_num, bbox, qnum)
        
        # Se texto ruim, tenta OCR
        stem = text
        options = [{"key": k, "text": "(Veja a imagem da questão)"} for k in "ABCDE"]
        
        if OCR_AVAILABLE and cropped_img:
            ocr_text = ocr_image(cropped_img, lang="por")
            if ocr_text and len(ocr_text) > len(text):
                stem = extract_stem_from_ocr(ocr_text) or stem
                parsed_opts = parse_alternatives_from_ocr(ocr_text)
                if parsed_opts:
                    options = [{"key": k, "text": parsed_opts.get(k, "(Veja a imagem da questão)")} for k in "ABCDE"]
        
        # Limpa stem
        import re
        stem = re.sub(r'^\s*\d{1,2}\s*[.\)]\s*', '', stem).strip()
        if not stem or len(stem) < 10:
            stem = "(Veja a imagem da questão)"
        
        # Gabarito
        correct = gabarito.get(qnum, "A")
        
        # Monta questão
        question = {
            "id": f"fuvest-{year}-q{qnum:02d}",
            "year": year,
            "number": qnum,
            "page": page_num,
            "bbox": bbox,
            "stem": stem[:2000],
            "options": options,
            "answer": {"correct": correct},
            "explanation": {
                "theory": "Pendente",
                "steps": [],
                "distractors": {"A": "", "B": "", "C": "", "D": "", "E": ""},
                "finalSummary": ""
            },
            "assets": {"questionImage": asset_path}
        }
        
        questions.append(question)
        added += 1
        print(" OK")
    
    doc.close()
    
    # Reordena por número
    questions.sort(key=lambda q: q.get("number", 0))
    data["questions"] = questions
    
    # Salva
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n[DONE] {year}: {added} questões adicionadas. Total: {len(questions)}/90")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()
    
    complete_missing_questions(args.year)

if __name__ == "__main__":
    main()
