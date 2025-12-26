"""
Corrige questões 6-17 de 2015 que foram extraídas da capa ao invés das páginas corretas.
Remove as questões ruins e re-extrai das páginas corretas do PDF.
"""
import os
import sys
import json
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

def detect_question_markers(page, skip_if_page_one=False):
    """Detecta marcadores numéricos na página, pulando página 1 (capa)."""
    import re
    words = page.get_text("words") or []
    rect = page.rect
    mid_x = rect.width / 2.0
    
    # Ignora página com "INSTRUÇÕES" ou "CADERNO" no topo (provavelmente capa)
    page_text_upper = page.get_text("text")[:500].upper()
    if skip_if_page_one and ("INSTRUÇÕES" in page_text_upper or "CADERNO DE PROVA" in page_text_upper):
        return []
    
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

def build_bbox_for_question_skip_capa(doc, qnum, dpi=200, start_page=2):
    """Constrói bbox ignorando a página 1 (capa)."""
    scale = dpi / 72.0
    
    # Começa da página 2 (índice 1) para ignorar a capa
    for page_idx in range(start_page - 1, len(doc)):
        page = doc[page_idx]
        rect = page.rect
        page_w, page_h = rect.width, rect.height
        mid_x = page_w / 2.0
        
        markers = detect_question_markers(page, skip_if_page_one=True)
        
        for q, x0, y0, x1, y1 in markers:
            if q == qnum:
                col = 0 if x0 < mid_x else 1
                col_x0, col_x1 = (0, mid_x) if col == 0 else (mid_x, page_w)
                
                y_end = page_h
                for q2, x2, y2, _, _ in markers:
                    same_col = (x2 < mid_x) == (x0 < mid_x)
                    if same_col and y2 > y0 and y2 < y_end:
                        y_end = y2
                
                pad = 8
                rect_pt = [max(0, col_x0 - pad), max(0, y0 - pad), 
                          min(page_w, col_x1 + pad), min(page_h, y_end + pad)]
                
                bbox_px = {
                    "x": int(rect_pt[0] * scale),
                    "y": int(rect_pt[1] * scale),
                    "w": max(1, int((rect_pt[2] - rect_pt[0]) * scale)),
                    "h": max(1, int((rect_pt[3] - rect_pt[1]) * scale))
                }
                
                # Retorna página real do PDF (1-indexed)
                return page_idx + 1, rect_pt, bbox_px
    
    return None, None, None

def extract_text_from_rect(doc, page_num, rect_pt):
    """Extrai texto de uma região."""
    page = doc[page_num - 1]
    clip = fitz.Rect(*rect_pt)
    text = page.get_text("text", clip=clip)
    return text.strip()

def crop_question_image_from_pdf(doc, year, page_num, bbox, qnum, dpi=200, padding=15):
    """Recorta imagem diretamente do PDF."""
    page = doc[page_num - 1]
    
    # Converte bbox de pixels para pontos
    scale = dpi / 72.0
    x_pt = bbox['x'] / scale
    y_pt = bbox['y'] / scale
    w_pt = bbox['w'] / scale
    h_pt = bbox['h'] / scale
    
    # Adiciona padding
    pad_pt = padding / scale
    clip = fitz.Rect(x_pt - pad_pt, y_pt - pad_pt, x_pt + w_pt + pad_pt, y_pt + h_pt + pad_pt)
    
    # Renderiza região
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Salva
    asset_dir = os.path.join(ASSETS_DIR, str(year), f"q{qnum:02d}")
    os.makedirs(asset_dir, exist_ok=True)
    asset_path = os.path.join(asset_dir, "image.png")
    img.save(asset_path, "PNG")
    
    return f"/assets/questions/{year}/q{qnum:02d}/image.png"

def fix_2015():
    """Corrige as questões 6-17 de 2015."""
    year = 2015
    json_path = os.path.join(DATA_DIR, f"fuvest-{year}.json")
    pdf_path = os.path.join(PROVAS_DIR, "p15.pdf")
    gabarito_path = os.path.join(PROVAS_DIR, "g15.pdf")
    
    print(f"[*] Carregando JSON de {year}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    questions = data.get("questions", [])
    
    # Questões que precisam ser corrigidas (estavam pegando da capa)
    bad_questions = [6, 7, 8, 9, 14, 15, 16, 17]
    
    # Remove as questões ruins
    questions = [q for q in questions if q.get("number") not in bad_questions]
    print(f"[OK] Removidas {len(bad_questions)} questões ruins. Restam {len(questions)}.")
    
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
    
    # Reprocessa as questões faltantes
    doc = fitz.open(pdf_path)
    
    for qnum in bad_questions:
        print(f"  [*] Reprocessando Q{qnum}...", end="", flush=True)
        
        # Busca a questão ignorando a capa (página 1)
        page_num, rect_pt, bbox = build_bbox_for_question_skip_capa(doc, qnum, dpi=200, start_page=2)
        
        if not page_num:
            print(f" NÃO ENCONTRADA no PDF!")
            continue
        
        print(f" página {page_num}...", end="", flush=True)
        
        # Extrai texto
        stem = extract_text_from_rect(doc, page_num, rect_pt)
        
        # Recorta imagem
        asset_path = crop_question_image_from_pdf(doc, year, page_num, bbox, qnum)
        
        # Limpa stem
        import re
        stem = re.sub(r'^\s*\d{1,2}\s*[.\)]\s*', '', stem).strip()
        if not stem or len(stem) < 20 or "DURANTE A PROVA" in stem.upper():
            stem = "(Veja a imagem da questão)"
        
        # Gabarito
        correct = gabarito.get(qnum, "A")
        
        # Cria questão
        question = {
            "id": f"fuvest-{year}-q{qnum:02d}",
            "year": year,
            "number": qnum,
            "page": page_num,
            "bbox": bbox,
            "stem": stem[:2000],
            "options": [{"key": k, "text": "(Veja a imagem da questão)"} for k in "ABCDE"],
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
        print(" OK")
    
    doc.close()
    
    # Reordena por número
    questions.sort(key=lambda q: q.get("number", 0))
    data["questions"] = questions
    
    # Salva
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n[DONE] {year} corrigido. Total: {len(questions)}/90")

if __name__ == "__main__":
    fix_2015()
