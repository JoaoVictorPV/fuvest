import fitz
import sys

pdf_path = "provas/p21.pdf"

print(f"\n[*] Testando PDF: {pdf_path}")

try:
    doc = fitz.open(pdf_path)
    print(f"[OK] PDF aberto com sucesso!")
    print(f"[OK] Número de páginas: {len(doc)}")
    
    # Testa extração de texto da primeira página
    if len(doc) > 0:
        page = doc.load_page(0)
        text = page.get_text("text")
        
        print(f"\n[*] Teste de extração de texto (primeiros 500 caracteres):")
        print("-" * 60)
        print(text[:500] if text else "(Vazio - PDF pode ser escaneado)")
        print("-" * 60)
        
        # Testa extração de palavras
        words = page.get_text("words")
        print(f"\n[OK] Palavras extraídas da página 1: {len(words) if words else 0}")
        
        if words and len(words) > 0:
            print("[OK] O PDF tem texto extraível - PODE usar método tradicional!")
            print("\n[RECOMENDAÇÃO] Remover forçamento do modo visual para 2021")
        else:
            print("[WARN] PDF parece ser escaneado - necessário modo visual")
    
    doc.close()
    
except Exception as e:
    print(f"[ERRO] Falha ao abrir PDF: {e}")
    sys.exit(1)
