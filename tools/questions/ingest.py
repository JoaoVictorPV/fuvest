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
import google.generativeai as genai

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
    """Inicializa o cliente Gemini somente se/when necessário.

    Isso evita gastar quota e tempo em execuções determinísticas (sem IA).
    """
    global gemini_vision_model
    if gemini_vision_model is not None:
        return gemini_vision_model

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY or GEMINI_API_KEY == "SUA_CHAVE_AQUI":
        raise ValueError("A variável de ambiente GEMINI_API_KEY não foi definida.")

    genai.configure(api_key=GEMINI_API_KEY)

    # IMPORTANTE:
    # Para extração/visão (OCR + bboxes) queremos um modelo multimodal forte.
    # Evitamos modelos de image-generation.
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
    """Heurística para detectar texto 'corrompido' vindo de PDFs com camada ruim."""
    t = (text or "").strip()
    if not t:
        return True

    # muitos caracteres estranhos e baixa proporção de letras
    letters = sum(ch.isalpha() for ch in t)
    ratio = letters / max(1, len(t))
    weird = sum(ch in "'&$%{}[]\\" for ch in t)

    if (len(t) > 40 and ratio < 0.25) or weird > 10:
        return True

    return False


def _normalize_spaces(s: str) -> str:
    s = (s or "").replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _looks_like_non_textual_option(text: str) -> bool:
    """Heurística para quando a alternativa é essencialmente figura/fórmula.

    Casos típicos:
    - Notação matemática que vira caracteres quebrados
    - Alternativa capturada como "(D)" / "50" / número solto
    - Texto com proporção muito baixa de letras
    """
    t = _normalize_spaces(text)
    if not t:
        return True

    # apenas letra/parenteses
    if re.fullmatch(r"\(?[A-E]\)?", t):
        return True

    # apenas número curto (ex: "50")
    if re.fullmatch(r"\d{1,3}", t):
        return True

    letters = sum(ch.isalpha() for ch in t)
    ratio = letters / max(1, len(t))
    # muitos símbolos matemáticos ou comparações
    sym = sum(ch in "=<>∪∩±×÷*/^_" for ch in t)

    if (len(t) > 12 and ratio < 0.35) or sym >= 3:
        return True

    # "Note e adote" é conteúdo de apoio (não alternativa)
    if "note e adote" in t.lower():
        return True

    return False


def _sanitize_option_text(text: str) -> str:
    """Normaliza/limpa texto de alternativa.

    Se o texto for ruim (equação/figura/caixa de aviso), devolve um placeholder único.
    """
    t = _normalize_spaces(text)

    # corta "vazamentos" de blocos de referência ou avisos que às vezes
    # entram no texto das alternativas.
    for marker in ["TEXTO PARA AS QUEST", "TEXTO PARA AS QUESTÕES", "NOTE E ADOTE"]:
        idx = t.upper().find(marker)
        if idx >= 0:
            t = t[:idx].strip()
            break

    if _looks_like_non_textual_option(t):
        return "(Veja a imagem da questão)"

    # remove lixo comum do fim: número de próxima questão (ex: "... 43")
    t = re.sub(r"\s+\d{1,2}$", "", t).strip()
    if not t:
        return "(Veja a imagem da questão)"
    return t


