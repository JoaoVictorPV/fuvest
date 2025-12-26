"""tools/questions/ocr.py

Módulo OCR local para fallback quando o PDF tem encoding ruim.
Usa Tesseract (pytesseract).

Objetivo:
- suportar alternativas A-E e a-e (muito comum nas provas)
- preferir OCR em português, mas permitir "por+eng" quando disponível
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


def _try_set_tessdata_prefix(tesseract_cmd: str | None):
    """Tenta configurar TESSDATA_PREFIX automaticamente no Windows.

    Observação: o pytesseract precisa do executável do tesseract + pasta tessdata.
    Em instalações padrão (Windows):
      C:\\Program Files\\Tesseract-OCR\\tesseract.exe
      C:\\Program Files\\Tesseract-OCR\\tessdata
    """
    if not tesseract_cmd:
        return
    try:
        base = os.path.dirname(tesseract_cmd)
        tessdata_dir = os.path.join(base, "tessdata")
        if os.path.isdir(tessdata_dir):
            # A mensagem de erro do Tesseract geralmente pede apontar para a pasta "tessdata".
            # Então priorizamos o tessdata_dir.
            os.environ.setdefault("TESSDATA_PREFIX", tessdata_dir)
    except Exception:
        return

def init_ocr():
    """Inicializa o OCR. Retorna True se disponível."""
    global OCR_AVAILABLE
    if not OCR_AVAILABLE:
        return False
    
    tesseract_path = _find_tesseract()
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        _try_set_tessdata_prefix(tesseract_path)
        return True
    return False


def best_ocr_lang(preferred: str = "por") -> str:
    """Retorna o melhor idioma disponível no Tesseract.

    Preferência:
    1) por+eng (quando ambos estiverem instalados)
    2) por
    3) eng
    """
    if not OCR_AVAILABLE:
        return "eng"
    try:
        langs = set(pytesseract.get_languages(config=""))
        if "por" in langs and "eng" in langs:
            return "por+eng"
        if preferred in langs:
            return preferred
        if "por" in langs:
            return "por"
        if "eng" in langs:
            return "eng"
    except Exception:
        pass
    return "eng"

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
        
        # Alguns ambientes não têm o idioma 'por' instalado.
        # Nesse caso, usamos automaticamente o melhor idioma disponível.
        lang = best_ocr_lang(lang)
        text = pytesseract.image_to_string(img, lang=lang)
        return (text or "").strip()
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
    
    # Padrões para alternativas (A-E e a-e)
    patterns = [
        r'\(([A-Ea-e])\)\s*(.+?)(?=\([A-Ea-e]\)|$)',  # (a) texto
        r'([A-Ea-e])\)\s*(.+?)(?=[A-Ea-e]\)|$)',       # a) texto
        r'^([A-Ea-e])\s*[.\-–:]\s*(.+?)(?=^[A-Ea-e]|$)',  # a. texto ou a - texto
    ]
    
    options = {}
    for pattern in patterns:
        matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
        if matches and len(matches) >= 3:  # Pelo menos 3 alternativas
            for key, value in matches:
                key = (key or "").upper().strip()
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
    alt_match = re.search(r'\n\s*\(?[A-Ea-e]\)?\s*[.\-–:\)]?\s*\w', text)
    if alt_match:
        text = text[:alt_match.start()]
    
    return text.strip()

# Inicializa automaticamente
OCR_READY = init_ocr() if OCR_AVAILABLE else False
