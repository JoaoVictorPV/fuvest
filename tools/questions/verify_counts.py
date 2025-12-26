import json
import os

years = [2023, 2024, 2025, 2026]
for year in years:
    path = f"public/data/questions/fuvest-{year}.json"
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            questions = data.get('questions', [])
            count = len(questions)
            enriched = sum(1 for q in questions if q.get('explanation', {}).get('theory') != 'Pendente')
            print(f"{year}: {count} questions, {enriched} enriched")
    else:
        print(f"{year}: File not found")