def _parse_question_targets_from_text(text: str):
    """Extrai números de questões a partir de textos do tipo:
    - "TEXTO PARA AS QUESTÕES 58 E 59"
    - "TEXTO PARA AS QUESTÕES DE 45 A 47"

    Retorna lista de ints.
    """
    t = _normalize_spaces(text).upper()
    nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b", t)]
    if not nums:
        return []

    # padrão com "DE X A Y"
    m = re.search(r"\bDE\s+(\d{1,2})\s+A\s+(\d{1,2})\b", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if 1 <= a <= 90 and 1 <= b <= 90 and a <= b:
            return list(range(a, b + 1))

    # se tiver 2+ números, usa os números (ex: "58 e 59")
    nums = [n for n in nums if 1 <= n <= 90]
    # remove duplicados preservando ordem
    seen = set()
    out = []
    for n in nums:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _extract_reference_blocks(doc: fitz.Document, dpi: int = 200):
    """Extrai blocos de referência que valem para múltiplas questões.

    Suporta:
    - "TEXTO PARA AS QUESTÕES ..." (mapeado por número de questão)
    - "TEXTO I/II/III/..." (mapeado por rótulo)

    Retorno:
      (by_qnum, by_label)
      by_qnum: {qnum: [ {"page":int, "rect_pt":[x0,y0,x1,y1], "bbox_px":{x,y,w,h}, "title":str, "text":str} ]}
      by_label: {"III": {"page":..., "rect_pt":..., "bbox_px":..., "title":..., "text":...}}
    """
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
        # transforma em y0 por coluna
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

            # --- Range: "TEXTO PARA AS QUESTÕES" ---
            if "TEXTO PARA AS QUEST" in t_up:
                targets = _parse_question_targets_from_text(t_up)
                if not targets:
                    continue

                col = 0 if x0 < mid_x else 1
                col_x0, col_x1 = (0, mid_x) if col == 0 else (mid_x, page_w)
                # fim = próximo marcador abaixo no mesmo col
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

            # --- Named: "TEXTO I/II/III" ---
            m = re.search(r"\bTEXTO\s+([IVX]{1,5})\b", t_up)
            if m and "TEXTO PARA" not in t_up:
                label = m.group(1)
                col = 0 if x0 < mid_x else 1
                col_x0, col_x1 = (0, mid_x) if col == 0 else (mid_x, page_w)
                y_end = page_h
                # encerra no próximo marcador de questão (ou outro TEXTO) abaixo
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
    """Extração multimodal (bboxes + stem + opções) por página.

    Usado como fallback (ou modo principal) quando o PDF é escaneado ou a camada de texto
    está corrompida (ex: 2021).

    Cache: tools/questions/cache/<ano>/vision_pages/<sha256>.json
    """
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

    resp = model.generate_content(
        [prompt, image],
        generation_config={"response_mime_type": "application/json"},
    )

    # Alguns modelos podem bloquear a resposta por motivo de copyright.
    # Nesses casos, retornamos vazio e seguimos com pipeline determinístico.
    try:
        data = json.loads(resp.text)
    except Exception as e:
        print(f"\n[WARN] Vision extraction falhou (provável bloqueio/sem resposta): {e}", flush=True)
        return {"page": None, "questions": []}

    # normalização leve
    qs = data.get("questions") or []
    for q in qs:
        q["stem"] = _normalize_spaces(q.get("stem", ""))
        opts = q.get("options") or []
        for o in opts:
            o["text"] = _normalize_spaces(o.get("text", ""))

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data


def _auto_trim_whitespace(img: Image.Image, pad: int = 10):
    """Recorta automaticamente bordas quase-brancas para melhorar enquadramento.

    - Converte para escala de cinza
    - Considera como 'conteúdo' pixels mais escuros que um limiar
    - Faz bounding box do conteúdo e aplica padding
    """
    try:
        gray = img.convert("L")
        # binariza: conteúdo = pixels escuros
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
    """Modelo 'texto' (mas multimodal) recomendado para OCR/leitura do gabarito.

    Preferência: gemini-2.0-flash (não-lite). Fallback: gemini-1.5-flash.
    """
    global gemini_text_model
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


def render_pdf_to_images(pdf_path, year, dpi=200):
    image_paths = []
    year_output_dir = os.path.join(OUTPUT_DIR, str(year), "pages")
    os.makedirs(year_output_dir, exist_ok=True)
    print(f"[*] Renderizando paginas de {os.path.basename(pdf_path)}...", flush=True)
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=dpi)
            output_path = os.path.join(year_output_dir, f"page_{page_num + 1:02d}.png")
            pix.save(output_path)
            image_paths.append(output_path)
        print(f"[OK] {len(doc)} paginas convertidas.", flush=True)
        doc.close()
        return image_paths
    except Exception as e:
        print(f"[ERRO] Falha ao processar PDF: {e}", flush=True)
        return []


