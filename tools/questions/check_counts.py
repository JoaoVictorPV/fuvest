import json
import os

years = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
base = "public/data/questions"

print("\n=== RESUMO DO PROCESSAMENTO ===\n")

for year in years:
    path = f"{base}/fuvest-{year}.json"
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                questions = data.get('questions', [])
                count = len(questions)
                
                # Verifica se tem gabarito
                with_answer = sum(1 for q in questions if q.get('answer', {}).get('correct'))
                
                print(f"[OK] {year}: {count}/90 questoes | {with_answer} com gabarito")
        except Exception as e:
            print(f"[ERRO] {year}: Erro ao ler - {e}")
    else:
        print(f"[...] {year}: Arquivo ainda nao existe")

print("\n")
