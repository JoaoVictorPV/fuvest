import fitz
import sys

def debug_pdf(path):
    doc = fitz.open(path)
    for i in range(min(3, len(doc))):
        page = doc.load_page(i)
        print(f"--- PAGE {i+1} ---")
        words = page.get_text("words")
        # Print words that look like '1' or '01'
        for w in words:
            if w[4].strip() in ['1', '01', '1.', '01.', '1)', '01)']:
                print(f"Candidate marker: '{w[4]}' at y={w[1]:.1f}")
        print(page.get_text("text")[:500])

if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug_pdf(sys.argv[1])