def _detect_question_markers_from_pdf_page(page: fitz.Page):
    """Detecta posições (em pontos PDF) onde começam as questões.

    Estratégia:
    - varre o texto estruturado (dict) e procura por tokens que parecem o número da questão
      (ex: "1", "23", "45")
    - retorna uma lista de (qnum:int, bbox:tuple(x0,y0,x1,y1)) em pontos

    Observação: isso é determinístico e geralmente mais confiável do que bboxes gerados por IA.
    """
    # Implementação mais robusta via "words" (evita problemas de encoding e spans quebrados)
    words = page.get_text("words") or []
    # words: x0,y0,x1,y1,"word",block,line,word
    if not words:
        return []

    rect = page.rect
    page_w = rect.width
    mid_x = page_w / 2.0

    # margem mais relaxada (questões às vezes vêm mais indentadas)
    # 2021+ tende a vir mais "pra dentro"; então deixamos bem permissivo.
    margin_pt = 520

    num_re = re.compile(r"^(\d{1,2})(?:[\.)])?$")

    # agrupa por linha usando (block,line)
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
        # aceitamos apenas linhas curtinhas, ex: "3" / "3." / "3)"
        if len(joined) > 4:
            continue
        m = num_re.match(joined)
        if not m:
            continue

        qnum = int(m.group(1))
        x0 = min(t[0] for t in items_sorted)
        y0 = min(t[1] for t in items_sorted)
        x1 = max(t[2] for t in items_sorted)
        y1 = max(t[3] for t in items_sorted)

        # checagem de margem (coluna) - permissiva para não perder questões.
        # Ainda assim evita capturar números no meio da coluna.
        if x0 < mid_x:
            if x0 > margin_pt:
                continue
        else:
            if x0 > (mid_x + margin_pt):
                continue

        candidates.append((qnum, (x0, y0, x1, y1)))

    markers = candidates

    # remove duplicatas mantendo a menor y (primeira ocorrência)
    best = {}
    for qnum, bbox in markers:
        if qnum not in best or bbox[1] < best[qnum][1]:
            best[qnum] = bbox
    return [(qnum, best[qnum]) for qnum in sorted(best.keys())]


