import os
import sys
import json
import hashlib
import argparse
import time
import re
import subprocess
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai


def _is_pid_alive(pid: int) -> bool:
    """Checa se um PID está vivo.

    No Windows usa `tasklist` (sem dependências externas).
    """
    if not isinstance(pid, int) or pid <= 0:
        return False

    if os.name == 'nt':
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}"],
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            if "No tasks are running" in out:
                return False
            return str(pid) in out
        except Exception:
            return False

    # POSIX
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _save_json_atomic(path: str, data: dict):
    """Salva JSON de forma atômica (evita arquivo corrompido se o processo morrer no meio)."""
    tmp_path = path + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _normalize_explanation(exp: dict) -> tuple[dict, bool]:
    """Garante que o objeto `explanation` tem todos os campos exigidos pelo schema.

    Retorna (exp_normalizado, alterou).
    """
    changed = False
    if not isinstance(exp, dict):
        exp = {}
        changed = True

    if 'theory' not in exp:
        exp['theory'] = ""
        changed = True
    if 'steps' not in exp or not isinstance(exp.get('steps'), list):
        exp['steps'] = []
        changed = True
    if 'distractors' not in exp or not isinstance(exp.get('distractors'), dict):
        exp['distractors'] = {}
        changed = True
    for k in ['A', 'B', 'C', 'D', 'E']:
        if k not in exp['distractors']:
            exp['distractors'][k] = ""
            changed = True
    if 'finalSummary' not in exp:
        exp['finalSummary'] = ""
        changed = True

    return exp, changed


def _looks_like_incomplete_explanation(exp: dict) -> bool:
    """Define se a explicação está incompleta (e deve ser enriquecida/reparada)."""
    if not isinstance(exp, dict):
        return True
    required = ['theory', 'steps', 'distractors', 'finalSummary']
    for k in required:
        if k not in exp:
            return True
    if not isinstance(exp.get('steps'), list):
        return True
    if not isinstance(exp.get('distractors'), dict):
        return True
    for k in ['A', 'B', 'C', 'D', 'E']:
        if k not in exp.get('distractors', {}):
            return True
    return False


def _try_parse_json_strict_or_repair(raw: str) -> dict:
    """Tenta fazer parse de JSON; se falhar, aplica um 'repair' simples.

    Observação: não é um parser completo de JSON5, mas resolve os erros mais comuns
    do modelo (vírgula sobrando antes de } ou ]).
    """
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Resposta vazia do modelo")

    # 1) tentativas diretas
    try:
        return json.loads(raw)
    except Exception:
        pass

    # 2) isola o primeiro objeto entre { ... }
    start = raw.find('{')
    end = raw.rfind('}')
    if start >= 0 and end > start:
        candidate = raw[start:end+1]
    else:
        candidate = raw

    # 3) remove vírgulas “sobrando” antes de fechar objeto/array
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)

    return json.loads(candidate)

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

    # Preferência de modelos (texto) com maior quota:
    # 1) gemini-2.5-flash (recomendado)
    # 2) gemini-2.0-flash
    # 3) gemini-1.5-flash
    # Evitar modelos "image-generation" aqui (não precisamos gerar imagem para enriquecer texto).
    preferred = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]

    models = [m for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]

    for pref in preferred:
        for m in models:
            if pref in m.name and "lite" not in m.name and "image" not in m.name:
                MODEL_ID = m.name
                model_found = True
                break
        if model_found:
            break
    
    if not model_found:
        print("[ERRO] Modelo compativel nao encontrado na sua conta.")
        sys.exit(1)
        
    print(f"[OK] Usando modelo para enriquecimento: {MODEL_ID}")
    model = genai.GenerativeModel(MODEL_ID)

except Exception as e:
    print(f"[ERRO] Falha ao configurar a API do Gemini: {e}")
    sys.exit(1)


# --- Rate limit / retry helpers ---
_LAST_CALL_TS = 0.0

def _sleep_for_rate_limit(min_interval_sec: float):
    global _LAST_CALL_TS
    now = time.time()
    wait = (_LAST_CALL_TS + min_interval_sec) - now
    if wait > 0:
        time.sleep(wait)
    _LAST_CALL_TS = time.time()


