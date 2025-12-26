"""
Módulo OCR local para fallback quando o PDF tem encoding ruim.
Usa Tesseract (pytesseract) com idioma português.
"""
import os
import re
from PIL import Image

# Tenta importar pytesseract; se falhar, define flag
try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Caminhos comuns do Tesseract no Windows
TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\joaov\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
]

def _find_tesseract():
    """Encontra o executável do Tesseract."""
    for path in TESSERACT_PATHS:
        if os.path.exists(path):
            return path
    # Tenta encontrar via PATH
    import shutil
    found = shutil.which("tesseract")
    return found

def init_ocr():
    """Inicializa o OCR. Retorna True se disponível."""
    global OCR_AVAILABLE
    if not OCR_AVAILABLE:
        return False
    
    tesseract_path = _find_tesseract()
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        return True
    return False

def ocr_image(image_path_or_pil, lang="por"):
    """
    Extrai texto de uma imagem usando OCR local.
    
    Args:
        image_path_or_pil: Caminho para imagem ou objeto PIL.Image
        lang: Idioma do Tesseract (por = português)
    
    Returns:
        Texto extraído ou string vazia se falhar.
    """
    if not OCR_AVAILABLE:
        return ""
    
    try:
        if isinstance(image_path_or_pil, str):
            img = Image.open(image_path_or_pil)
        else:
            img = image_path_or_pil
        
        # Converte para RGB se necessário
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        text = pytesseract.image_to_string(img, lang=lang)
        return text.strip()
    except Exception as e:
        print(f"[OCR] Erro: {e}")
        return ""

def parse_alternatives_from_ocr(text):
    """
    Tenta extrair alternativas A-E do texto OCR.
    
    Returns:
        Dict com {A: texto, B: texto, ...} ou None se não encontrar.
    """
    if not text:
        return None
    
    # Padrões para alternativas
    patterns = [
        r'\(([A-E])\)\s*(.+?)(?=\([A-E]\)|$)',  # (A) texto
        r'([A-E])\)\s*(.+?)(?=[A-E]\)|$)',       # A) texto
        r'^([A-E])\s*[.\-–:]\s*(.+?)(?=^[A-E]|$)',  # A. texto ou A - texto
    ]
    
    options = {}
    for pattern in patterns:
        matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
        if matches and len(matches) >= 3:  # Pelo menos 3 alternativas
            for key, value in matches:
                key = key.upper().strip()
                if key in 'ABCDE':
                    options[key] = value.strip()[:500]  # Limita tamanho
            if len(options) >= 3:
                break
    
    # Garante todas as chaves
    for k in 'ABCDE':
        if k not in options:
            options[k] = "(Veja a imagem da questão)"
    
    return options if any(v != "(Veja a imagem da questão)" for v in options.values()) else None

def extract_stem_from_ocr(text):
    """
    Extrai o enunciado (stem) do texto OCR.
    Remove número da questão e alternativas.
    """
    if not text:
        return ""
    
    # Remove número da questão no início
    text = re.sub(r'^\s*\d{1,2}\s*[.\)]\s*', '', text)
    
    # Encontra onde começam as alternativas
    alt_match = re.search(r'\n\s*\(?[A-E]\)?\s*[.\-–:]?\s*\w', text)
    if alt_match:
        text = text[:alt_match.start()]
    
    return text.strip()

# Inicializa automaticamente
OCR_READY = init_ocr() if OCR_AVAILABLE else False
