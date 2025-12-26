"""
QA Gate - Validação obrigatória antes de publicar um ano.
Verifica: 90 questões, assets, páginas, schema, qualidade do texto.
"""
import os
import sys
import json
import argparse
import re
import unicodedata

if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, "public", "data", "questions")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "public", "assets", "questions")
PAGES_DIR = os.path.join(PROJECT_ROOT, "public", "assets", "pages")


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    # remove acentos e normaliza unicode
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s)
    return s


def _is_placeholder(text: str) -> bool:
    t = _norm(text)
    if not t:
        return True
    # cobre variações: "questao" / "questão" / "quest�o" (mesmo se vier com encoding ruim)
    return "veja a imagem da quest" in t

def check_year(year):
    """Executa todas as verificações para um ano."""
    results = {
        "year": year,
        "passed": True,
        "checks": {},
        "warnings": [],
        "errors": []
    }
    
    json_path = os.path.join(DATA_DIR, f"fuvest-{year}.json")
    
    # 1. Arquivo existe
    if not os.path.exists(json_path):
        results["errors"].append(f"JSON nao encontrado: {json_path}")
        results["passed"] = False
        results["checks"]["json_exists"] = False
        return results
    results["checks"]["json_exists"] = True
    
    # 2. JSON valido
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        results["checks"]["json_valid"] = True
    except Exception as e:
        results["errors"].append(f"JSON invalido: {e}")
        results["passed"] = False
        results["checks"]["json_valid"] = False
        return results
    
    questions = data.get("questions", [])
    
    # 3. Contagem de questoes
    q_count = len(questions)
    results["checks"]["question_count"] = q_count
    if q_count != 90:
        results["errors"].append(f"Esperado 90 questoes, encontrado {q_count}")
        results["passed"] = False
    
    # 4. Numeros 1-90 sem buracos
    numbers = sorted([q.get("number", 0) for q in questions])
    expected = list(range(1, 91))
    missing_nums = set(expected) - set(numbers)
    if missing_nums:
        results["errors"].append(f"Questoes faltando: {sorted(missing_nums)}")
        results["passed"] = False
    results["checks"]["missing_numbers"] = list(missing_nums)
    
    # 5. Assets de questoes
    missing_assets = []
    for q in questions:
        qnum = q.get("number", 0)
        asset_path = q.get("assets", {}).get("questionImage", "")
        if asset_path:
            full_path = os.path.join(PROJECT_ROOT, "public", asset_path.lstrip("/"))
            if not os.path.exists(full_path):
                missing_assets.append(qnum)
        else:
            missing_assets.append(qnum)
    results["checks"]["missing_assets"] = missing_assets
    if missing_assets:
        results["warnings"].append(f"{len(missing_assets)} questoes sem asset: {missing_assets[:10]}...")
    
    # 6. Paginas
    pages_dir = os.path.join(PAGES_DIR, str(year))
    if os.path.exists(pages_dir):
        page_files = [f for f in os.listdir(pages_dir) if f.endswith('.png')]
        results["checks"]["page_count"] = len(page_files)
    else:
        results["checks"]["page_count"] = 0
        results["warnings"].append(f"Diretorio de paginas nao encontrado: {pages_dir}")
    
    # 7. Qualidade do texto
    stems_placeholder = 0
    options_placeholder = 0
    total_options = 0
    
    for q in questions:
        stem = q.get("stem", "")
        if _is_placeholder(stem) or len((stem or "").strip()) < 20:
            stems_placeholder += 1
        
        for opt in q.get("options", []):
            total_options += 1
            if _is_placeholder(opt.get("text", "")):
                options_placeholder += 1
    
    stem_pct = (stems_placeholder / max(1, len(questions))) * 100
    opt_pct = (options_placeholder / max(1, total_options)) * 100
    
    results["checks"]["stems_placeholder_pct"] = round(stem_pct, 1)
    results["checks"]["options_placeholder_pct"] = round(opt_pct, 1)
    
    if stem_pct > 50:
        results["warnings"].append(f"{stem_pct:.1f}% dos enunciados sao placeholders")
    if opt_pct > 50:
        results["warnings"].append(f"{opt_pct:.1f}% das alternativas sao placeholders")

    # 7b. BBoxes suspeitas
    small_bbox = []
    for q in questions:
        bbox = q.get("bbox") or {}
        h = int(bbox.get("h") or 0)
        if h > 0 and h < 300:
            small_bbox.append(q.get("number"))
    results["checks"]["small_bboxes"] = small_bbox
    if len(small_bbox) >= 5:
        results["warnings"].append(f"{len(small_bbox)} bboxes com altura suspeita (<300px) — possivel recorte curto")
    
    # 8. Enrichment
    enriched = 0
    for q in questions:
        exp = q.get("explanation", {})
        if isinstance(exp, dict) and exp.get("theory") and exp.get("theory") != "Pendente":
            enriched += 1
    
    enrich_pct = (enriched / max(1, len(questions))) * 100
    results["checks"]["enriched_pct"] = round(enrich_pct, 1)
    if enrich_pct < 100:
        results["warnings"].append(f"Apenas {enrich_pct:.1f}% das questoes enriquecidas")
    
    return results

