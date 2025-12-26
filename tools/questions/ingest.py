import os
import sys
import fitz  # PyMuPDF
from PIL import Image
import argparse
import json
import hashlib
from datetime import datetime
import re
from dotenv import load_dotenv
try:
    import google.generativeai as genai
except Exception:
    genai = None

# OCR local (sem Google) para fallback quando PDF vier com encoding ruim
try:
    from ocr import ocr_image, parse_alternatives_from_ocr, extract_stem_from_ocr, OCR_READY
except Exception:
    OCR_READY = False
    ocr_image = None
    parse_alternatives_from_ocr = None
    extract_stem_from_ocr = None

# --- Configuração de Codificação ---
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- Constantes e Configurações ---
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env')) 

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "tools", "questions", "out")
CACHE_DIR = os.path.join(PROJECT_ROOT, "tools", "questions", "cache")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "public", "assets", "questions")
DATA_DIR = os.path.join(PROJECT_ROOT, "public", "data", "questions")
PROVAS_DIR = os.path.join(PROJECT_ROOT, "provas")

gemini_vision_model = None

gemini_text_model = None


def get_gemini_vision_model():
    global gemini_vision_model
    if genai is None:
        raise RuntimeError("google.generativeai não está instalado. (Gemini desabilitado)")
    if gemini_vision_model is not None:
        return gemini_vision_model

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY or GEMINI_API_KEY == "SUA_CHAVE_AQUI":
        raise ValueError("A variável de ambiente GEMINI_API_KEY não foi definida.")

    genai.configure(api_key=GEMINI_API_KEY)

    preferred = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]

    models = [m for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    model_id = None
    for pref in preferred:
        for m in models:
            name = (m.name or "")
            if pref in name and "image-generation" not in name and "lite" not in name:
                model_id = name
                break
        if model_id:
            break

    if not model_id:
        raise RuntimeError("Modelo Gemini (vision) compatível não encontrado.")

    print(f"[OK] Usando modelo (vision): {model_id}")
    gemini_vision_model = genai.GenerativeModel(model_id)
    return gemini_vision_model


def _is_garbled_text(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    # Menos restritivo para PDFs com encoding especial
    letters = sum(ch.isalpha() for ch in t)
    ratio = letters / max(1, len(t))
    weird = sum(ch in "'&$%{}[]\\" for ch in t)
    # Aumenta tolerância para aceitar mais textos
    if (len(t) > 100 and ratio < 0.15) or weird > 20:
        return True
    return False


def _normalize_spaces(s: str) -> str:
    s = (s or "").replace("\u00a0", " ").replace("¬", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _looks_like_non_textual_option(text: str) -> bool:
    t = _normalize_spaces(text)
    if not t:
        return True
    if re.fullmatch(r"\(?[A-E]\)?", t):
        return True
    if re.fullmatch(r"\d{1,3}", t):
        return True
    letters = sum(ch.isalpha() for ch in t)
    ratio = letters / max(1, len(t))
    sym = sum(ch in "=<>∪∩±×÷*/^_" for ch in t)
    if (len(t) > 12 and ratio < 0.35) or sym >= 3:
        return True
    if "note e adote" in t.lower():
        return True
    return False


def _sanitize_option_text(text: str) -> str:
    t = _normalize_spaces(text)
    for marker in ["TEXTO PARA AS QUEST", "TEXTO PARA AS QUESTÕES", "NOTE E ADOTE"]:
        idx = t.upper().find(marker)
        if idx >= 0:
            t = t[:idx].strip()
            break
    if _looks_like_non_textual_option(t):
        return "(Veja a imagem da questão)"
    t = re.sub(r"\s+\d{1,2}$", "", t).strip()
    if not t:
        return "(Veja a imagem da questão)"
    return t


def _parse_question_targets_from_text(text: str):
    t = _normalize_spaces(text).upper()
    nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", t)]
    if not nums:
        return []
    m = re.search(r"\bDE\s+(\d{1,2})\s+A\s+(\d{1,2})\b", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if 1 <= a <= 90 and 1 <= b <= 90 and a <= b:
            return list(range(a, b + 1))
    nums = [n for n in nums if 1 <= n <= 90]
    seen = set()
    out = []
    for n in nums:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _extract_reference_blocks(doc: fitz.Document, dpi: int = 200):
    scale = dpi / 72.0
    by_qnum = {}
    by_label = {}
    for i in range(len(doc)):
        page = doc.load_page(i)
        rect = page.rect
        page_w = rect.width
        page_h = rect.height
        mid_x = page_w / 2.0
        markers = _detect_question_markers_from_pdf_page(page)
        col_markers = []
        for qnum, bbox in markers:
            x0, y0, *_ = bbox
            col = 0 if x0 < mid_x else 1
            col_markers.append((col, qnum, y0))
        blocks = page.get_text("blocks") or []
        for b in blocks:
            x0, y0, x1, y1, txt = b[0], b[1], b[2], b[3], b[4]
            if not txt:
                continue
            t = _normalize_spaces(txt)
            t_up = t.upper()
            if "TEXTO PARA AS QUEST" in t_up:
                targets = _parse_question_targets_from_text(t_up)
                if not targets:
                    continue
                col = 0 if x0 < mid_x else 1
                col_x0, col_x1 = (0, mid_x) if col == 0 else (mid_x, page_w)
                y_end = page_h
                for c, qn, my0 in col_markers:
                    if c == col and my0 > y0 and my0 < y_end:
                        y_end = my0
                rect_pt = [col_x0, y0, col_x1, y_end]
                bbox_px = {
                    "x": int(rect_pt[0] * scale),
                    "y": int(rect_pt[1] * scale),
                    "w": max(1, int((rect_pt[2] - rect_pt[0]) * scale)),
                    "h": max(1, int((rect_pt[3] - rect_pt[1]) * scale)),
                }
                text_full = _normalize_spaces(page.get_text("text", clip=fitz.Rect(*rect_pt)))
                title = _normalize_spaces(t.split("\n")[0])
                ref_obj = {
                    "page": i + 1,
                    "rect_pt": rect_pt,
                    "bbox_px": bbox_px,
                    "title": title,
                    "text": text_full,
                }
                for qn in targets:
                    by_qnum.setdefault(qn, []).append(ref_obj)
                continue
            m = re.search(r"\bTEXTO\s+([IVX]{1,5})\b", t_up)
            if m and "TEXTO PARA" not in t_up:
                label = m.group(1)
                col = 0 if x0 < mid_x else 1
                col_x0, col_x1 = (0, mid_x) if col == 0 else (mid_x, page_w)
                y_end = page_h
                for c, qn, my0 in col_markers:
                    if c == col and my0 > y0 and my0 < y_end:
                        y_end = my0
                rect_pt = [col_x0, y0, col_x1, y_end]
                bbox_px = {
                    "x": int(rect_pt[0] * scale),
                    "y": int(rect_pt[1] * scale),
                    "w": max(1, int((rect_pt[2] - rect_pt[0]) * scale)),
                    "h": max(1, int((rect_pt[3] - rect_pt[1]) * scale)),
                }
                text_full = _normalize_spaces(page.get_text("text", clip=fitz.Rect(*rect_pt)))
                by_label[label] = {
                    "page": i + 1,
                    "rect_pt": rect_pt,
                    "bbox_px": bbox_px,
                    "title": f"TEXTO {label}",
                    "text": text_full,
                }
    return by_qnum, by_label


def extract_questions_from_page_image(image_path: str, year: int):
    with open(image_path, "rb") as f:
        img_bytes = f.read()
    cache_key = hashlib.sha256(img_bytes).hexdigest()
    cache_dir = os.path.join(CACHE_DIR, str(year), "vision_pages")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{cache_key}.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    model = get_gemini_vision_model()
    image = Image.open(image_path)
    prompt = """Você vai ler uma página de prova da Fuvest (múltipla escolha) e extrair as questões.
Regras obrigatórias:
1) A página pode ter duas colunas. Respeite a ordem: coluna esquerda de cima para baixo, depois coluna direita.
2) Ignore cabeçalho, rodapés, paginação, logos e textos fora das questões.
3) Para CADA questão, retorne:
   - number (1..90)
   - bbox em PIXELS: x,y,w,h (recorte deve conter enunciado + alternativas + figuras da questão)
   - stem (enunciado) em texto (pode incluir quebras de linha)
   - options: A..E com text. Se uma alternativa for só imagem/símbolo, escreva "(Veja a imagem da questão)".
4) Retorne SOMENTE JSON estrito e válido.
Schema:
{
  "page": number,
  "questions": [
    {
      "number": number,
      "stem": string,
      "options": [{"key":"A","text":string}, {"key":"B","text":string}, {"key":"C","text":string}, {"key":"D","text":string}, {"key":"E","text":string}],
      "bbox": {"x": number, "y": number, "w": number, "h": number}
    }
  ]
}
"""
    try:
        resp = model.generate_content(
            [prompt, image],
            generation_config={"response_mime_type": "application/json"},
        )
        data = json.loads(resp.text)
        qs = data.get("questions") or []
        for q in qs:
            q["stem"] = _normalize_spaces(q.get("stem", ""))
            opts = q.get("options") or []
            for o in opts:
                o["text"] = _normalize_spaces(o.get("text", ""))
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data
    except Exception as e:
        print(f"\n[WARN] Vision extraction falhou: {e}", flush=True)
        return {"page": None, "questions": []}


def _auto_trim_whitespace(img: Image.Image, pad: int = 10):
    try:
        gray = img.convert("L")
        bw = gray.point(lambda p: 255 if p < 245 else 0)
        bbox = bw.getbbox()
        if not bbox:
            return img
        x0, y0, x1, y1 = bbox
        x0 = max(0, x0 - pad)
        y0 = max(0, y0 - pad)
        x1 = min(img.width, x1 + pad)
        y1 = min(img.height, y1 + pad)
        if x1 <= x0 or y1 <= y0:
            return img
        return img.crop((x0, y0, x1, y1))
    except Exception:
        return img


def get_gemini_text_model():
    global gemini_text_model
    if genai is None:
        raise RuntimeError("google.generativeai não está instalado. (Gemini desabilitado)")
    if gemini_text_model is not None:
        return gemini_text_model
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY or GEMINI_API_KEY == "SUA_CHAVE_AQUI":
        raise ValueError("A variável de ambiente GEMINI_API_KEY não foi definida.")
    genai.configure(api_key=GEMINI_API_KEY)
    model_id = None
    found = False
    for m in genai.list_models():
        if 'generateContent' not in m.supported_generation_methods:
            continue
        if "gemini-2.0-flash" in m.name and "lite" not in m.name:
            model_id = m.name
            found = True
            break
    if not found:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and "gemini-1.5-flash" in m.name:
                model_id = m.name
                found = True
                break
    if not model_id:
        raise RuntimeError("Modelo Gemini (texto) compatível não encontrado.")
    print(f"[OK] Usando modelo para OCR/gabarito: {model_id}")
    gemini_text_model = genai.GenerativeModel(model_id)
    return gemini_text_model


def render_pdf_to_images(pdf_path, year, dpi=200, skip_first_page=True):
    image_paths = []
    year_output_dir = os.path.join(OUTPUT_DIR, str(year), "pages")
    os.makedirs(year_output_dir, exist_ok=True)
    print(f"[*] Renderizando paginas de {os.path.basename(pdf_path)}...", flush=True)
    try:
        doc = fitz.open(pdf_path)
        start_page = 1 if skip_first_page else 0
        print(f"[INFO] Pulando primeira página (capa/instruções)." if skip_first_page else "", flush=True)
        for page_num in range(start_page, len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=dpi)
            output_path = os.path.join(year_output_dir, f"page_{page_num + 1:02d}.png")
            pix.save(output_path)
            image_paths.append(output_path)
        print(f"[OK] {len(doc) - start_page} paginas convertidas.", flush=True)
        doc.close()
        return image_paths
    except Exception as e:
        print(f"[ERRO] Falha ao processar PDF: {e}", flush=True)
        return []


def _is_cover_or_instructions_page(page: fitz.Page) -> bool:
    """Heurística simples pra evitar tratar capa/instruções como questões.

    IMPORTANTE: vários anos têm cabeçalho com "FUVEST"/"PROVA" em TODAS as páginas.
    Então esta heurística só deve valer para as primeiras páginas.
    """
    try:
        # Só consideramos capa/instruções nas 2 primeiras páginas.
        # Depois disso, o risco de falso-positivo (por cabeçalho repetido) é alto.
        if getattr(page, "number", 999) > 1:
            return False
        t = _normalize_spaces(page.get_text("text") or "").upper()
        if not t:
            return False
        # Heurística mais precisa:
        # - "FUVEST" e "PROVA" aparecem em cabeçalhos de páginas normais, então NÃO usamos.
        # - se tiver INSTRUÇÕES / "SÓ ABRA" / "FISCAL" etc, então é capa.
        strong = [
            "INSTRU",
            "SÓ ABRA",
            "SO ABRA",
            "FISCAL",
            "FOLHA ÓPTICA",
            "FOLHA OPTICA",
            "CANETA",
        ]
        return any(k in t for k in strong)
    except Exception:
        return False


def _detect_question_markers_from_pdf_page(page: fitz.Page):
    words = page.get_text("words") or []
    if not words:
        return []

    # Evita falsos positivos em capa/instruções
    if _is_cover_or_instructions_page(page):
        return []
    rect = page.rect
    page_w = rect.width
    mid_x = page_w / 2.0
    margin_pt = 520
    # Permite 01, 02 etc (alguns PDFs usam 2 dígitos para as primeiras questões)
    num_re = re.compile(r"^\{?0*(\d{1,2})\}?(?:[\.)])?$")
    lines = {}
    for w in words:
        x0, y0, x1, y1, txt, block_no, line_no = w[0], w[1], w[2], w[3], w[4], w[5], w[6]
        txt = (txt or "").strip()
        if not txt:
            continue
        key = (block_no, line_no)
        lines.setdefault(key, []).append((x0, y0, x1, y1, txt))
    candidates = []
    for items in lines.values():
        items_sorted = sorted(items, key=lambda t: t[0])
        tokens = [t[4] for t in items_sorted]
        joined = "".join(tokens)
        joined = re.sub(r"\s+", "", joined)
        joined = re.sub(r"[\x00-\x1f]", "", joined)
        # Remove caracteres invisíveis comuns em PDFs antigos
        joined = joined.replace("\u00ad", "")
        if len(joined) > 8:
            continue
        m = num_re.match(joined)
        if not m:
            continue
        qnum = int(m.group(1))
        x0 = min(t[0] for t in items_sorted)
        y0 = min(t[1] for t in items_sorted)
        x1 = max(t[2] for t in items_sorted)
        y1 = max(t[3] for t in items_sorted)
        if x0 < mid_x:
            if x0 > margin_pt:
                continue
        else:
            if x0 > (mid_x + margin_pt):
                continue
        candidates.append((qnum, (x0, y0, x1, y1)))
    markers = candidates
    best = {}
    for qnum, bbox in markers:
        if qnum not in best or bbox[1] < best[qnum][1]:
            best[qnum] = bbox
    return [(qnum, best[qnum]) for qnum in sorted(best.keys())]


def build_question_bboxes_from_pdf(pdf_path: str, dpi: int = 200):
    doc = fitz.open(pdf_path)
    scale = dpi / 72.0
    page_map = {}
    for i in range(len(doc)):
        page = doc.load_page(i)
        rect = page.rect
        page_w = rect.width
        page_h = rect.height
        mid_x = page_w / 2.0
        markers = _detect_question_markers_from_pdf_page(page)
        if not markers:
            continue
        left = []
        right = []
        for qnum, bbox in markers:
            x0, y0, x1, y1 = bbox
            if x0 < mid_x:
                left.append((qnum, y0))
            else:
                right.append((qnum, y0))
        left.sort(key=lambda t: t[1])
        right.sort(key=lambda t: t[1])
        def build_column_bboxes(col_items, col_x0, col_x1):
            out = {}
            for idx, (qnum, y0) in enumerate(col_items):
                y1 = col_items[idx + 1][1] if idx + 1 < len(col_items) else page_h
                pad_pt = 6
                x0p = max(0, col_x0 - pad_pt)
                x1p = min(page_w, col_x1 + pad_pt)
                y0p = max(0, y0 - pad_pt)
                y1p = min(page_h, y1 + pad_pt)
                px0 = int(x0p * scale)
                py0 = int(y0p * scale)
                px1 = int(x1p * scale)
                py1 = int(y1p * scale)
                out[qnum] = {
                    "x": px0,
                    "y": py0,
                    "w": max(1, px1 - px0),
                    "h": max(1, py1 - py0),
                }
            return out
        page_bboxes = {}
        page_bboxes.update(build_column_bboxes(left, 0, mid_x))
        page_bboxes.update(build_column_bboxes(right, mid_x, page_w))
        if page_bboxes:
            page_map[i + 1] = page_bboxes
    doc.close()
    return page_map


def build_question_rect_index(pdf_path: str, dpi: int = 200, min_q=1, max_q=90):
    doc = fitz.open(pdf_path)
    scale = dpi / 72.0
    idx = {}
    for i in range(len(doc)):
        page = doc.load_page(i)
        rect = page.rect
        page_w = rect.width
        page_h = rect.height
        mid_x = page_w / 2.0
        markers = _detect_question_markers_from_pdf_page(page)
        if not markers:
            continue
        left = []
        right = []
        for qnum, bbox in markers:
            if qnum < min_q or qnum > max_q:
                continue
            x0, y0, x1, y1 = bbox
            if x0 < mid_x:
                left.append((qnum, y0))
            else:
                right.append((qnum, y0))
        left.sort(key=lambda t: t[1])
        right.sort(key=lambda t: t[1])
        def build_col(col_items, col_x0, col_x1):
            out = []
            for idx2, (qnum, y0) in enumerate(col_items):
                y1 = col_items[idx2 + 1][1] if idx2 + 1 < len(col_items) else page_h
                pad_pt = 8
                x0p = max(0, col_x0 - pad_pt)
                x1p = min(page_w, col_x1 + pad_pt)
                y0p = max(0, y0 - pad_pt)
                y1p = min(page_h, y1 + pad_pt)
                rect_pt = [x0p, y0p, x1p, y1p]
                px0 = int(x0p * scale)
                py0 = int(y0p * scale)
                px1 = int(x1p * scale)
                py1 = int(y1p * scale)
                bbox_px = {"x": px0, "y": py0, "w": max(1, px1 - px0), "h": max(1, py1 - py0)}
                out.append((qnum, rect_pt, bbox_px))
            return out
        for qnum, rect_pt, bbox_px in build_col(left, 0, mid_x) + build_col(right, mid_x, page_w):
            if qnum not in idx:
                idx[qnum] = {"page": i + 1, "rect": rect_pt, "bbox": bbox_px}
    doc.close()
    return idx


def extract_question_text_from_pdf(doc: fitz.Document, page_num: int, rect_pt):
    page = doc.load_page(page_num - 1)
    clip = fitz.Rect(*rect_pt)
    words = page.get_text("words", clip=clip) or []
    if not words:
        return None, None
    words.sort(key=lambda w: (w[1], w[0]))
    line_groups = []
    y_tol = 2.0
    for w in words:
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        text = (text or "").replace("\u00a0", " ").strip()
        if not text:
            continue
        if not line_groups or abs(y0 - line_groups[-1]["y"]) > y_tol:
            line_groups.append({"y": y0, "x0": x0, "tokens": [(x0, text)]})
        else:
            line_groups[-1]["x0"] = min(line_groups[-1]["x0"], x0)
            line_groups[-1]["tokens"].append((x0, text))
    lines = []
    for lg in line_groups:
        toks = [t[1] for t in sorted(lg["tokens"], key=lambda t: t[0])]
        line_text = " ".join(toks).strip()
        if line_text:
            lines.append((lg["x0"], line_text))
    if not lines:
        return None, None
    if re.match(r"^\d{1,2}[\.)]?$", lines[0][1]):
        lines = lines[1:]
    if not lines:
        return None, None
    base_x0 = min(x for (x, _) in lines)
    opt_x_max = base_x0 + 60
    cont_x_max = base_x0 + 85
    opt_head_re = re.compile(r"^\(?([A-E])\)?\s*$")
    opt_inline_re = re.compile(r"^\(?([A-E])\)?\s*[\).\-–:]\s*(.*)$")
    opt_lines = []
    for i, (x0, txt) in enumerate(lines):
        if x0 > opt_x_max:
            continue
        m = opt_inline_re.match(txt)
        if m:
            opt_lines.append((i, m.group(1), (m.group(2) or "").strip()))
            continue
        m2 = opt_head_re.match(txt)
        if m2:
            opt_lines.append((i, m2.group(1), ""))
    if not opt_lines:
        stem = " ".join([t for (_, t) in lines]).strip()
        if len(stem) < 20:
            return None, None
        options = [{"key": k, "text": "(Veja a imagem da questão)"} for k in ["A", "B", "C", "D", "E"]]
        stem = re.sub(r"\s+", " ", stem.replace("\u00a0", " ").replace("¬", " ")).strip()
        stem = re.sub(r"^\{?\d+\}?\s*", "", stem)
        return stem, options
    first_opt = opt_lines[0][0]
    stem = " ".join([t for (_, t) in lines[:first_opt]]).strip()
    if len(stem) < 20:
        return None, None
    options_by_key = {}
    for idx, (line_i, key, inline_text) in enumerate(opt_lines):
        end = opt_lines[idx + 1][0] if idx + 1 < len(opt_lines) else len(lines)
        chunk = []
        if inline_text:
            chunk.append(inline_text)
        for j in range(line_i + 1, end):
            if lines[j][0] <= cont_x_max:
                chunk.append(lines[j][1])
        text = " ".join([c for c in chunk if c]).strip()
        options_by_key[key] = _sanitize_option_text(text)
    for k in ["A", "B", "C", "D", "E"]:
        if not options_by_key.get(k):
            options_by_key[k] = "(Veja a imagem da questão)"
    options = [{"key": k, "text": options_by_key.get(k, "")} for k in ["A", "B", "C", "D", "E"]]
    stem = re.sub(r"\s+", " ", stem.replace("\u00a0", " ").replace("¬", " ")).strip()
    stem = re.sub(r"^\{?\d+\}?\s*", "", stem)
    for opt in options:
        opt["text"] = _sanitize_option_text(opt.get("text", ""))
    return stem, options


def crop_assets(questions, year, page_image_paths, bbox_index=None, padding=15):
    print("\n[CLIP] Recortando assets das questoes...", flush=True)
    for question in questions:
        q_num = question.get("number")
        if bbox_index and q_num in bbox_index:
            question["page"] = bbox_index[q_num]["page"]
            bbox = bbox_index[q_num]["bbox"]
        else:
            bbox = question.get("bbox")
        # IMPORTANTÍSSIMO: page_images pode estar "pulando" páginas dependendo do render.
        # Para evitar offset, sempre indexamos pela posição real na lista.
        # O render gera arquivos nomeados pelo page_num + 1 do PDF.
        page_idx = int(question.get("page", 0)) - 1
        if not all([q_num, bbox, page_idx >= 0]):
            question['asset_path'] = "/assets/questions/holder.png"
            continue
        try:
            with Image.open(page_image_paths[page_idx]) as img:
                img_w, img_h = img.size
                x = max(0, bbox['x'] - padding)
                y = max(0, bbox['y'] - padding)
                w = min(img_w - x, bbox['w'] + (padding * 2))
                h = min(img_h - y, bbox['h'] + (padding * 2))
                cropped_img = img.crop((x, y, x + w, y + h))
                cropped_img = _auto_trim_whitespace(cropped_img, pad=12)
                asset_dir = os.path.join(ASSETS_DIR, str(year), f"q{q_num:02d}")
                os.makedirs(asset_dir, exist_ok=True)
                asset_path = os.path.join(asset_dir, "image.png")
                cropped_img.save(asset_path, "PNG")
                question['asset_path'] = f"/assets/questions/{year}/q{q_num:02d}/image.png"
        except Exception as e:
            print(f"[ERRO] Falha no recorte da Q{q_num}: {e}", flush=True)
            question['asset_path'] = "/assets/questions/holder.png"
    return questions


def _dedupe_refs(refs):
    seen = set()
    out = []
    for r in refs or []:
        key = (
            str(r.get("title") or ""),
            int(r.get("page") or 0),
            tuple(r.get("rect_pt") or []),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _crop_reference_image(page_image_paths, ref_obj, padding_px=14):
    page_idx = int(ref_obj.get("page", 0)) - 1
    bbox = ref_obj.get("bbox_px") or {}
    if page_idx < 0 or page_idx >= len(page_image_paths):
        return None
    if not all(k in bbox for k in ["x", "y", "w", "h"]):
        return None
    try:
        with Image.open(page_image_paths[page_idx]) as img:
            img_w, img_h = img.size
            x = max(0, int(bbox["x"]) - padding_px)
            y = max(0, int(bbox["y"]) - padding_px)
            w = min(img_w - x, int(bbox["w"]) + (padding_px * 2))
            h = min(img_h - y, int(bbox["h"]) + (padding_px * 2))
            cropped = img.crop((x, y, x + w, y + h))
            return _auto_trim_whitespace(cropped, pad=12)
    except Exception:
        return None


def _combine_images_vertical(images, gap=16, bg=(255, 255, 255)):
    imgs = [im for im in (images or []) if im is not None]
    if not imgs:
        return None
    w = max(im.width for im in imgs)
    h = sum(im.height for im in imgs) + gap * (len(imgs) - 1)
    canvas = Image.new("RGB", (w, h), bg)
    y = 0
    for im in imgs:
        x = (w - im.width) // 2
        canvas.paste(im, (x, y))
        y += im.height + gap
    return canvas


def _apply_refs_to_stem(stem: str, refs):
    refs = _dedupe_refs(refs)
    if not refs:
        return stem
    blocks = []
    for r in refs:
        title = _normalize_spaces(r.get("title") or "").strip()
        text = _normalize_spaces(r.get("text") or "").strip()
        if not text:
            continue
        if title:
            blocks.append(f"{title}\n{text}")
        else:
            blocks.append(text)
    if not blocks:
        return stem
    prefix = "\n\n".join(blocks)
    return f"{prefix}\n\n{stem}" if stem else prefix


def apply_reference_assets(questions, year, page_image_paths):
    for q in questions:
        refs = q.get("_references") or []
        refs = _dedupe_refs(refs)
        if not refs:
            continue
        asset_url = q.get("asset_path") or q.get("assets", {}).get("questionImage")
        if not asset_url:
            continue
        local_path = os.path.join(PROJECT_ROOT, "public", asset_url.lstrip("/"))
        if not os.path.exists(local_path):
            continue
        try:
            with Image.open(local_path) as base_img:
                base_img = base_img.convert("RGB")
                ref_imgs = []
                for r in refs:
                    ri = _crop_reference_image(page_image_paths, r)
                    if ri is not None:
                        ref_imgs.append(ri.convert("RGB"))
                if not ref_imgs:
                    continue
                composed = _combine_images_vertical([*ref_imgs, base_img], gap=18)
                if composed is None:
                    continue
                composed = _auto_trim_whitespace(composed, pad=10)
                composed.save(local_path, "PNG")
        except Exception as e:
            print(f"[WARN] Falha ao compor imagem com refs (Q{q.get('number')}): {e}", flush=True)
    return questions


def run_vision_pipeline(pdf_path, year, page_images):
    print(f"\n[VISION] Executando pipeline visual para {year}...")
    all_questions = []
    for i, img_path in enumerate(page_images):
        page_num = i + 1
        print(f"[*] Processando pagina {page_num} com Gemini Vision...", flush=True)
        data = extract_questions_from_page_image(img_path, year)
        if not data or not data.get("questions"):
            continue
        for q in data["questions"]:
            q["page"] = page_num
            q.setdefault("options", [])
            q.setdefault("stem", "(Veja a imagem da questão)")
            q["stem"] = _normalize_spaces(q["stem"])
            for opt in q["options"]:
                opt["text"] = _sanitize_option_text(opt.get("text", ""))
            all_questions.append(q)
    print(f"\n[CLIP] Recortando assets baseados na IA...")
    questions_with_assets = crop_assets(all_questions, year, page_images, bbox_index=None)
    return questions_with_assets


def extract_gabarito(gabarito_pdf_path):
    print(f"\n[GAB] Lendo gabarito...", flush=True)
    gabarito = {}
    doc = fitz.open(gabarito_pdf_path)
    text = "\n".join([page.get_text("text") for page in doc])
    doc.close()
    patterns = [
        r'(\d{1,2})\s*[-–—]\s*([ABCDE])',
        r'(\d{1,2})\s*[\)\.]\s*([ABCDE])',
        r'(\d{1,2})\s+([ABCDE])',
    ]
    matches = []
    for pat in patterns:
        matches.extend(re.findall(pat, text))
    for num_str, letter in matches:
        n = int(num_str)
        if 1 <= n <= 90:
            gabarito[n] = letter
    if len(gabarito) < 90 and genai is not None:
        gabarito = extract_gabarito_via_gemini(gabarito_pdf_path)
    if len(gabarito) < 90:
        missing = [i for i in range(1, 91) if i not in gabarito]
        raise RuntimeError(f"Gabarito incompleto ({len(gabarito)}/90). Faltando: {missing[:20]}...")
    return gabarito


def extract_gabarito_via_gemini(gabarito_pdf_path: str):
    os.makedirs(CACHE_DIR, exist_ok=True)
    pdf_bytes = open(gabarito_pdf_path, 'rb').read()
    cache_key = hashlib.sha256(pdf_bytes).hexdigest()
    cache_subdir = os.path.join(CACHE_DIR, "gabarito")
    os.makedirs(cache_subdir, exist_ok=True)
    cache_file = os.path.join(cache_subdir, f"{os.path.basename(gabarito_pdf_path)}_{cache_key}.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            return {int(k): v for k, v in json.load(f).items()}
    print("[GAB] Fallback OCR via Gemini (PDF escaneado)...", flush=True)
    model = get_gemini_text_model()
    doc = fitz.open(gabarito_pdf_path)
    answers = {}
    for i in range(len(doc)):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=220)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        prompt = """Você vai ler um gabarito da Fuvest (questões 1 a 90) a partir de uma imagem.
Regras:
1) Retorne SOMENTE JSON estrito.
2) Formato de saída: {"1":"A","2":"C",...,"90":"E"}.
3) Use letras A/B/C/D/E.
4) Ignore quaisquer textos que não sejam o gabarito.
5) Se algum número estiver ilegível, omita-o (não chute)."""
        resp = model.generate_content(
            [prompt, img],
            generation_config={"response_mime_type": "application/json"}
        )
        page_map = json.loads(resp.text)
        for k, v in page_map.items():
            try:
                n = int(str(k).strip())
            except Exception:
                continue
            if 1 <= n <= 90 and str(v).strip() in ["A", "B", "C", "D", "E"]:
                answers[n] = str(v).strip()
    doc.close()
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump({str(k): v for k, v in sorted(answers.items())}, f, ensure_ascii=False, indent=2)
    return answers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--recrop-only", action="store_true", help="Regera apenas imagens/recortes usando bboxes do PDF e JSON existente (sem IA).")
    args = parser.parse_args()

    pdf_path = os.path.join(PROVAS_DIR, f"p{str(args.year)[-2:]}.pdf")

    if args.recrop_only:
        recrop_only(pdf_path, args.year, dpi=200)
        return

    # Para padronização e evitar offsets: NUNCA pular capa aqui.
    # (as páginas completas são usadas pelo botão "Ver Página" e pelo recorte)
    page_images = render_pdf_to_images(pdf_path, args.year, skip_first_page=False)
    if not page_images: sys.exit(1)

    print("\n[*] Gerando índice determinístico (page/rect/bbox) via PyMuPDF...", flush=True)
    rect_index = build_question_rect_index(pdf_path, dpi=200)
    doc = fitz.open(pdf_path)
    try:
        refs_by_qnum, refs_by_label = _extract_reference_blocks(doc, dpi=200)
    except Exception as e:
        print(f"[WARN] Falha ao extrair blocos de referência: {e}", flush=True)
        refs_by_qnum, refs_by_label = {}, {}

    all_questions = []
    garbled_count = 0
    ocr_used = 0

    for qnum in sorted(rect_index.keys()):
        info = rect_index[qnum]
        stem, options = extract_question_text_from_pdf(doc, info["page"], info["rect"])

        if stem is None or options is None:
            stem = "(Veja a imagem da questão)"
            options = [{"key": k, "text": "(Veja a imagem da questão)"} for k in ["A", "B", "C", "D", "E"]]

        # Se o texto do PDF vier ruim, tenta OCR local na imagem recortada da questão.
        if _is_garbled_text(stem):
            garbled_count += 1
            if OCR_READY and ocr_image and parse_alternatives_from_ocr and extract_stem_from_ocr:
                try:
                    page_idx = int(info["page"]) - 1
                    if 0 <= page_idx < len(page_images):
                        with Image.open(page_images[page_idx]) as img:
                            bbox = info["bbox"]
                            pad = 15
                            x = max(0, bbox['x'] - pad)
                            y = max(0, bbox['y'] - pad)
                            w = min(img.width - x, bbox['w'] + (pad * 2))
                            h = min(img.height - y, bbox['h'] + (pad * 2))
                            cropped = img.crop((x, y, x + w, y + h))
                            cropped = _auto_trim_whitespace(cropped, pad=12)
                            ocr_txt = ocr_image(cropped, lang="por")
                            if ocr_txt:
                                o_stem = extract_stem_from_ocr(ocr_txt)
                                o_opts = parse_alternatives_from_ocr(ocr_txt)
                                if o_stem and len(o_stem) >= 20:
                                    stem = _normalize_spaces(o_stem)
                                if o_opts:
                                    options = [{"key": k, "text": _sanitize_option_text(o_opts.get(k, ""))} for k in ["A","B","C","D","E"]]
                                ocr_used += 1
                except Exception as e:
                    print(f"[OCR] Falha OCR local Q{qnum}: {e}", flush=True)

            # Se ainda estiver ruim, usa placeholder
            if _is_garbled_text(stem):
                stem = "(Veja a imagem da questão)"
                options = [{"key": k, "text": "(Veja a imagem da questão)"} for k in ["A", "B", "C", "D", "E"]]

        for opt in options:
            if not (opt.get("text") or "").strip():
                opt["text"] = "(Veja a imagem da questão)"

        refs = []
        refs.extend(refs_by_qnum.get(qnum, []) or [])
        m = re.search(r"\bTEXTO\s+([IVX]{1,5})\b", (stem or "").upper())
        if m:
            label = m.group(1)
            if label in refs_by_label:
                refs.append(refs_by_label[label])
        if refs:
            stem = _apply_refs_to_stem(stem, refs)

        all_questions.append({
            "number": qnum,
            "page": info["page"],
            "bbox": info["bbox"],
            "stem": stem,
            "options": options,
            "_references": refs,
        })

    doc.close()
    print(f"\n[CHECK] Garbled stems: {garbled_count}/90 | OCR used: {ocr_used}/90", flush=True)
    questions_with_assets = crop_assets(all_questions, args.year, page_images, bbox_index=rect_index)
    questions_with_assets = apply_reference_assets(questions_with_assets, args.year, page_images)

    gabarito_path = os.path.join(PROVAS_DIR, f"g{str(args.year)[-2:]}.pdf")
    gabarito = extract_gabarito(gabarito_path) if os.path.exists(gabarito_path) else {}
    prev_by_id = {}
    prev_path = os.path.join(DATA_DIR, f"fuvest-{args.year}.json")
    if os.path.exists(prev_path):
        try:
            with open(prev_path, "r", encoding="utf-8") as f:
                prev = json.load(f)
            for pq in prev.get("questions", []) or []:
                pid = pq.get("id")
                if pid:
                    prev_by_id[pid] = pq
        except Exception:
            prev_by_id = {}
    final_questions = []
    for q in questions_with_assets:
        num = q.get('number')
        if not num: continue
        correct = gabarito.get(num)
        if correct not in ["A", "B", "C", "D", "E"]:
            raise RuntimeError(f"Sem gabarito para questão {num} ({args.year}).")
        q['answer'] = {"correct": correct}
        q['id'] = f"fuvest-{args.year}-q{num:02d}"
        q['year'] = args.year
        q['explanation'] = {
            "theory": "Pendente",
            "steps": [],
            "distractors": {"A": "", "B": "", "C": "", "D": "", "E": ""},
            "finalSummary": ""
        }
        prev_q = prev_by_id.get(q['id'])
        if prev_q:
            prev_exp = (prev_q.get('explanation') or {})
            if (prev_exp.get('theory') or "").strip() and prev_exp.get('theory') != 'Pendente':
                q['explanation'] = prev_exp
            if prev_q.get('tags'):
                q['tags'] = prev_q.get('tags')
        if "_references" in q:
            q.pop("_references", None)
        q['assets'] = {"questionImage": q.pop('asset_path', None)}
        final_questions.append(q)
    output_json_path = os.path.join(DATA_DIR, f"fuvest-{args.year}.json")
    final_data = {
        "year": args.year,
        "source": {
            "provaPdf": os.path.basename(pdf_path),
            "gabaritoPdf": os.path.basename(gabarito_path)
        },
        "generatedAt": datetime.now().isoformat(),
        "questions": final_questions
    }
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    print(f"\n[DONE] Processo concluido para {args.year}!")


if __name__ == "__main__":
    main()
