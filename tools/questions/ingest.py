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

    MODEL_ID = None
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods and "gemini-2.0-flash-exp-image-generation" in m.name:
            MODEL_ID = m.name
            break

    if not MODEL_ID:
        raise RuntimeError("Modelo Gemini compatível não encontrado.")

    print(f"[OK] Usando modelo: {MODEL_ID}")
    gemini_vision_model = genai.GenerativeModel(MODEL_ID)
    return gemini_vision_model


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
    margin_pt = 240

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

        # checagem de margem (coluna)
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

    # detecta alternativas pelas primeiras palavras da linha
    # aceita: "A", "A)", "A.", "(A)", "A-" etc
    opt_head_re = re.compile(r"^\(?([A-E])\)?\s*$")
    opt_inline_re = re.compile(r"^\(?([A-E])\)?\s*[\).\-–:]\s*(.*)$")

    opt_lines = []  # (idx_line, key, text_after)
    for i, (x0, txt) in enumerate(lines):
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
        options = [{"key": k, "text": ""} for k in ["A", "B", "C", "D", "E"]]
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
            chunk.append(lines[j][1])

        text = " ".join([c for c in chunk if c]).strip()
        options_by_key[key] = text

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
        opt["text"] = re.sub(r"\s+", " ", opt["text"].replace("\u00a0", " ")).strip()

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
                
                asset_dir = os.path.join(ASSETS_DIR, str(year), f"q{q_num:02d}")
                os.makedirs(asset_dir, exist_ok=True)
                asset_path = os.path.join(asset_dir, "image.png")
                cropped_img.save(asset_path, "PNG")
                
                question['asset_path'] = f"/assets/questions/{year}/q{q_num:02d}/image.png"
                
        except Exception as e:
            print(f"[ERRO] Falha no recorte da Q{q_num}: {e}", flush=True)
            question['asset_path'] = "/assets/questions/holder.png"
            
    return questions

def extract_gabarito(gabarito_pdf_path):
    # (Simplified for brevity)
    print(f"\n[GAB] Lendo gabarito...", flush=True)
    gabarito = {}
    doc = fitz.open(gabarito_pdf_path)
    text = "".join([page.get_text() for page in doc])
    import re
    matches = re.findall(r'(\d+)[\s-]*([ABCDE])', text)
    for num_str, letter in matches:
        gabarito[int(num_str)] = letter
    return gabarito

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
    # Se não acharmos bbox para alguma questão, caímos no bbox da IA (quando existir).
    print("\n[*] Gerando índice determinístico (page/rect/bbox) via PyMuPDF...", flush=True)
    rect_index = build_question_rect_index(pdf_path, dpi=200)

    # Extração de texto determinística (sem IA) usando clip do PDF.
    doc = fitz.open(pdf_path)
    all_questions = []
    for qnum in sorted(rect_index.keys()):
        info = rect_index[qnum]
        stem, options = extract_question_text_from_pdf(doc, info["page"], info["rect"])
        if stem is None or options is None:
            # abandona questão se não extrair texto mínimo confiável
            continue

        all_questions.append({
            "number": qnum,
            "page": info["page"],
            "bbox": info["bbox"],
            "stem": stem,
            "options": options,
        })
    doc.close()

    questions_with_assets = crop_assets(all_questions, args.year, page_images, bbox_index=rect_index)
    
    gabarito_path = os.path.join(PROVAS_DIR, f"g{str(args.year)[-2:]}.pdf")
    gabarito = extract_gabarito(gabarito_path) if os.path.exists(gabarito_path) else {}
    
    final_questions = []
    for q in questions_with_assets:
        num = q.get('number')
        if not num: continue

        q['answer'] = {"correct": gabarito.get(num)}
        q['id'] = f"fuvest-{args.year}-q{num:02d}"
        q['year'] = args.year
        q['explanation'] = {"theory": "Pendente"}
        q['assets'] = {"questionImage": q.pop('asset_path', None)}
        final_questions.append(q)
        
    output_json_path = os.path.join(DATA_DIR, f"fuvest-{args.year}.json")
    final_data = {"year": args.year, "generatedAt": datetime.now().isoformat(), "questions": final_questions}
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] Processo concluido para {args.year}!")

if __name__ == "__main__":
    main()