def print_report(results):
    """Imprime relatorio formatado."""
    year = results["year"]
    passed = results["passed"]
    
    status = "[OK]" if passed else "[FALHOU]"
    print(f"\n{'='*60}")
    print(f"QA GATE - FUVEST {year} {status}")
    print(f"{'='*60}")
    
    checks = results["checks"]
    print(f"\nVerificacoes:")
    print(f"  - JSON existe: {checks.get('json_exists', False)}")
    print(f"  - JSON valido: {checks.get('json_valid', False)}")
    print(f"  - Questoes: {checks.get('question_count', 0)}/90")
    print(f"  - Faltando: {checks.get('missing_numbers', [])}")
    print(f"  - Assets faltando: {len(checks.get('missing_assets', []))}")
    print(f"  - Paginas: {checks.get('page_count', 0)}")
    print(f"  - Enunciados placeholder: {checks.get('stems_placeholder_pct', 0)}%")
    print(f"  - Alternativas placeholder: {checks.get('options_placeholder_pct', 0)}%")
    print(f"  - BBoxes pequenas: {len(checks.get('small_bboxes', []))}")
    print(f"  - Enrichment: {checks.get('enriched_pct', 0)}%")
    
    if results["errors"]:
        print(f"\n[ERROS]:")
        for e in results["errors"]:
            print(f"  - {e}")
    
    if results["warnings"]:
        print(f"\n[AVISOS]:")
        for w in results["warnings"]:
            print(f"  - {w}")
    
    print(f"\n{'='*60}")
    return passed

def main():
    parser = argparse.ArgumentParser(description="QA Gate - Validacao de anos")
    parser.add_argument("--year", type=int, help="Ano especifico")
    parser.add_argument("--all", action="store_true", help="Todos os anos disponiveis")
    parser.add_argument("--json", action="store_true", help="Saida em JSON")
    args = parser.parse_args()
    
    if args.year:
        years = [args.year]
    elif args.all:
        years = []
        for f in os.listdir(DATA_DIR):
            if f.startswith("fuvest-") and f.endswith(".json"):
                try:
                    y = int(f.replace("fuvest-", "").replace(".json", ""))
                    years.append(y)
                except:
                    pass
        years.sort()
    else:
        print("Uso: python qa_gate.py --year YYYY ou --all")
        sys.exit(1)
    
    all_results = []
    all_passed = True
    
    for year in years:
        results = check_year(year)
        all_results.append(results)
        if not results["passed"]:
            all_passed = False
        if not args.json:
            print_report(results)
    
    if args.json:
        print(json.dumps(all_results, ensure_ascii=False, indent=2))
    
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