def build_question_bboxes_from_pdf(pdf_path: str, dpi: int = 200):
    """Gera bboxes em PIXELS (para recorte do PNG) por página e número de questão.

    - Usa coordenadas do PDF (pontos) e converte para pixels considerando o DPI do render.
    - Assume páginas com 2 colunas: divide a página ao meio e recorta a coluna inteira entre
      início de uma questão e início da próxima questão na mesma coluna.
    """
    doc = fitz.open(pdf_path)
    scale = dpi / 72.0

    page_map = {}  # {page_num: {qnum: {x,y,w,h}}}
    for i in range(len(doc)):
        page = doc.load_page(i)
        rect = page.rect
        page_w = rect.width
        page_h = rect.height
        mid_x = page_w / 2.0

        markers = _detect_question_markers_from_pdf_page(page)
        if not markers:
            continue

        # classifica por coluna (0=esq, 1=dir) usando x0 do bbox
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

                # padding leve em pontos (evita cortar borda do texto)
                pad_pt = 6
                x0p = max(0, col_x0 - pad_pt)
                x1p = min(page_w, col_x1 + pad_pt)
                y0p = max(0, y0 - pad_pt)
                y1p = min(page_h, y1 + pad_pt)

                # converte para pixels
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
    """Índice determinístico por número de questão com retângulo em pontos (PDF) e bbox em pixels.

    Retorno:
      { qnum: {"page": int, "rect": [x0,y0,x1,y1] (pt), "bbox": {x,y,w,h} (px)} }

    Observação:
    - O recorte é a *coluna inteira* entre o início da questão e o início da próxima questão.
    - Isso resolve (1) imagens trocadas e (2) bboxes aleatórios da IA.
    """
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

        # Importante: NÃO filtramos por sequência esperada.
        # Queremos 100% das questões no JSON.

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
    """Extrai texto da questão a partir do PDF (determinístico) usando clip por retângulo.

    Retorna (stem, options[A..E]) ou (None, None) se não for confiável.
    """
    page = doc.load_page(page_num - 1)
    clip = fitz.Rect(*rect_pt)
    # Extração por words (mais robusta que text) para reconstruir linhas e captar alternativas
    words = page.get_text("words", clip=clip) or []
    # words: x0,y0,x1,y1,"word",block,line,word
    if not words:
        return None, None

    # agrupa por linha usando y0 aproximado
    words.sort(key=lambda w: (w[1], w[0]))
    line_groups = []  # [{"y":..., "x0":..., "tokens":[(x0,text), ...]}]
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

    # monta linhas (ordenando por x)
    lines = []
    for lg in line_groups:
        toks = [t[1] for t in sorted(lg["tokens"], key=lambda t: t[0])]
        line_text = " ".join(toks).strip()
        if line_text:
            lines.append((lg["x0"], line_text))

    if not lines:
        return None, None

    # remove um possível "3" solto no início
    if re.match(r"^\d{1,2}[\.)]?$", lines[0][1]):
        lines = lines[1:]
    if not lines:
        return None, None

    # Heurística de layout:
    # a coluna pode conter elementos "laterais" (ex: caixa cinza "Note e adote")
    # que não devem entrar na extração de alternativas. Como as alternativas
    # quase sempre começam alinhadas à esquerda, usamos a menor x0 como referência.
    base_x0 = min(x for (x, _) in lines)
    opt_x_max = base_x0 + 60
    cont_x_max = base_x0 + 85

    # detecta alternativas pelas primeiras palavras da linha
    # aceita: "A", "A)", "A.", "(A)", "A-" etc
    opt_head_re = re.compile(r"^\(?([A-E])\)?\s*$")
    opt_inline_re = re.compile(r"^\(?([A-E])\)?\s*[\).\-–:]\s*(.*)$")

    opt_lines = []  # (idx_line, key, text_after)
    for i, (x0, txt) in enumerate(lines):
        # ignora candidatos "muito à direita" (ex: caixas laterais)
        if x0 > opt_x_max:
            continue

        m = opt_inline_re.match(txt)
        if m:
            opt_lines.append((i, m.group(1), (m.group(2) or "").strip()))
            continue

        # caso: linha só com "A" e o texto vem na próxima linha
        m2 = opt_head_re.match(txt)
        if m2:
            opt_lines.append((i, m2.group(1), ""))

    if not opt_lines:
        stem = " ".join([t for (_, t) in lines]).strip()
        if len(stem) < 20:
            return None, None

        # Mesmo quando não conseguimos segmentar as alternativas em texto,
        # mantemos placeholders para o aluno usar o recorte (PNG).
        options = [{"key": k, "text": "(Veja a imagem da questão)"} for k in ["A", "B", "C", "D", "E"]]
        stem = re.sub(r"\s+", " ", stem.replace("\u00a0", " ")).strip()
        return stem, options

    # stem = tudo antes da primeira alternativa
    first_opt = opt_lines[0][0]
    stem = " ".join([t for (_, t) in lines[:first_opt]]).strip()
    if len(stem) < 20:
        return None, None

    # monta alternativas
    options_by_key = {}
    for idx, (line_i, key, inline_text) in enumerate(opt_lines):
        end = opt_lines[idx + 1][0] if idx + 1 < len(opt_lines) else len(lines)
        chunk = []
        if inline_text:
            chunk.append(inline_text)

        # se a primeira linha era só "A", tentamos pegar o texto da(s) próxima(s) linha(s)
        for j in range(line_i + 1, end):
            # ignora conteúdo fora do alinhamento (ex: "Note e adote" lateral)
            if lines[j][0] <= cont_x_max:
                chunk.append(lines[j][1])

        text = " ".join([c for c in chunk if c]).strip()
        options_by_key[key] = _sanitize_option_text(text)

    # validação: idealmente A..E e pelo menos 4 preenchidas.
    # Porém, para garantir 100% das questões no JSON sem quebrar o app,
    # quando faltar texto, preenchimos com placeholder para o aluno ler na imagem.
    for k in ["A", "B", "C", "D", "E"]:
        if not options_by_key.get(k):
            options_by_key[k] = "(Veja a imagem da questão)"

    options = [{"key": k, "text": options_by_key.get(k, "")} for k in ["A", "B", "C", "D", "E"]]

    # limpeza simples de espaços estranhos (NBSP etc)
    stem = re.sub(r"\s+", " ", stem.replace("\u00a0", " ")).strip()
    for opt in options:
        opt["text"] = _sanitize_option_text(opt.get("text", ""))

    return stem, options


