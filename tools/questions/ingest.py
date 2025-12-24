import os
import sys
import fitz  # PyMuPDF
from PIL import Image
import argparse
import json
import hashlib
from datetime import datetime
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

# --- Inicialização do Cliente Gemini ---
try:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY or GEMINI_API_KEY == "SUA_CHAVE_AQUI":
        raise ValueError("A variável de ambiente GEMINI_API_KEY não foi definida.")
    
    genai.configure(api_key=GEMINI_API_KEY)
    
    # Busca o melhor modelo disponível
    model_found = False
    MODEL_ID = None
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            if "gemini-2.0-flash-exp-image-generation" in m.name:
                MODEL_ID = m.name
                model_found = True
                break
            elif "gemini-2.0-flash" in m.name and "lite" not in m.name:
                MODEL_ID = m.name
                model_found = True
            elif not model_found and "gemini-1.5-flash" in m.name:
                MODEL_ID = m.name
                model_found = True
    
    if not MODEL_ID:
        print("[ERRO] Modelo compativel nao encontrado.")
        sys.exit(1)
        
    print(f"[OK] Usando modelo: {MODEL_ID}")
    gemini_vision_model = genai.GenerativeModel(MODEL_ID)

except Exception as e:
    print(f"[ERRO] Falha ao configurar o cliente Gemini: {e}")
    sys.exit(1)


def render_pdf_to_images(pdf_path, year, dpi=200):
    image_paths = []
    year_output_dir = os.path.join(OUTPUT_DIR, str(year), "pages")
    os.makedirs(year_output_dir, exist_ok=True)
    print(f"[*] Processando PDF: {os.path.basename(pdf_path)}", flush=True)
    print(f"[*] Renderizando paginas em {dpi} DPI...", flush=True)
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=dpi)
            output_path = os.path.join(year_output_dir, f"page_{page_num + 1:02d}.png")
            pix.save(output_path)
            image_paths.append(output_path)
        print(f"[OK] Sucesso! {len(doc)} paginas convertidas.", flush=True)
        doc.close()
        return image_paths
    except Exception as e:
        print(f"[ERRO] Falha ao processar o PDF: {e}", flush=True)
        return []

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
        # Refinamento do prompt para BBox mais precisa
        prompt = """Você é um especialista em visão computacional e extração de provas.
Sua tarefa é identificar CADA QUESTÃO em uma página de prova (que pode ter 2 colunas).

REGRAS CRÍTICAS PARA BOUNDING BOX (bbox):
1) O bbox deve cercar EXATAMENTE e APENAS o conteúdo da questão (enunciado + alternativas + figuras associadas).
2) IGNORE cabeçalhos de página, números de página, logotipos da FUVEST e rodapés.
3) O bbox é definido por: x, y, width, height em PIXELS da imagem original.
4) Respeite a ordem das colunas (esquerda primeiro, depois direita).

Schema esperado:
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
        
        response = gemini_vision_model.generate_content(
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

def find_and_crop_figure(question, page_image_path, year, padding=10):
    print(f" -> Buscando figura para Q{question.get('number', 'N/A')}...", end="", flush=True)
    
    try:
        image = Image.open(page_image_path)
        
        # Novo prompt, super específico para a figura
        figure_prompt = f"""Análise de Imagem Focada:
Dada a imagem da página e o enunciado de uma questão, seu único objetivo é retornar o bounding box (bbox) da FIGURA, GRÁFICO ou TABELA principal mencionada no enunciado.
- Enunciado da Questão: "{question.get('stem', '')}"
- Se não houver figura, retorne um bbox nulo.
- O bbox deve ser preciso, contendo apenas a área visual da figura.

