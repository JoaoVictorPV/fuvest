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
    
    # Diagnóstico: Listar modelos disponíveis
    print("[DIAG] Listando modelos disponiveis...")
    model_found = False
    MODEL_ID = None
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            # Prioriza gemini-2.0-flash, depois 1.5-flash
            if "gemini-2.0-flash" in m.name and "lite" not in m.name:
                MODEL_ID = m.name
                model_found = True
            elif not model_found and "gemini-1.5-flash" in m.name:
                MODEL_ID = m.name
                model_found = True
    
    if not model_found:
        print("[ERRO] Modelo compativel nao encontrado na sua conta.")
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
        print(f"[OK] Sucesso! {len(doc)} paginas convertidas e salvas em '{year_output_dir}'", flush=True)
        doc.close()
        return image_paths
    except Exception as e:
        print(f"[ERRO] Falha ao processar o PDF '{pdf_path}': {e}", flush=True)
        return []

def extract_content_from_image(image_path, year):
    print(f"\n[IA] Extraindo conteudo de: {os.path.basename(image_path)}", end="", flush=True)
    cache_key = hashlib.sha256(open(image_path, 'rb').read()).hexdigest()
    cache_dir = os.path.join(CACHE_DIR, str(year), "extraction")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{cache_key}.json")
    if os.path.exists(cache_file):
        print(" (CACHE HIT!)", flush=True)
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    print(" (CHAMADA DE API...)", flush=True)
    try:
        image = Image.open(image_path)
        prompt = """Você é um extrator de provas de vestibular brasileiro. Sua tarefa é transformar uma PÁGINA de prova (imagem) em JSON estrito.
Regras: 
1) Respeite ordem de leitura correta para prova em 2 colunas.
2) Detecte cada questão com seu número.
3) Para cada questão, extraia: enunciado (stem) e alternativas A-E (options).
4) Retorne também bounding box aproximada (bbox) da questão inteira na página: x,y,width,height (pixels na imagem recebida).
5) Não invente texto. Se algo estiver ilegível, marque como '[ILEGIVEL]'.
6) Output deve ser SOMENTE JSON, sem texto adicional.
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
        print(f"\n[ERRO] Falha na extração com IA para '{image_path}': {e}", flush=True)
        return None

def crop_and_save_question_assets(questions, year, page_image_paths):
    print("\n[CLIP] Recortando e salvando imagens das questoes...", flush=True)
    year_assets_dir = os.path.join(ASSETS_DIR, str(year))
    os.makedirs(year_assets_dir, exist_ok=True)
    updated_questions = []
    for question in questions:
        q_num = question.get("number")
        bbox = question.get("bbox")
        page_idx = int(question.get("page", 0)) - 1
        if q_num is None or bbox is None or page_idx < 0:
            continue
        try:
            page_image_path = page_image_paths[page_idx]
            with Image.open(page_image_path) as img:
                x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
                crop_area = (x, y, x + w, y + h)
                cropped_img = img.crop(crop_area)
                question_asset_dir = os.path.join(year_assets_dir, f"q{q_num:02d}")
                os.makedirs(question_asset_dir, exist_ok=True)
                asset_path = os.path.join(question_asset_dir, "image.png")
                cropped_img.save(asset_path, "PNG")
                question['assets'] = {"questionImage": f"/assets/questions/{year}/q{q_num:02d}/image.png"}
                updated_questions.append(question)
        except Exception as e:
            print(f"[ERRO] Falha ao recortar imagem para questao {q_num}: {e}", flush=True)
            question['assets'] = {"questionImage": None}
            updated_questions.append(question)
    print(f"[OK] Imagens recortadas salvas em '{year_assets_dir}'", flush=True)
    return updated_questions

def extract_gabarito(gabarito_pdf_path):
    print(f"\n[GAB] Extraindo gabarito de: {os.path.basename(gabarito_pdf_path)}", flush=True)
    gabarito = {}
    try:
        doc = fitz.open(gabarito_pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()

        import re
        matches = re.findall(r'(\d+)[\s-]*([ABCDE])', text)
        for num_str, letter in matches:
            gabarito[int(num_str)] = letter
        
        print(f"[OK] Gabarito extraído! {len(gabarito)} respostas encontradas.", flush=True)
        return gabarito
    except Exception as e:
        print(f"[ERRO] Falha ao extrair gabarito: {e}", flush=True)
        return {}

def main():
    parser = argparse.ArgumentParser(description="Pipeline de Ingestao de Provas da Fuvest.")
    parser.add_argument("--year", type=int, required=True, help="Ano da prova a ser processada (ex: 2019).")
    args = parser.parse_args()
    print(f"[*] Iniciando Fase 2 para o ano de {args.year}...", flush=True)
    
    year_str = str(args.year)[-2:]
    prova_path = os.path.join(PROVAS_DIR, f"p{year_str}.pdf")
    gabarito_path = os.path.join(PROVAS_DIR, f"g{year_str}.pdf")

    if not os.path.exists(prova_path):
        print(f"[ERRO] Arquivo da prova '{prova_path}' não encontrado.", flush=True)
        sys.exit(1)
    
    # 1. Renderizar Imagens
    page_images = render_pdf_to_images(prova_path, args.year)
    if not page_images:
        sys.exit(1)

    # 2. Extrair Conteúdo via IA
    all_extracted_questions = []
    for image_path in page_images:
        extracted_data = extract_content_from_image(image_path, args.year)
        if extracted_data and 'questions' in extracted_data:
            for q in extracted_data['questions']:
                q['page'] = extracted_data.get('page', extracted_data.get('page_number', 0))
            all_extracted_questions.extend(extracted_data['questions'])

    # 3. Recortar Assets
    questions_with_assets = crop_and_save_question_assets(all_extracted_questions, args.year, page_images)

    # 4. Cruzar com Gabarito
    if os.path.exists(gabarito_path):
        gabarito = extract_gabarito(gabarito_path)
    else:
        print(f"[AVISO] Gabarito '{gabarito_path}' nao encontrado.", flush=True)
        gabarito = {}
    
    final_questions = []
    for q in questions_with_assets:
        num = q.get('number', 0)
        if num is None or num == 0:
            continue
            
        if num in gabarito:
            q['answer'] = {"correct": gabarito[num]}
        else:
            q['answer'] = {"correct": None}
            print(f"[AVISO] Gabarito não encontrado para a questao {num}", flush=True)
        
        q['id'] = f"fuvest-{args.year}-q{num:02d}"
        q['year'] = args.year
        q['explanation'] = {
            "theory": "Pendente",
            "steps": [],
            "distractors": {"A": "", "B": "", "C": "", "D": "", "E": ""},
            "finalSummary": ""
        }
        final_questions.append(q)

    output_json_path = os.path.join(DATA_DIR, f"fuvest-{args.year}.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    
    final_data = {
        "year": args.year,
        "source": {
            "provaPdf": f"provas/p{year_str}.pdf",
            "gabaritoPdf": f"provas/g{year_str}.pdf"
        },
        "generatedAt": datetime.now().isoformat(),
        "questions": final_questions
    }

    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] FASE 2 CONCLUIDA COM SUCESSO!", flush=True)
    print(f"[*] Dataset gerado: {output_json_path}", flush=True)
    print(f"[*] Imagens salvas em: {os.path.join(ASSETS_DIR, str(args.year))}", flush=True)

if __name__ == "__main__":
    main()
