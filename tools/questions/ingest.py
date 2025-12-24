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

def crop_assets(questions, year, page_image_paths, padding=15):
    print("\n[CLIP] Recortando assets das questoes...", flush=True)
    for question in questions:
        q_num = question.get("number")
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
    args = parser.parse_args()

    page_images = render_pdf_to_images(os.path.join(PROVAS_DIR, f"p{str(args.year)[-2:]}.pdf"), args.year)
    if not page_images: sys.exit(1)

    all_questions = []
    for i, image_path in enumerate(page_images):
        data = extract_content_from_image(image_path, args.year)
        if data and 'questions' in data:
            for q in data['questions']:
                q['page'] = i + 1
            all_questions.extend(data['questions'])

    questions_with_assets = crop_assets(all_questions, args.year, page_images)
    
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
