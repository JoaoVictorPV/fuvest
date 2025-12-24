import os
import sys
import json
import hashlib
import argparse
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
CACHE_DIR = os.path.join(PROJECT_ROOT, "tools", "questions", "cache")
DATA_DIR = os.path.join(PROJECT_ROOT, "public", "data", "questions")

# --- Inicialização do Modelo de IA ---
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
        
    print(f"[OK] Usando modelo para enriquecimento: {MODEL_ID}")
    model = genai.GenerativeModel(MODEL_ID)

except Exception as e:
    print(f"[ERRO] Falha ao configurar a API do Gemini: {e}")
    sys.exit(1)

def enrich_question(question_data):
    """
    Usa a IA para gerar uma explicação detalhada para uma questão.
    Utiliza cache para economizar API.
    """
    q_id = question_data.get('id', 'unknown')
    print(f"[*] Enriquecendo questao: {q_id}", end="", flush=True)

    # --- Lógica de Cache ---
    # O hash é baseado no enunciado + alternativas para detectar mudanças
    core_content = question_data['stem'] + str(question_data['options']) + str(question_data['answer'])
    cache_key = hashlib.sha256(core_content.encode('utf-8')).hexdigest()
    
    cache_subdir = os.path.join(CACHE_DIR, str(question_data['year']), "enrichment")
    os.makedirs(cache_subdir, exist_ok=True)
    cache_file = os.path.join(cache_subdir, f"{q_id}_{cache_key}.json")

    if os.path.exists(cache_file):
        print(" (CACHE HIT!)", flush=True)
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    print(" (CHAMADA DE API...)", flush=True)

    # --- Prompt de Especialista ---
    prompt = f"""Você é um professor especialista em vestibular (nível Fuvest) e precisa ensinar o aluno.

Objetivo: dado o JSON de uma questão de múltipla escolha (A–E) e a alternativa correta, gere uma explicação EXTREMAMENTE DIDÁTICA, técnica e precisa.

Regras obrigatórias:
1) Não altere enunciado e alternativas.
2) Sempre gere: theory, steps, distractors, finalSummary.
3) Distractors: explique por que CADA alternativa errada está errada (A,B,C,D,E).
4) O aluno sempre verá a explicação após responder; escreva para ser útil mesmo se ele acertou.
5) Não invente dados/fatos. Se faltar informação no enunciado, deixe claro.
6) Output deve ser SOMENTE JSON estrito e válido.

Dados da Questão:
{json.dumps(question_data, ensure_ascii=False, indent=2)}

Resposta Correta: {question_data['answer']['correct']}

Schema de saída esperado:
{{
  "theory": "Breve contexto teórico necessário para resolver a questão.",
  "steps": ["Passo 1 da resolução...", "Passo 2..."],
  "distractors": {{
    "A": "Explicação do erro na A ou confirmação se for a correta...",
    "B": "Explicação do erro na B...",
    "C": "Explicação do erro na C...",
    "D": "Explicação do erro na D...",
    "E": "Explicação do erro na E..."
  }},
  "finalSummary": "Um resumo em uma frase da pegadinha ou do conceito chave."
}}"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        explanation_data = json.loads(response.text)
        
        # Salva no cache
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(explanation_data, f, ensure_ascii=False, indent=2)
            
        return explanation_data

    except Exception as e:
        print(f"\n[ERRO] Falha ao enriquecer questao {q_id}: {e}", flush=True)
        return None

def main():
    parser = argparse.ArgumentParser(description="Enriquecimento de Questoes com IA.")
    parser.add_argument("--year", type=int, required=True, help="Ano da prova a ser enriquecida.")
    parser.add_argument("--limit", type=int, default=0, help="Limite de questoes para processar (0 = todas).")
    args = parser.parse_args()

    input_path = os.path.join(DATA_DIR, f"fuvest-{args.year}.json")
    if not os.path.exists(input_path):
        print(f"[ERRO] Dataset '{input_path}' nao encontrado. Rode o ingest.py primeiro.")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    questions = data.get('questions', [])
    print(f"[*] Iniciando enriquecimento de {len(questions)} questoes de {args.year}...")

    count = 0
    enrichement_performed = 0
    for q in questions:
        # Pula se já estiver enriquecida. 
        if q.get('explanation', {}).get('theory') == "Pendente":
            new_explanation = enrich_question(q)
            if new_explanation:
                q['explanation'] = new_explanation
                enrichement_performed += 1
            
            count += 1
        
        if args.limit > 0 and count >= args.limit:
            print(f"[*] Limite de {args.limit} questoes atingido.")
            break

    # Salva o arquivo atualizado
    if enrichement_performed > 0:
        with open(input_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] FASE 3!")
    print(f"[*] {enrichement_performed} questoes enriquecidas no arquivo: {input_path}")

if __name__ == "__main__":
    main()