def build_question_bbox_index(pdf_path: str, dpi: int = 200):
    """Cria um índice determinístico por número de questão.

    Retorno:
      { qnum: {"page": int, "bbox": {"x","y","w","h"}} }

    Importante: este índice é a fonte de verdade para recorte e deve prevalecer sobre
    page/bbox retornados pela IA (que podem estar errados).
    """
    page_map = build_question_bboxes_from_pdf(pdf_path, dpi=dpi)
    idx = {}
    for page_num, qmap in page_map.items():
        for qnum, bbox in qmap.items():
            # em caso de duplicata, fica com o primeiro que aparecer (normalmente o correto)
            if qnum not in idx:
                idx[qnum] = {"page": page_num, "bbox": bbox}
    return idx


def recrop_only(pdf_path: str, year: int, dpi: int = 200):
    """Regera apenas os recortes (assets) usando o JSON existente e bboxes do PDF.

    Não faz chamadas de IA.
    """
    json_path = os.path.join(DATA_DIR, f"fuvest-{year}.json")
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON nao encontrado: {json_path}")

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    page_images = render_pdf_to_images(pdf_path, year, dpi=dpi)
    bbox_index = build_question_rect_index(pdf_path, dpi=dpi)

    questions = data.get("questions", [])
    for q in questions:
        qnum = q.get("number")
        if qnum and qnum in bbox_index:
            q["page"] = bbox_index[qnum]["page"]
            q["bbox"] = bbox_index[qnum]["bbox"]

    questions_with_assets = crop_assets(questions, year, page_images, bbox_index=bbox_index)

    # regrava apenas assets no json
    for q in questions_with_assets:
        q.setdefault("assets", {})
        q["assets"]["questionImage"] = q.get("assets", {}).get("questionImage") or q.get("asset_path")
        if "asset_path" in q:
            q["assets"]["questionImage"] = q.pop("asset_path")

    data["questions"] = questions_with_assets
    data["generatedAt"] = datetime.now().isoformat()
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[OK] Recrop-only concluido: {json_path}")

def extract_content_from_image(image_path, year):
    print(f"\n[IA] Analisando: {os.path.basename(image_path)}", end="", flush=True)
    cache_key = hashlib.sha256(open(image_path, 'rb').read()).hexdigest()
    cache_dir = os.path.join(CACHE_DIR, str(year), "extraction")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{cache_key}.json")
    if os.path.exists(cache_file):
        print(" (CACHE HIT!)", flush=True)
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    print(" (API CALL...)", flush=True)
    try:
        image = Image.open(image_path)
        model = get_gemini_vision_model()
        prompt = """Sua tarefa e identificar CADA QUESTAO em uma pagina de prova.
REGRAS:
1) O bbox deve cercar EXATAMENTE e APENAS o conteudo da questao (enunciado + alternativas + figuras associadas).
2) IGNORE cabeçalhos, rodapés e logos.
3) O bbox e definido por: x, y, width, height em PIXELS.
4) Respeite a ordem das colunas.
Schema de saida:
{
  "page": number,
  "questions": [
    {
      "number": number,
      "stem": string,
      "options": [ {"key":"A"|"B"|"C"|"D"|"E", "text": string} ],
      "bbox": {"x": number, "y": number, "w": number, "h": number}
    }
  ]
}"""
        
        response = model.generate_content(
            [prompt, image],
            generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text)
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data
    except Exception as e:
        print(f"\n[ERRO] Falha na IA: {e}", flush=True)
        return None

