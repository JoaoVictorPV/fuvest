import argparse
import json
from pathlib import Path
from PIL import Image


def white_ratio(img: Image.Image, threshold: int = 245) -> float:
    """Percentual de pixels quase-brancos.

    threshold: 0..255 (quanto maior, mais permissivo para considerar branco)
    """
    gray = img.convert("L")
    data = gray.getdata()
    total = len(data)
    if total == 0:
        return 1.0
    white = sum(1 for p in data if p >= threshold)
    return white / total


def content_bbox_ratio(img: Image.Image, dark_threshold: int = 245) -> float:
    """Quanta área do recorte está ocupada por 'conteúdo' (não branco).

    Retorna: bbox_area / total_area
    Quanto menor, mais "vazio"/margem/branco excessivo.
    """
    gray = img.convert("L")
    bw = gray.point(lambda p: 255 if p < dark_threshold else 0)
    bbox = bw.getbbox()
    if not bbox:
        return 0.0
    x0, y0, x1, y1 = bbox
    bbox_area = max(1, (x1 - x0) * (y1 - y0))
    total_area = max(1, img.width * img.height)
    return bbox_area / total_area


def audit_year(year: int, dataset_path: Path, out_dir: Path, white_threshold: float, min_area: int):
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    questions = dataset.get("questions") or []

    # dataset_path = <repo>/public/data/questions/fuvest-YYYY.json
    # public_dir = dataset_path.parents[2] -> <repo>/public
    public_dir = dataset_path.parents[2]

    rows = []
    for q in questions:
        qnum = int(q.get("number") or 0)
        asset = ((q.get("assets") or {}).get("questionImage") or "").lstrip("/")
        if not asset:
            continue
        img_path = public_dir / asset  # public/<asset>
        if not img_path.exists():
            rows.append({
                "year": year,
                "number": qnum,
                "missing": True,
            })
            continue

        with Image.open(img_path) as img:
            w, h = img.size
            area = w * h
            wr = white_ratio(img)
            cr = content_bbox_ratio(img)

        rows.append({
            "year": year,
            "number": qnum,
            "path": str(img_path).replace("\\", "/"),
            "width": w,
            "height": h,
            "area": area,
            "white_ratio": round(wr, 4),
            "content_ratio": round(cr, 4),
            "flag_white": wr >= white_threshold,
            "flag_small": area <= min_area,
            "missing": False,
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / f"audit_crops_{year}.json"
    out_json.write_text(json.dumps({
        "year": year,
        "dataset": str(dataset_path).replace("\\", "/"),
        "white_threshold": white_threshold,
        "min_area": min_area,
        "total": len(rows),
        "flagged": sum(1 for r in rows if r.get("flag_white") or r.get("flag_small") or r.get("missing")),
        "rows": sorted(rows, key=lambda r: (r.get("flag_white") is False, r.get("flag_small") is False, r.get("missing") is False, r.get("number") or 0)),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # também gera uma versão CSV simples para abrir no Excel
    out_csv = out_dir / f"audit_crops_{year}.csv"
    cols = ["year","number","width","height","area","white_ratio","content_ratio","flag_white","flag_small","missing","path"]
    lines = [";".join(cols)]
    for r in rows:
        line = []
        for c in cols:
            v = r.get(c, "")
            line.append(str(v))
        lines.append(";".join(line))
    out_csv.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Relatório gerado: {out_json}")
    print(f"[OK] CSV gerado: {out_csv}")


def main():
    parser = argparse.ArgumentParser(description="Audita recortes de questões (área branca / tamanho).")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--dataset", type=str, default=None, help="Caminho do dataset (default: public/data/questions/fuvest-<year>.json)")
    parser.add_argument("--out", type=str, default="tools/questions/out", help="Diretório de saída")
    parser.add_argument("--white-threshold", type=float, default=0.72, help="Flag se white_ratio >= este valor")
    parser.add_argument("--min-area", type=int, default=220_000, help="Flag se area <= este valor")

    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]  # repo root
    dataset_path = Path(args.dataset) if args.dataset else (root / "public" / "data" / "questions" / f"fuvest-{args.year}.json")
    out_dir = Path(args.out)
    audit_year(args.year, dataset_path, out_dir, args.white_threshold, args.min_area)


if __name__ == "__main__":
    main()