Retorne SOMENTE um JSON com o seguinte schema:
{{
  "figure_bbox": {{"x": number, "y": number, "w": number, "h": number}} | null
}}"""

        response = gemini_vision_model.generate_content(
            [figure_prompt, image],
            generation_config={"response_mime_type": "application/json"}
        )
        
        bbox_data = json.loads(response.text)
        figure_bbox = bbox_data.get("figure_bbox")

        if not figure_bbox:
            print(" Nenhuma figura encontrada.", flush=True)
            return None # Retorna None se não achar a figura

        # Se encontrou, recorta
        img_w, img_h = image.size
        x = max(0, figure_bbox['x'] - padding)
        y = max(0, figure_bbox['y'] - padding)
        w = min(img_w - x, figure_bbox['w'] + (padding * 2))
        h = min(img_h - y, figure_bbox['h'] + (padding * 2))
        
        crop_area = (x, y, x + w, y + h)
        cropped_img = image.crop(crop_area)
        
        question_asset_dir = os.path.join(ASSETS_DIR, str(year), f"q{question['number']:02d}")
        os.makedirs(question_asset_dir, exist_ok=True)
        asset_path = os.path.join(question_asset_dir, "image.png")
        cropped_img.save(asset_path, "PNG")
        
        print(" [OK]", flush=True)
        return f"/assets/questions/{year}/q{question['number']:02d}/image.png"

    except Exception as e:
        print(f"\n[ERRO] Falha na busca de figura: {e}", flush=True)
        return None

def extract_gabarito(gabarito_pdf_path):
    print(f"\n[GAB] Lendo gabarito: {os.path.basename(gabarito_pdf_path)}", flush=True)
    gabarito = {}
    try:
        doc = fitz.open(gabarito_pdf_path)
        text = "".join([page.get_text() for page in doc])
        doc.close()
        import re
        matches = re.findall(r'(\d+)[\s-]*([ABCDE])', text)
        for num_str, letter in matches:
            gabarito[int(num_str)] = letter
        print(f"[OK] {len(gabarito)} respostas extraidas.", flush=True)
        return gabarito
    except Exception as e:
        print(f"[ERRO] Falha no gabarito: {e}", flush=True)
        return {}

def main():
    parser = argparse.ArgumentParser(description="Pipeline de Ingestao de Provas.")
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()

    page_images = render_pdf_to_images(os.path.join(PROVAS_DIR, f"p{str(args.year)[-2:]}.pdf"), args.year)
    if not page_images: sys.exit(1)

    all_questions = []
    keywords = ['figura', 'gráfico', 'imagem', 'tabela', 'charge', 'mapa', 'esquema']

    for i, image_path in enumerate(page_images):
        page_num = i + 1
        data = extract_content_from_image(image_path, args.year)
        if not (data and 'questions' in data):
            continue

        for q in data['questions']:
            q['page'] = page_num
            stem = q.get('stem')
            
            # Pula a questão se o enunciado (stem) for nulo
            if not stem:
                print(f"\n[AVISO] Questao sem enunciado na pagina {page_num}. Pulando.")
                continue

            # Lógica do duplo prompt
            if any(keyword in stem.lower() for keyword in keywords):
                asset_path = find_and_crop_figure(q, image_path, args.year)
                q['assets'] = {"questionImage": asset_path}
            else:
                q['assets'] = {"questionImage": "/assets/questions/holder.png"} # Usa o placeholder
            
            all_questions.append(q)

    gabarito_path = os.path.join(PROVAS_DIR, f"g{str(args.year)[-2:]}.pdf")
    gabarito = extract_gabarito(gabarito_path) if os.path.exists(gabarito_path) else {}
    final_questions = []
    
    for q in all_questions:
        num = q.get('number')
        if not num: continue

        q['answer'] = {"correct": gabarito.get(num)}
        q['id'] = f"fuvest-{args.year}-q{num:02d}"
        q['year'] = args.year
        q['explanation'] = {"theory": "Pendente", "steps": [], "distractors": {"A":"","B":"","C":"","D":"","E":""}, "finalSummary": ""}
        final_questions.append(q)
        
    output_json_path = os.path.join(DATA_DIR, f"fuvest-{args.year}.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    final_data = {"year": args.year, "generatedAt": datetime.now().isoformat(), "questions": final_questions}
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] Processo concluido para {args.year}!")

if __name__ == "__main__":
    main()
