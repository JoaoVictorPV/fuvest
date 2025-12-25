import shutil
import os
import argparse

# Configuração
SOURCE_ROOT = os.path.join("tools", "questions", "out")
DEST_ROOT = os.path.join("public", "assets", "pages")

def copy_pages(year):
    src_dir = os.path.join(SOURCE_ROOT, str(year), "pages")
    dest_dir = os.path.join(DEST_ROOT, str(year))
    
    if not os.path.exists(src_dir):
        print(f"[WARN] Origem não encontrada: {src_dir}")
        return

    os.makedirs(dest_dir, exist_ok=True)
    
    files = os.listdir(src_dir)
    count = 0
    for f in files:
        if f.endswith(".png"):
            shutil.copy2(os.path.join(src_dir, f), os.path.join(dest_dir, f))
            count += 1
            
    print(f"[OK] {count} páginas de {year} copiadas para {dest_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, help="Ano específico (opcional)")
    args = parser.parse_args()
    
    years = [args.year] if args.year else [2019, 2021, 2022]
    
    for y in years:
        copy_pages(y)