def _parse_retry_delay_seconds(err_text: str) -> int:
    # tenta extrair "retry_delay { seconds: 57 }" da mensagem do Gemini
    m = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", err_text)
    if not m:
        return 0
    try:
        return int(m.group(1))
    except Exception:
        return 0

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
7) NUNCA retorne campos faltando. Mesmo que esteja inseguro, retorne strings vazias para theory/finalSummary e lista vazia para steps.

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

    # Por padrão, algumas contas têm limite baixo (ex.: 10 req/min/modelo).
    # Então, além do cache, aplicamos:
    # - throttle (min 7s entre chamadas) e
    # - retry com espera (lendo retry_delay quando disponível).
    min_interval_sec = 7.0
    max_retries = 6

    for attempt in range(1, max_retries + 1):
        try:
            _sleep_for_rate_limit(min_interval_sec)
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )

            # Alguns modelos/contas ocasionalmente retornam JSON com ruído.
            # Tentamos parsear de forma tolerante.
            raw = (response.text or "").strip()
            explanation_data = _try_parse_json_strict_or_repair(raw)

            # Garante que o schema sempre vai passar
            explanation_data, _ = _normalize_explanation(explanation_data)

            # Salva no cache
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(explanation_data, f, ensure_ascii=False, indent=2)

            return explanation_data

        except Exception as e:
            msg = str(e)
            retry_delay = _parse_retry_delay_seconds(msg)

            if "429" in msg:
                # respeita sugestão do backend quando existir
                wait = (retry_delay if retry_delay > 0 else 60)
                print(f"\n[WARN] Rate limit (429) em {q_id}. Aguardando {wait}s e tentando novamente ({attempt}/{max_retries})...", flush=True)
                time.sleep(wait + 1)
                continue

            # Outros erros: backoff simples
            wait = min(60, 2 ** attempt)
            print(f"\n[WARN] Erro ao enriquecer {q_id}: {msg}. Tentando novamente em {wait}s ({attempt}/{max_retries})...", flush=True)
            time.sleep(wait)

    print(f"\n[ERRO] Falha definitiva ao enriquecer questao {q_id} apos {max_retries} tentativas.", flush=True)
    return None


def _find_pending_questions(questions: list[dict]) -> list[dict]:
    pending = []
    for q in questions:
        exp = q.get('explanation', {})
        if not isinstance(exp, dict) or exp.get('theory') == 'Pendente' or _looks_like_incomplete_explanation(exp):
            pending.append(q)
    return pending

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

    # Para evitar percorrer tudo e gerar locks/restarts a cada rodada,
    # identificamos apenas as pendentes e processamos somente elas.
    pending_questions = _find_pending_questions(questions)
    print(f"[*] Iniciando enriquecimento de {len(pending_questions)}/{len(questions)} questoes pendentes de {args.year}...")

    # lock por ano para evitar dois enrich rodando ao mesmo tempo (e duplicando custos)
    lock_dir = os.path.join(CACHE_DIR, "_locks")
    os.makedirs(lock_dir, exist_ok=True)
    lock_path = os.path.join(lock_dir, f"enrich_{args.year}.lock")

    # Lock robusto:
    # - Criação atômica (O_EXCL)
    # - Se já existir, tenta ler PID do lock e verificar se processo ainda está vivo
    # - Se PID não estiver vivo (ou lock estiver muito antigo), remove lock automaticamente
    stale_lock_seconds = 60 * 60  # 60 min (conservador; evita remover lock legítimo em execuções longas)

    def _read_lock_pid(path: str) -> int:
        try:
            txt = open(path, 'r', encoding='utf-8', errors='ignore').read().strip()
            # formato esperado: "pid=12345;ts=2025-..."
            m = re.search(r"pid\s*=\s*(\d+)", txt)
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return 0

    if os.path.exists(lock_path):
        try:
            pid = _read_lock_pid(lock_path)
            age = time.time() - os.path.getmtime(lock_path)
            pid_alive = _is_pid_alive(pid) if pid else False

            if (pid and not pid_alive) or (age > stale_lock_seconds):
                print(f"[LOCK] Lock stale detectado (pid={pid}, alive={pid_alive}, age={int(age)}s). Removendo: {lock_path}")
                os.remove(lock_path)
        except Exception:
            pass

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(f"pid={os.getpid()};ts={datetime.now().isoformat()}")
    except FileExistsError:
        pid = _read_lock_pid(lock_path)
        print(f"[LOCK] Já existe um enriquecimento em andamento para {args.year} (lock: {lock_path}, pid={pid}).\n"
              "Se você tem certeza que não há outro processo rodando, apague o lock e rode novamente.")
        sys.exit(2)

    # Para evitar perder progresso em caso de interrupção (ou rate limit prolongado),
    # salvamos incrementalmente a cada questão enriquecida.
    save_every = 1

    try:
        count = 0
        enrichement_performed = 0
        for q in pending_questions:
            # 1) Normaliza explicação existente (sem gastar API)
            exp_norm, changed = _normalize_explanation(q.get('explanation'))
            q['explanation'] = exp_norm

            if changed:
                enrichement_performed += 1
                if save_every > 0 and (enrichement_performed % save_every == 0):
                    _save_json_atomic(input_path, data)

            # 2) Enriquecimento via IA (apenas pendentes/incompletas)
            new_explanation = enrich_question(q)
            if new_explanation:
                q['explanation'] = new_explanation
                enrichement_performed += 1
                if save_every > 0 and (enrichement_performed % save_every == 0):
                    _save_json_atomic(input_path, data)

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
    finally:
        try:
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except Exception:
            pass

if __name__ == "__main__":
    main()
