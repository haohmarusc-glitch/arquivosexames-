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
import os
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

from achados import Achado, extrair_achados
from mapa_exames import identificar


DATE_RE = re.compile(r"\b([0-3]?\d/[01]?\d/(?:19|20)\d{2})\b")
RESULT_RE = re.compile(
    r"(?:Resultado|Resultado\s*obtido)\s*:\s*"
    r"(?P<value>(?:inferior|superior)\s+a\s+)?(?P<number>-?\d+(?:[.,]\d+)?)"
    r"\s*(?P<unit>[%A-Za-zµμ/³²0-9.]+(?:\s+em\s+\d+\s+min)?)?",
    re.IGNORECASE,
)
NAO_IDADE = r"(?![\d.,]*\s*anos)"  # "21 a 49 anos" e faixa etaria, nao limite de valor
REF_RANGE_RE = re.compile(
    r"(?P<low>-?\d+(?:[.,]\d+)?)\s*(?:a|ate|à|-)\s*"
    r"(?P<high>-?\d+(?:[.,]\d+)?)" + NAO_IDADE + r"\s*(?P<unit>[%A-Za-zµμ/³²0-9.]+)?",
    re.IGNORECASE,
)
REF_UPPER_RE = re.compile(
    r"(?:inferior|menor|ate)\s+(?:ou\s+igual\s+)?a?\s*(?P<high>\d+(?:[.,]\d+)?)" + NAO_IDADE,
    re.IGNORECASE,
)
REF_LOWER_RE = re.compile(
    r"(?:superior|maior)\s+(?:ou\s+igual\s+)?a\s+(?P<low>\d+(?:[.,]\d+)?)" + NAO_IDADE,
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
    duplicado_de: str | None = None
    aviso: str = ""


@dataclass
class LabResult:
    arquivo: str
    data: str | None
    exame: str
    valor_texto: str
    valor_numerico: float | None
    unidade: str
    referencia: str
    ref_min: float | None
    ref_max: float | None
    classificacao: str
    exame_id: str
    exame_nome: str
    sistema: str


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return "".join(c for c in value if not unicodedata.combining(c)).lower()


THOUSANDS_ONLY_DOT_RE = re.compile(r"^-?\d{1,3}(?:\.\d{3})+$")


def parse_number(value: str | None) -> float | None:
    """Converte numeros no formato brasileiro ou internacional.

    - "519,61" -> 519.61 (virgula decimal)
    - "1.250,5" -> 1250.5 (ponto de milhar + virgula decimal)
    - "5.0" / "0.8" -> 5.0 / 0.8 (ponto decimal)
    - "6.500" -> 6500 (so ponto, grupos de 3 digitos: convencao brasileira de milhar,
      comum em hemograma, ex. leucocitos/mm3)
    """
    if not value:
        return None
    value = value.strip()
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    elif THOUSANDS_ONLY_DOT_RE.match(value):
        value = value.replace(".", "")
    try:
        return float(value)
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


LABELED_DATE_RE = re.compile(
    r"(?:data\s+(?:do\s+)?(?:exame|atend\.?|coleta)|entrada|coleta|atendimento)\s*:?\s*\n?\s*"
    r"([0-3]?\d/[01]?\d/(?:19|20)\d{2})",
    re.IGNORECASE,
)
BIRTH_DATE_RE = re.compile(r"(?:d\.?\s*n\.?|data\s+de\s+nascimento)\s*:?\s*[0-3]?\d/[01]?\d/(?:19|20)\d{2}", re.IGNORECASE)


def _parse_br_date(text: str) -> str | None:
    try:
        return datetime.strptime(text, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def first_date(text: str, filename: str) -> str | None:
    head = text[:12000]
    labeled = LABELED_DATE_RE.search(head)
    if labeled:
        parsed = _parse_br_date(labeled.group(1))
        if parsed:
            return parsed
    name_match = re.search(r"((?:19|20)\d{2})[-_](\d{2})[-_](\d{2})", filename)
    if name_match:
        return "-".join(name_match.groups())
    # Ultimo recurso: primeira data solta, ignorando a de nascimento (que costuma vir antes).
    sem_nascimento = BIRTH_DATE_RE.sub("", head)
    for raw in DATE_RE.findall(sem_nascimento):
        parsed = _parse_br_date(raw)
        if parsed:
            return parsed
    return None


IMAGE_TOKENS = {"rm", "rnm", "rx", "tc", "usg", "tomo", "eco", "doppler"}
IMAGE_WORDS = (
    "ressonancia", "tomografia", "ultrasson", "ultrassom", "ultrassonografia",
    "radiografia", "raiox", "ecografia", "mamografia", "densitometria", "cintilografia",
)


def _mentions_image(text: str) -> bool:
    tokens = set(re.split(r"[^a-z0-9]+", text))
    compact = re.sub(r"[^a-z]", "", text)
    return bool(tokens & IMAGE_TOKENS) or any(word in compact for word in IMAGE_WORDS)


LAB_MARKERS_RE = re.compile(r"resultado\s*:.*?(?:valor(?:es)?\s+de\s+refer|coleta)", re.IGNORECASE | re.DOTALL)


def looks_like_lab(text: str) -> bool:
    return bool(LAB_MARKERS_RE.search(text[:6000]))


def classify_file(filename: str, text: str) -> str:
    """Classifica pelo CONTEUDO; o nome do arquivo so desempata.

    O portal pode salvar um laudo com o nome de outro pedido
    (ex.: "Rm_Coluna_Cervical.pdf" contendo exames de sangue).
    """
    name = normalize(filename)
    head = normalize(text[:1500])
    if "anatomopat" in re.sub(r"[^a-z]", "", head + name) and not looks_like_lab(text):
        return "anatomopatologico"
    if _mentions_image(head) and not looks_like_lab(text):
        return "imagem"
    if text.strip() and looks_like_lab(text):
        return "laboratorial"
    if _mentions_image(name):
        return "imagem"
    if "anatomopat" in re.sub(r"[^a-z]", "", name):
        return "anatomopatologico"
    return "laboratorial"


def probable_heading(lines: list[str], result_index: int) -> str:
    ignored = ("material", "metodo", "coleta", "liberacao", "resultado", "valor de referencia")
    anteriores = [i for i in range(result_index - 1, -1, -1) if lines[i].strip()][:14]  # ignora linhas em branco
    for i in anteriores:
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
    window = "\n".join(" ".join(x.split()) for x in lines[index + 1 : index + 20] if x.strip())
    marker = normalize(window).find("valor de referencia")
    if marker >= 0:
        window = window[marker:]
        window = window.split("\n", 1)[1] if "\n" in window and window.split("\n", 1)[0].rstrip(" .:").lower().endswith(("referencia", "referência")) else window
    partes = window.split("\n")
    while partes and (normalize(partes[0]).startswith("resultado") or NUM_LINE_RE.match(partes[0])
                      or (len(partes[0]) <= 10 and ":" not in partes[0] and not re.search(r"\d", partes[0]))):
        partes.pop(0)
    window = "\n".join(partes)
    corte = re.search(
        r"\n(?:notas?\b|obs\b|nota\b|observa|sr\s*\(a\)|idade\b|dr\s*\(a\)|data/hora|impresso|nome\s*:|documento\s*:|nro\.?\s*da\s*os)",
        window, re.IGNORECASE,
    )
    if corte:
        window = window[: corte.start()]
    return window[:700].strip()


SEXO_HEADERS = {"M": ("masculino", "homens", "homem"), "F": ("feminino", "mulheres", "mulher")}
PREFERIDAS = ("normal", "normoglicemia", "nao diabetico", "adequado", "desejavel", "referencia")
IDADE_FAIXA_RE = re.compile(r"(\d+)\s*a\s*(\d+)\s*(anos|meses)")
IDADE_MIN_RE = re.compile(r"(superior|maior|acima)\s*(ou\s+igual\s*)?(?:a|de)?\s*(\d+)\s*anos")
IDADE_MAX_RE = re.compile(r"(inferior|menor|abaixo|ate|<)\s*(ou\s+igual\s*)?(?:a|de)?\s*(\d+)\s*(anos|mes|meses)")


def _aplica(prefixo: str, idade: int | None) -> bool | None:
    """True/False se o rotulo da linha define para quem vale; None se nao fala de idade/grupo."""
    if "meta" in prefixo or "tratamento" in prefixo or "em uso de" in prefixo:
        return False  # alvo de tratamento, nao referencia geral
    if "gestante" in prefixo or "trimestre" in prefixo or "menacme" in prefixo or "menopausa" in prefixo or "fase " in prefixo:
        return False
    faixa, minimo, maximo = IDADE_FAIXA_RE.search(prefixo), IDADE_MIN_RE.search(prefixo), IDADE_MAX_RE.search(prefixo)
    if (faixa or minimo or maximo) and idade is None:
        return False  # depende da idade, que nao sabemos
    if faixa:
        a, b = int(faixa.group(1)), int(faixa.group(2))
        return faixa.group(3) == "anos" and a <= idade <= b  # type: ignore[operator]
    if minimo:
        c = int(minimo.group(3))
        return idade >= c if minimo.group(2) else idade > c  # type: ignore[operator]
    if maximo:
        if maximo.group(4) != "anos":
            return False
        c = int(maximo.group(3))
        return idade <= c if (maximo.group(2) or maximo.group(1) == "ate") else idade < c  # type: ignore[operator]
    if re.search(r"crianca|adolescente|pediatric|pre-? ?pubere|recem", prefixo):
        return False if idade is None or idade >= 18 else True
    if "adulto" in prefixo:
        return None if idade is None else idade >= 18
    return None


def select_reference(reference: str, sexo: str | None = None, idade: int | None = None) -> str:
    """Escolhe, numa tabela de referencia, as linhas que valem para esta pessoa.

    Entende cabecalhos de secao ("Masculino:", "Para adultos acima de 20 anos:",
    "Gestantes:") e linhas com o grupo no rotulo ("41 a 60 anos....: 2,67 a 18,30").
    Retorna "" quando a tabela depende de sexo/idade desconhecidos.
    """
    linhas = [normalize(" ".join(x.split())) for x in reference.splitlines()]
    linhas = [x for x in linhas if x]
    if len(linhas) <= 1:
        return reference

    def sexo_de(linha: str) -> str | None:
        for sx, termos in SEXO_HEADERS.items():
            if linha.startswith(termos):
                return sx
        return None

    secoes = [(i, sexo_de(l)) for i, l in enumerate(linhas) if sexo_de(l)]
    if len({sx for _, sx in secoes}) > 1:
        if sexo not in ("M", "F"):
            return ""
        escolhidas: list[str] = []
        for k, (i, sx) in enumerate(secoes):
            if sx != sexo:
                continue
            fim = secoes[k + 1][0] if k + 1 < len(secoes) else len(linhas)
            cauda = linhas[i].split(":", 1)[1] if ":" in linhas[i] else ""
            escolhidas += ([cauda] if cauda.strip() else []) + linhas[i + 1 : fim]
        linhas = [x for x in escolhidas if x.strip()]
        if not linhas:
            return ""

    # grupo (idade, gestante...) por linha, herdando o cabecalho de secao
    marcadas: list[tuple[str, str, bool | None]] = []
    contexto: bool | None = None
    for l in linhas:
        prefixo, _, cauda = l.partition(":")
        grupo = _aplica(prefixo, idade)
        if not cauda.strip():  # cabecalho de secao
            contexto = grupo
            continue
        efetivo = False if contexto is False else (grupo if grupo is not None else contexto)
        marcadas.append((prefixo, cauda, efetivo))
    if not marcadas:
        return "\n".join(linhas)
    if any(g is not None for _, _, g in marcadas):
        marcadas = [m for m in marcadas if m[2] is not False]  # vale para todos ou para este grupo
        if not marcadas:
            return ""

    for termo in PREFERIDAS:
        for prefixo, cauda, _ in marcadas:
            if prefixo.startswith(termo):
                return cauda
    return "\n".join(cauda if (g is not None or ":" in reference) else p + ":" + cauda for p, cauda, g in marcadas)


def reference_bounds(reference: str) -> tuple[float | None, float | None, bool]:
    """Retorna (minimo, maximo, encontrado) do intervalo de referencia."""
    if not reference:
        return None, None, False
    normalized = normalize(reference)
    if any(t in normalized for t in ("alvo terapeutico", "categoria de risco", "nao ha valores de referencia")):
        # Meta depende do risco estimado pelo medico: nao ha um limite unico para comparar.
        return None, None, False
    upper = REF_UPPER_RE.search(normalized)
    if upper:
        return None, parse_number(upper.group("high")), True
    lower = REF_LOWER_RE.search(normalized)
    if lower:
        return parse_number(lower.group("low")), None, True
    range_match = REF_RANGE_RE.search(normalized)
    if range_match:
        return parse_number(range_match.group("low")), parse_number(range_match.group("high")), True
    return None, None, False


def classification(value: float | None, reference: str) -> str:
    if value is None:
        return "nao determinado"
    if not reference_bounds(reference)[2] and any(
        t in normalize(reference) for t in ("alvo terapeutico", "categoria de risco", "nao ha valores de referencia")
    ):
        return "nao determinado"
    candidatas = [x for x in reference.splitlines() if reference_bounds(x)[2]]
    if len(candidatas) > 1:
        # Ex.: "com jejum" e "sem jejum": so classifica se todas concordam.
        vereditos = {_classifica_uma(value, x) for x in candidatas}
        return vereditos.pop() if len(vereditos) == 1 else "nao determinado"
    return _classifica_uma(value, reference)


def _classifica_uma(value: float, reference: str) -> str:
    low, high, found = reference_bounds(reference)
    if not found or (low is None and high is None):
        return "nao determinado"
    if low is not None and value < low:
        return "abaixo"
    if high is not None and value > high:
        return "acima"
    return "dentro"


COLETA_RE = re.compile(r"coleta\s*:?\s*\n?\s*([0-3]?\d/[01]?\d/(?:19|20)\d{2})", re.IGNORECASE)
NUM_LINE_RE = re.compile(r"^-?\d{1,3}(?:\.\d{3})*(?:,\d+)?$|^-?\d+(?:[.,]\d+)?$")
LABEL_RE = re.compile(r"^(?P<label>[^\d:\s][^:]{0,70}?)[\s.]*:\s*$")
REF_LINE_RE = re.compile(r"\d[\d.,]*\s*(?:a|ate|-)\s*\d|inferior|superior|menor|maior|nao ha valores", re.IGNORECASE)
IGNORED_LABELS = (
    "material", "coleta", "liberacao", "metodo", "valor de referencia", "valores de referencia", "nota", "obs",
    "sr (a)", "idade", "dr (a)", "data", "nro", "documento", "celulas contadas", "resultado", "homens", "mulheres",
    "eritrograma", "leucograma", "local", "prescricao", "responsavel",
)
UNIT_PAREN_RE = re.compile(r"^(?P<nome>.*?)\s*\((?P<unit>[^)]*(?:/|%|dl|l|fl|pg|mm3)[^)]*)\)\s*$", re.IGNORECASE)


def split_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Blocos de exame no formato "TITULO / Material: / Coleta: ..."."""
    # O pypdf 6 pode inserir linhas em branco entre o titulo e "Material:".
    cheias = [i for i, l in enumerate(lines) if l.strip()]
    heads = [a for a, b in zip(cheias, cheias[1:]) if lines[b].strip().lower().startswith("material")]
    if not heads:
        return [(0, len(lines))]
    return [(h, heads[k + 1] if k + 1 < len(heads) else len(lines)) for k, h in enumerate(heads)]


def block_date(lines: list[str], fallback: str | None) -> str | None:
    match = COLETA_RE.search("\n".join([l for l in lines if l.strip()][:12]))
    if match:
        try:
            return datetime.strptime(match.group(1), "%d/%m/%Y").date().isoformat()
        except ValueError:
            pass
    return fallback


def _is_label(line: str) -> str | None:
    m = LABEL_RE.match(line)
    if not m:
        return None
    label = " ".join(m.group("label").split()).strip(" .")
    if not label or normalize(label).startswith(IGNORED_LABELS):
        return None
    return label


PERFIL: dict[str, object] = {"sexo": None, "idade": None}
IDADE_RE = re.compile(r"idade\s*\n?\s*:?\s*\n?\s*(\d{1,3})\s*anos", re.IGNORECASE)


def _make_result(path: Path, date: str | None, exame: str, raw: str, numeric: float | None, unit: str, reference: str) -> LabResult:
    escolhida = select_reference(reference, PERFIL.get("sexo"), PERFIL.get("idade"))  # type: ignore[arg-type]
    ref_min, ref_max, _ = reference_bounds(escolhida)
    exame_id, exame_nome, sistema = identificar(exame)
    return LabResult(
        arquivo=path.name, data=date, exame=exame, valor_texto=raw, valor_numerico=numeric, unidade=unit,
        referencia=reference, ref_min=ref_min, ref_max=ref_max, classificacao=classification(numeric, escolhida),
        exame_id=exame_id, exame_nome=exame_nome, sistema=sistema,
    )


def extract_panel(path: Path, lines: list[str], date: str | None, heading: str) -> list[LabResult]:
    """Paineis como hemograma e bilirrubinas: "Nome......:" seguido do valor e da faixa."""
    clean = [" ".join(x.split()) for x in lines]
    clean = [x for x in clean if x]
    results: list[LabResult] = []
    prefix = "Eletroforese " if "eletroforese" in normalize(heading) else ""
    for i, line in enumerate(clean):
        label = _is_label(line)
        if not label:
            continue
        values: list[tuple[str, str]] = []  # (valor, unidade)
        reference = ""
        for nxt in clean[i + 1 : i + 12]:
            if _is_label(nxt):
                break
            low = normalize(nxt)
            if low.startswith("valor de referencia"):
                tail = nxt.split(":", 1)[1].strip() if ":" in nxt else ""
                if tail:
                    reference = tail
                    break
                continue
            if NUM_LINE_RE.match(nxt):
                values.append((nxt, ""))
            elif values and REF_LINE_RE.search(low):
                reference = nxt
                j = clean.index(nxt, i + 1) + 1
                while j < len(clean) and normalize(clean[j]).startswith(SEXO_HEADERS["M"] + SEXO_HEADERS["F"]):
                    reference += "\n" + clean[j]
                    j += 1
                break
            elif values and not values[-1][1] and len(nxt) <= 14 and not nxt[0].isdigit():
                values[-1] = (values[-1][0], nxt)
        if not values:
            continue
        raw, unit = values[-1]  # leucograma/eletroforese: % e absoluto -> usa o absoluto
        nome = label
        paren = UNIT_PAREN_RE.match(label)
        if paren:
            nome, unit = paren.group("nome").strip(" ."), unit or paren.group("unit")
        if not unit and reference:
            tokens = reference.split()
            unit = tokens[-1] if tokens and not tokens[-1][0].isdigit() else ""
        results.append(_make_result(path, date, prefix + nome, f"{raw} {unit}".strip(), parse_number(raw), unit, reference))
    return results


def extract_results(path: Path, text: str, date: str | None) -> list[LabResult]:
    idade = IDADE_RE.search(text)
    PERFIL["idade"] = int(idade.group(1)) if idade else None
    all_lines = text.splitlines()
    results: list[LabResult] = []
    for start, end in split_blocks(all_lines):
        lines = all_lines[start:end]
        bdate = block_date(lines, date)
        found = False
        for index, line in enumerate(lines):
            # Alguns laboratorios colocam "Resultado:" e o valor em linhas separadas.
            segment = " ".join(" ".join(x.split()) for x in lines[index : index + 3])
            match = RESULT_RE.search(segment)
            if not match:
                continue
            if index and RESULT_RE.search(" ".join(" ".join(x.split()) for x in lines[index - 1 : index + 2])):
                continue
            found = True
            raw_value = " ".join(match.group(0).split()).split(":", 1)[-1].strip()
            exame = probable_heading(lines, index)
            if exame == "Exame nao identificado" and start and lines[0].strip():
                exame = " ".join(lines[0].split())  # titulo do bloco
            results.append(_make_result(path, bdate, exame, raw_value,
                                        parse_number(match.group("number")), (match.group("unit") or "").strip(),
                                        reference_near(lines, index)))
        if not found:
            heading = " ".join(lines[0].split()) if lines else ""
            results.extend(extract_panel(path, lines, bdate, heading))
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


def extract_achados_seguro(nome: str, date: str | None, text: str) -> list[Achado]:
    try:
        return extrair_achados(nome, date, text)
    except Exception:  # um laudo com layout inesperado nao deve parar a analise
        return []


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
    parser.add_argument("--sexo", choices=["M", "F"], default=os.environ.get("ANALISADOR_SEXO") or None,
                        help="Escolhe a faixa de referencia certa em tabelas por sexo (ou ANALISADOR_SEXO)")
    args = parser.parse_args()
    PERFIL["sexo"] = args.sexo
    args.saida.mkdir(parents=True, exist_ok=True)

    files: list[ExamFile] = []
    results: list[LabResult] = []
    findings: list[Achado] = []
    errors: list[dict[str, str]] = []

    with tempfile.TemporaryDirectory(prefix="exames_") as temp:
        try:
            pdfs = find_pdfs(args.origem, Path(temp))
        except Exception as exc:
            parser.error(str(exc))
        if not pdfs:
            parser.error("Nenhum PDF encontrado")
        vistos: dict[str, str] = {}
        for pdf in pdfs:
            try:
                digest = sha256(pdf)
                text, pages = extract_text(pdf)
                # Compara pelo texto: o portal pode gerar bytes diferentes para o mesmo laudo.
                chave = hashlib.sha256(" ".join(text.split()).encode()).hexdigest() if text.strip() else digest
                if chave in vistos:
                    files.append(ExamFile(pdf.name, None, "duplicado", pages, digest, True, duplicado_de=vistos[chave],
                                          aviso=f"conteudo identico a {vistos[chave]}"))
                    continue
                vistos[chave] = pdf.name
                date = first_date(text, pdf.name)
                tipo = classify_file(pdf.name, text)
                aviso = ""
                if tipo == "laboratorial" and _mentions_image(normalize(pdf.name)):
                    aviso = "nome indica exame de imagem, mas o conteudo e laboratorial"
                item = ExamFile(pdf.name, date, tipo, pages, digest, bool(text.strip()), aviso=aviso)
                files.append(item)
                if tipo == "laboratorial":
                    results.extend(extract_results(pdf, text, date))
                elif tipo == "imagem" and text.strip():
                    findings.extend(extract_achados_seguro(pdf.name, date, text))
            except Exception as exc:
                errors.append({"arquivo": pdf.name, "erro": str(exc)})

    write_csv(args.saida / "catalogo.csv", files, list(ExamFile.__annotations__))
    write_csv(args.saida / "resultados.csv", results, list(LabResult.__annotations__))
    payload = {"aviso": "Organizacao automatica; nao e diagnostico medico.", "arquivos": [asdict(x) for x in files], "resultados": [asdict(x) for x in results], "achados": [asdict(x) for x in findings], "erros": errors}
    (args.saida / "resultados.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(args.saida / "resumo.md", files, results)
    dups = [f for f in files if f.tipo == "duplicado"]
    divergentes = [f for f in files if f.aviso and f.tipo != "duplicado"]
    print(f"Concluido: {len(files)} PDFs ({len(files) - len(dups)} unicos), {len(results)} resultados, "
          f"{len(findings)} achados de imagem, {len(errors)} erros.")
    if dups:
        print(f"ATENCAO: {len(dups)} PDF(s) com conteudo repetido, ignorados (confira o download no portal).")
    if divergentes:
        print(f"ATENCAO: {len(divergentes)} PDF(s) com nome de exame de imagem, mas conteudo laboratorial.")
    print(f"Saida: {args.saida.resolve()}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