def crop_assets(questions, year, page_image_paths, bbox_index=None, padding=15):
    print("\n[CLIP] Recortando assets das questoes...", flush=True)
    for question in questions:
        q_num = question.get("number")

        # Fonte de verdade para recorte: índice determinístico
        if bbox_index and q_num in bbox_index:
            question["page"] = bbox_index[q_num]["page"]
            bbox = bbox_index[q_num]["bbox"]
        else:
            bbox = question.get("bbox")

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
                # aperta bordas brancas (melhora muito o enquadramento quando o bbox
                # determinístico pega coluna inteira)
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


def _crop_reference_image(page_image_paths, ref_obj, padding_px: int = 14):
    """Recorta o bloco de referência a partir da imagem da página (renderizada)."""
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


def _combine_images_vertical(images, gap: int = 16, bg=(255, 255, 255)):
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


def apply_reference_assets(questions, year: int, page_image_paths):
    """Se a questão tiver refs, cria um PNG composto (refs + questão) e sobrescreve o asset."""
    for q in questions:
        refs = q.get("_references") or []
        refs = _dedupe_refs(refs)
        if not refs:
            continue

        asset_url = q.get("asset_path") or q.get("assets", {}).get("questionImage")
        if not asset_url:
            continue

        # caminho local do asset atual
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

def extract_gabarito(gabarito_pdf_path):
    """Extrai gabarito de gXX.pdf.

    Estratégia: regex tolerante em cima do texto extraído.
    Se o gabarito vier incompleto, abortamos para não gerar JSON inválido.
    """
    print(f"\n[GAB] Lendo gabarito...", flush=True)
    gabarito = {}
    doc = fitz.open(gabarito_pdf_path)
    text = "\n".join([page.get_text("text") for page in doc])
    doc.close()

    # padrões comuns: "1-A", "01 A", "1 A", "1) A" etc
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

    # Fallback: se o PDF for "mudo" (scaneado) o get_text falha.
    # Nesse caso, fazemos OCR via Gemini (2 páginas apenas) e cacheamos.
    if len(gabarito) < 90:
        gabarito = extract_gabarito_via_gemini(gabarito_pdf_path)

    # hard guard: precisamos do gabarito completo para garantir integridade
    if len(gabarito) < 90:
        missing = [i for i in range(1, 91) if i not in gabarito]
        raise RuntimeError(f"Gabarito incompleto ({len(gabarito)}/90). Faltando: {missing[:20]}...")

    return gabarito


