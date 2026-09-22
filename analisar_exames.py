#!/usr/bin/env python3
"""Catalogador local de exames em PDF.

Extrai texto, datas e resultados simples sem enviar dados para servicos externos.
Nao realiza diagnostico medico.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import tempfile
import unicodedata
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader


DATE_RE = re.compile(r"\b([0-3]?\d/[01]?\d/(?:19|20)\d{2})\b")
RESULT_RE = re.compile(
    r"(?:Resultado|Resultado\s*obtido)\s*:\s*"
    r"(?P<value>(?:inferior|superior)\s+a\s+)?(?P<number>-?\d+(?:[.,]\d+)?)"
    r"\s*(?P<unit>[%A-Za-zµμ/³²0-9.]+(?:\s+em\s+\d+\s+min)?)?",
    re.IGNORECASE,
)
REF_RANGE_RE = re.compile(
    r"(?P<low>-?\d+(?:[.,]\d+)?)\s*(?:a|ate|à|-)\s*"
    r"(?P<high>-?\d+(?:[.,]\d+)?)\s*(?P<unit>[%A-Za-zµμ/³²0-9.]+)?",
    re.IGNORECASE,
)
REF_UPPER_RE = re.compile(
    r"(?:inferior|menor)\s+(?:ou\s+igual\s+)?a\s+(?P<high>\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
REF_LOWER_RE = re.compile(
    r"(?:superior|maior)\s+(?:ou\s+igual\s+)?a\s+(?P<low>\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)


@dataclass
class ExamFile:
    arquivo: str
    data: str | None
    tipo: str
    paginas: int
    sha256: str
    texto_extraido: bool


@dataclass
class LabResult:
    arquivo: str
    data: str | None
    exame: str
    valor_texto: str
    valor_numerico: float | None
    unidade: str
    referencia: str
    classificacao: str


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return "".join(c for c in value if not unicodedata.combining(c)).lower()


def parse_number(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_text(path: Path) -> tuple[str, int]:
    reader = PdfReader(str(path), strict=False)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\f\n".join(pages), len(reader.pages)


def first_date(text: str, filename: str) -> str | None:
    matches = DATE_RE.findall(text[:12000])
    if matches:
        try:
            return datetime.strptime(matches[0], "%d/%m/%Y").date().isoformat()
        except ValueError:
            pass
    name_match = re.search(r"((?:19|20)\d{2})[-_](\d{2})[-_](\d{2})", filename)
    return "-".join(name_match.groups()) if name_match else None


def classify_file(filename: str, text: str) -> str:
    normalized_name = normalize(filename)
    if "anatomopat" in normalized_name:
        return "anatomopatologico"
    if "laboratorial" in normalized_name:
        return "laboratorial"
    source = normalize(filename + "\n" + text[:4000])
    if any(term in source for term in ("ressonancia", "tomografia", "ultrasson", "radiografia", " raio x", "rx ")):
        return "imagem"
    return "laboratorial"


def probable_heading(lines: list[str], result_index: int) -> str:
    ignored = ("material", "metodo", "coleta", "liberacao", "resultado", "valor de referencia")
    for i in range(result_index - 1, max(-1, result_index - 14), -1):
        candidate = " ".join(lines[i].split()).strip(" _:-")
        if not candidate or len(candidate) > 100:
            continue
        lowered = normalize(candidate)
        if any(word in lowered for word in ignored):
            continue
        letters = [c for c in candidate if c.isalpha()]
        if letters and sum(c.isupper() for c in letters) / len(letters) >= 0.72:
            return candidate
    return "Exame nao identificado"


def reference_near(lines: list[str], index: int) -> str:
    window = " ".join(" ".join(x.split()) for x in lines[index + 1 : index + 12])
    marker = normalize(window).find("valor de referencia")
    if marker >= 0:
        window = window[marker:]
    return window[:350].strip()


def classification(value: float | None, reference: str) -> str:
    if value is None or not reference:
        return "nao determinado"
    normalized = normalize(reference)
    upper = REF_UPPER_RE.search(normalized)
    if upper:
        high = parse_number(upper.group("high"))
        return "acima" if high is not None and value > high else "dentro"
    lower = REF_LOWER_RE.search(normalized)
    if lower:
        low = parse_number(lower.group("low"))
        return "abaixo" if low is not None and value < low else "dentro"
    range_match = REF_RANGE_RE.search(normalized)
    if range_match:
        low = parse_number(range_match.group("low"))
        high = parse_number(range_match.group("high"))
        if low is not None and value < low:
            return "abaixo"
        if high is not None and value > high:
            return "acima"
        return "dentro"
    return "nao determinado"


def extract_results(path: Path, text: str, date: str | None) -> list[LabResult]:
    lines = text.splitlines()
    results: list[LabResult] = []
    for index, line in enumerate(lines):
        # Alguns laboratorios colocam "Resultado:" e o valor em linhas separadas.
        segment = " ".join(" ".join(x.split()) for x in lines[index : index + 3])
        match = RESULT_RE.search(segment)
        if not match:
            continue
        if index and RESULT_RE.search(" ".join(" ".join(x.split()) for x in lines[index - 1 : index + 2])):
            continue
        raw_value = " ".join(match.group(0).split()).split(":", 1)[-1].strip()
        numeric = parse_number(match.group("number"))
        reference = reference_near(lines, index)
        results.append(
            LabResult(
                arquivo=path.name,
                data=date,
                exame=probable_heading(lines, index),
                valor_texto=raw_value,
                valor_numerico=numeric,
                unidade=(match.group("unit") or "").strip(),
                referencia=reference,
                classificacao=classification(numeric, reference),
            )
        )
    return results


def find_pdfs(source: Path, temp_dir: Path) -> list[Path]:
    if source.is_dir():
        return sorted(source.rglob("*.pdf"))
    if source.suffix.lower() == ".pdf":
        return [source]
    if source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            for member in archive.infolist():
                target = (temp_dir / member.filename).resolve()
                if not str(target).startswith(str(temp_dir.resolve())):
                    raise ValueError("ZIP contem caminho inseguro")
                if member.filename.lower().endswith(".pdf"):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as src, target.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
        return sorted(temp_dir.rglob("*.pdf"))
    raise ValueError("Informe uma pasta, um PDF ou um ZIP")


def write_csv(path: Path, rows: Iterable[object], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_summary(path: Path, files: list[ExamFile], results: list[LabResult]) -> None:
    abnormal = [r for r in results if r.classificacao in {"acima", "abaixo"}]
    dates = sorted({f.data for f in files if f.data})
    lines = [
        "# Resumo local dos exames",
        "",
        "> Documento de organizacao. Nao constitui diagnostico nem recomendacao de tratamento.",
        "",
        f"- PDFs processados: {len(files)}",
        f"- Resultados extraidos automaticamente: {len(results)}",
        f"- Resultados possivelmente fora do intervalo: {len(abnormal)}",
        f"- Periodo identificado: {dates[0] if dates else 'nao identificado'} a {dates[-1] if dates else 'nao identificado'}",
        "",
        "## Itens para conferencia no laudo original",
        "",
    ]
    if abnormal:
        lines.extend(["| Data | Exame | Resultado | Sinalizacao | Arquivo |", "|---|---|---:|---|---|"])
        for r in sorted(abnormal, key=lambda x: (x.data or "", x.exame)):
            lines.append(f"| {r.data or '-'} | {r.exame} | {r.valor_texto} | {r.classificacao} | {r.arquivo} |")
    else:
        lines.append("Nenhum item foi classificado automaticamente como fora do intervalo.")
    lines += [
        "",
        "## Observacoes",
        "",
        "- Confirme cada valor no PDF original; layouts variam e a extracao pode errar.",
        "- 'Nao determinado' significa que o programa nao conseguiu interpretar o intervalo.",
        "- Sintomas, exame fisico, medicamentos e contexto clinico nao sao avaliados pelo programa.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Organiza exames PDF localmente")
    parser.add_argument("origem", type=Path, help="Pasta, PDF ou ZIP")
    parser.add_argument("--saida", type=Path, default=Path("resultado"))
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)

    files: list[ExamFile] = []
    results: list[LabResult] = []
    errors: list[dict[str, str]] = []

    with tempfile.TemporaryDirectory(prefix="exames_") as temp:
        try:
            pdfs = find_pdfs(args.origem, Path(temp))
        except Exception as exc:
            parser.error(str(exc))
        if not pdfs:
            parser.error("Nenhum PDF encontrado")
        for pdf in pdfs:
            try:
                text, pages = extract_text(pdf)
                date = first_date(text, pdf.name)
                item = ExamFile(pdf.name, date, classify_file(pdf.name, text), pages, sha256(pdf), bool(text.strip()))
                files.append(item)
                if item.tipo == "laboratorial":
                    results.extend(extract_results(pdf, text, date))
            except Exception as exc:
                errors.append({"arquivo": pdf.name, "erro": str(exc)})

    write_csv(args.saida / "catalogo.csv", files, list(ExamFile.__annotations__))
    write_csv(args.saida / "resultados.csv", results, list(LabResult.__annotations__))
    payload = {"aviso": "Organizacao automatica; nao e diagnostico medico.", "arquivos": [asdict(x) for x in files], "resultados": [asdict(x) for x in results], "erros": errors}
    (args.saida / "resultados.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(args.saida / "resumo.md", files, results)
    print(f"Concluido: {len(files)} PDFs, {len(results)} resultados, {len(errors)} erros.")
    print(f"Saida: {args.saida.resolve()}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
