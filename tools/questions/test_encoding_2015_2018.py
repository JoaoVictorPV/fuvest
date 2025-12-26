"""
Testa encoding dos PDFs de 2015-2018 para verificar viabilidade de processamento.
"""
import fitz
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
PROVAS_DIR = PROJECT_ROOT / "provas"

years_to_test = [2015, 2016, 2017, 2018]

print("=" * 60)
print("TESTE DE ENCODING DE PDFs 2015-2018")
print("=" * 60)

results = {}

for year in years_to_test:
    pdf_path = PROVAS_DIR / f"p{str(year)[2:]}.pdf"
    
    if not pdf_path.exists():
        print(f"\n[ERRO] {year}: Arquivo não encontrado")
        results[year] = "NOT_FOUND"
        continue
    
    try:
        doc = fitz.open(str(pdf_path))
        
        # Testa extração de texto das primeiras 3 páginas
        sample_text = ""
        for page_num in range(min(3, len(doc))):
            page = doc[page_num]
            text = page.get_text()
            sample_text += text
        
        # Verifica qualidade do encoding
        total_chars = len(sample_text)
        readable_chars = sum(1 for c in sample_text if c.isprintable() or c.isspace())
        special_chars = sum(1 for c in sample_text if ord(c) > 127 and c not in 'áéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ')
        
        quality_score = (readable_chars / total_chars * 100) if total_chars > 0 else 0
        corruption_rate = (special_chars / total_chars * 100) if total_chars > 0 else 0
        
        # Procura por padrões típicos de questões
        has_questions = "questão" in sample_text.lower() or "questao" in sample_text.lower()
        has_alternatives = any(f"({opt})" in sample_text or f"{opt})" in sample_text for opt in ['A', 'B', 'C', 'D', 'E'])
        
        print(f"\n{'='*60}")
        print(f"ANO: {year}")
        print(f"{'='*60}")
        print(f"Total de páginas: {len(doc)}")
        print(f"Caracteres na amostra: {total_chars}")
        print(f"Taxa de legibilidade: {quality_score:.1f}%")
        print(f"Taxa de corrupção: {corruption_rate:.1f}%")
        print(f"Detecta 'questão': {'✓' if has_questions else '✗'}")
        print(f"Detecta alternativas: {'✓' if has_alternatives else '✗'}")
        
        # Mostra amostra
        print(f"\n[AMOSTRA - primeiros 300 chars]")
        print("-" * 60)
        print(sample_text[:300].replace('\n', ' '))
        print("-" * 60)
        
        # Critério de aprovação: >85% legibilidade E <15% corrupção
        if quality_score > 85 and corruption_rate < 15:
            verdict = "✅ EXCELENTE - Processamento recomendado"
            results[year] = "EXCELLENT"
        elif quality_score > 70 and corruption_rate < 30:
            verdict = "⚠️ BOM - Processamento possível com atenção"
            results[year] = "GOOD"
        else:
            verdict = "❌ RUIM - Encoding problemático, não recomendado"
            results[year] = "POOR"
        
        print(f"\n{verdict}")
        
        doc.close()
        
    except Exception as e:
        print(f"\n[ERRO] {year}: {e}")
        results[year] = "ERROR"

print(f"\n\n{'='*60}")
print("RESUMO FINAL")
print(f"{'='*60}")

excellent = [y for y, r in results.items() if r == "EXCELLENT"]
good = [y for y, r in results.items() if r == "GOOD"]
poor = [y for y, r in results.items() if r == "POOR"]
errors = [y for y, r in results.items() if r in ["ERROR", "NOT_FOUND"]]

print(f"\n✅ EXCELENTES (processar): {excellent if excellent else 'Nenhum'}")
print(f"⚠️ BONS (processar com atenção): {good if good else 'Nenhum'}")
print(f"❌ RUINS (NÃO processar): {poor if poor else 'Nenhum'}")
if errors:
    print(f"🔴 ERROS: {errors}")

print(f"\n{'='*60}")
print("RECOMENDAÇÃO:")
if excellent or good:
    processable = excellent + good
    print(f"Processar os anos: {processable}")
    print(f"\nComando: python tools/questions/ingest.py --year {' '.join(map(str, processable))}")
else:
    print("Nenhum ano recomendado para processamento.")
print(f"{'='*60}")