def extract_gabarito_via_gemini(gabarito_pdf_path: str):
    """Extrai gabarito via Gemini Vision/Text (OCR).

    - Renderiza cada página do gabarito para PNG.
    - Envia para Gemini pedindo JSON com mapeamento 1..90.
    - Usa cache por hash do PDF.
    """
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
        # usa PIL Image em memória
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

    page_images = render_pdf_to_images(pdf_path, args.year)
    if not page_images: sys.exit(1)

    # BBoxes determinísticos via PDF (pixels), para corrigir recortes trocados/cortados.
    # Se o PDF tiver camada de texto corrompida (ex: 2021), faremos fallback multimodal.
    print("\n[*] Gerando índice determinístico (page/rect/bbox) via PyMuPDF...", flush=True)
    rect_index = build_question_rect_index(pdf_path, dpi=200)

    # Extração primária: determinística (sem IA) usando clip do PDF.
    # IMPORTANTE (robustez/definitivo):
    # - Para provas (pYY.pdf), NÃO tentamos OCR via Gemini por risco de bloqueio/copyright.
    # - Quando o texto do PDF estiver corrompido (ex: Fuvest 2021), substituímos por
    #   placeholders e garantimos que o aluno consiga resolver pela IMAGEM recortada.
    doc = fitz.open(pdf_path)

    # --- Blocos de referência (texto base para múltiplas questões) ---
    # Ex:
    # - "TEXTO PARA AS QUESTÕES 58 E 59" (range)
    # - "TEXTO III" (rótulo)
    # O objetivo é garantir que nenhuma questão fique "sem o texto".
    try:
        refs_by_qnum, refs_by_label = _extract_reference_blocks(doc, dpi=200)
    except Exception as e:
        print(f"[WARN] Falha ao extrair blocos de referência: {e}", flush=True)
        refs_by_qnum, refs_by_label = {}, {}
    all_questions = []
    garbled_count = 0

    for qnum in sorted(rect_index.keys()):
        info = rect_index[qnum]
        stem, options = extract_question_text_from_pdf(doc, info["page"], info["rect"])
        if stem is None or options is None:
            stem = "(Veja a imagem da questão)"
            options = [{"key": k, "text": "(Veja a imagem da questão)"} for k in ["A", "B", "C", "D", "E"]]

        # sanitização forte: se o texto estiver corrompido, não exibimos no frontend.
        if _is_garbled_text(stem):
            garbled_count += 1
            stem = "(Veja a imagem da questão)"
            options = [{"key": k, "text": "(Veja a imagem da questão)"} for k in ["A", "B", "C", "D", "E"]]

        # garante que nunca existam alternativas vazias
        for opt in options:
            if not (opt.get("text") or "").strip():
                opt["text"] = "(Veja a imagem da questão)"

        # --- Aplica referências ao enunciado + marca para compor asset ---
        refs = []
        refs.extend(refs_by_qnum.get(qnum, []) or [])

        # Caso "Texto III" mencionado no enunciado: tenta anexar o bloco correspondente.
        # Ex: "No texto III, ..."
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

    print(f"\n[CHECK] Garbled stems: {garbled_count}/90. (não usamos vision/OCR de prova)", flush=True)

    # Recorte sempre determinístico (com auto-trim pós-recorte).
    questions_with_assets = crop_assets(all_questions, args.year, page_images, bbox_index=rect_index)

    # Se existirem blocos de referência para a questão, compomos um PNG:
    # [referência 1]
    # [referência 2]
    # [questão]
    questions_with_assets = apply_reference_assets(questions_with_assets, args.year, page_images)
    
    gabarito_path = os.path.join(PROVAS_DIR, f"g{str(args.year)[-2:]}.pdf")
    gabarito = extract_gabarito(gabarito_path) if os.path.exists(gabarito_path) else {}
    
    # Se já existe dataset anterior, preserva campos enriquecidos (explanation/tags) quando existirem.
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
        # Placeholder compatível com schema.json e com enrich.py (que procura theory == "Pendente")
        q['explanation'] = {
            "theory": "Pendente",
            "steps": [],
            "distractors": {"A": "", "B": "", "C": "", "D": "", "E": ""},
            "finalSummary": ""
        }

        # preserva enrich anterior se existir
        prev_q = prev_by_id.get(q['id'])
        if prev_q:
            prev_exp = (prev_q.get('explanation') or {})
            if (prev_exp.get('theory') or "").strip() and prev_exp.get('theory') != 'Pendente':
                q['explanation'] = prev_exp
            if prev_q.get('tags'):
                q['tags'] = prev_q.get('tags')
        # remove metadata interna (não faz parte do schema público)
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
