import json
import jsonschema
import sys
import os

# Força stdout em UTF-8 no Windows para evitar UnicodeEncodeError
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def validate_dataset(schema_path, dataset_path):
    """
    Valida um arquivo de dataset JSON contra um schema.
    """
    try:
        # Carrega o schema
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        # Carrega o dataset
        with open(dataset_path, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
            
        # Valida
        jsonschema.validate(instance=dataset, schema=schema)
        
        print(f"[OK] Validação bem-sucedida para: {os.path.basename(dataset_path)}")
        return True
        
    except json.JSONDecodeError as e:
        print(f"[ERRO] JSON inválido em '{os.path.basename(dataset_path)}': {e}")
        return False
    except jsonschema.exceptions.ValidationError as e:
        print(f"[ERRO] Validação de schema falhou em '{os.path.basename(dataset_path)}':")
        print(f"  - Mensagem: {e.message}")
        print(f"  - Caminho no JSON: {list(e.path)}")
        return False
    except FileNotFoundError as e:
        print(f"[ERRO] Arquivo não encontrado - {e.filename}")
        return False
    except Exception as e:
        print(f"[ERRO] Ocorreu um erro inesperado: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python validate.py <caminho_para_o_dataset.json>")
        sys.exit(1)
        
    # O primeiro argumento é o nome do script, então começamos do segundo
    dataset_files = sys.argv[1:]
    
    # O schema está na mesma pasta que o script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    schema_file = os.path.join(script_dir, "schema.json")

    if not os.path.exists(schema_file):
        print(f"❌ Erro Crítico: O arquivo de schema '{schema_file}' não foi encontrado.")
        sys.exit(1)

    validation_passed = True
    for dataset_file in dataset_files:
        if not os.path.exists(dataset_file):
            print(f"⚠️ Aviso: O arquivo de dataset '{dataset_file}' não foi encontrado. Pulando.")
            continue
        
        print(f"--- Validando: {dataset_file} ---")
        if not validate_dataset(schema_file, dataset_file):
            validation_passed = False
            
    if validation_passed:
        print("\n[OK] Todos os arquivos de dataset foram validados com sucesso!")
        sys.exit(0)
    else:
        print("\n[ERRO] Encontrados erros de validação em um ou mais arquivos.")
        sys.exit(1)
