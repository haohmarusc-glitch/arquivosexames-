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
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader

from achados import Achado, extrair_achados
from mapa_exames import NAO_MARCADORES, e_generico, identificar


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
    hash_texto: str = ""  # sha256 do texto normalizado, usado para detectar o mesmo laudo com bytes diferentes
    origem: str = ""  # "envio": veio da pasta de PDFs enviados pelo painel (--enviados)


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
    material: str = ""  # material/secao do bloco (ex.: "Urina jato medio"), separa urina de sangue
    unidade_fonte: str = ""  # "laudo", "referencia", "padrao" (so exibicao) ou ""
    grafico: bool = True  # False: fica na tabela, mas nao entra no grafico
    motivo: str = ""  # por que grafico=False
    arquivos: list[str] = field(default_factory=list)  # todos os PDFs com este mesmo valor
    coleta_hora: str = ""  # "HH:MM" da coleta; desempata duas coletas no mesmo dia


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


def limites_referencia(reference: str) -> tuple[float | None, float | None]:
    """(ref_min, ref_max) usados no grafico E na classificacao.

    Varias faixas que discordam (ex.: "com jejum" x "sem jejum") ou metas por
    categoria de risco nao dao um limite unico: devolve (None, None).
    """
    if not reference:
        return None, None
    candidatas = {reference_bounds(x)[:2] for x in reference.splitlines() if reference_bounds(x)[2]}
    if len(candidatas) > 1:
        return None, None
    low, high, _ = reference_bounds(reference)
    return low, high


def classificar(value: float | None, ref_min: float | None, ref_max: float | None) -> str:
    """Classificacao derivada SOMENTE de ref_min/ref_max, para nunca divergir do grafico."""
    if value is None or (ref_min is None and ref_max is None):
        return "nao determinado"
    if ref_min is not None and value < ref_min:
        return "abaixo"
    if ref_max is not None and value > ref_max:
        return "acima"
    return "dentro"


def classification(value: float | None, reference: str) -> str:
    return classificar(value, *limites_referencia(reference))


# ------------------------------------------------------------------ Unidades

UNIDADE_TOKEN_RE = re.compile(r"^[A-Za-zÀ-ÿµμ%‰°/³²¹⁰-⁹0-9.^x\-]+$")  # com acento: "milhões/mm3"
UNIDADE_PALAVRAS = {
    "mg", "g", "ng", "pg", "ug", "µg", "μg", "mcg", "fl", "u", "ui", "mui", "µui", "μui", "uui", "meq", "mmol", "umol",
    "µmol", "μmol", "nmol", "pmol", "mm", "mmhg", "s", "seg", "segundos", "segundo", "min", "minutos", "ratio", "kg", "cm",
    "l", "ml", "dl", "mm3", "mm³", "cel", "celulas", "milhoes", "mil", "ufc", "campo", "ms", "copias", "ua", "iu", "miu",
}
NAO_UNIDADE = {
    "a", "ate", "de", "da", "do", "e", "ou", "em", "para", "com", "sem", "sr", "sra", "dr", "dra", "nota", "notas", "obs",
    "inferior", "superior", "menor", "maior", "igual", "resultado", "valor", "valores", "referencia", "negativo",
    "positivo", "reagente", "nao", "ausente", "ausentes", "presente", "idade", "anos", "material", "metodo", "coleta",
}


def unidade_valida(unidade: str | None) -> str:
    """Devolve a unidade limpa, ou "" quando o texto capturado e pedaco do laudo
    ("Sr (a)", "Ate 1,2", ">= 39.000.000", "Notas:") e nao uma unidade."""
    u = " ".join((unidade or "").split()).strip(" .;")
    if not u or len(u) > 20 or re.search(r"[:()<>=≤≥,]", u):
        return ""
    tokens = u.split()
    if len(tokens) > 2 or not all(UNIDADE_TOKEN_RE.match(t) for t in tokens):
        return ""
    if normalize(tokens[0]).strip(".") in NAO_UNIDADE:
        return ""
    if not re.search(r"[A-Za-zÀ-ÿµμ%‰³²]", u):
        return ""  # so numeros
    if any(c in u for c in "/%‰^³²") or all(normalize(t).strip(".") in UNIDADE_PALAVRAS for t in tokens):
        return u
    return ""


UNIDADE_NA_REF_RE = re.compile(r"\d(?:[\d.,]*\d)?\s*(?P<u>[^\s\d][^\s]*(?:\s+/\s*[^\s]+)?)")


def unidade_da_referencia(reference: str) -> str:
    """Primeira unidade valida escrita logo depois de um numero da referencia ("70 a 99 mg/dL")."""
    for m in UNIDADE_NA_REF_RE.finditer(reference or ""):
        u = unidade_valida(m.group("u"))
        if u:
            return u
    return ""


# So para EXIBICAO quando nem o valor nem a referencia trazem a unidade. Nunca
# usada para decidir serie, conflito ou classificacao.
UNIDADE_PADRAO: dict[str, str] = {
    "glicose": "mg/dL", "hba1c": "%", "hemoglobina": "g/dL", "hematocrito": "%", "hemacias": "milhões/mm³",
    "leucocitos": "/mm³", "plaquetas": "/mm³", "vgm": "fL", "hcm": "pg", "chcm": "g/dL", "rdw": "%",
    "creatinina": "mg/dL", "ureia": "mg/dL", "acido_urico": "mg/dL", "colesterol_total": "mg/dL", "ldl": "mg/dL",
    "hdl": "mg/dL", "vldl": "mg/dL", "nao_hdl": "mg/dL", "triglicerides": "mg/dL", "tgo": "U/L", "tgp": "U/L",
    "ggt": "U/L", "fosfatase_alcalina": "U/L", "sodio": "mEq/L", "potassio": "mEq/L", "vhs": "mm/h",
    "ferritina": "ng/mL", "vitamina_d": "ng/mL", "vitamina_b12": "pg/mL", "tsh": "µUI/mL", "t4_livre": "ng/dL",
    "psa_total": "ng/mL", "psa_livre": "ng/mL", "tp_paciente": "s", "tp_normal": "s", "ttpa_paciente": "s",
    "ttpa_normal": "s", "tp_atividade": "%",
}


COLETA_RE = re.compile(r"coleta\s*:?\s*\n?\s*([0-3]?\d/[01]?\d/(?:19|20)\d{2})(?:\s*-?\s*(\d{1,2}:\d{2}))?", re.IGNORECASE)
NUM_LINE_RE = re.compile(r"^-?\d{1,3}(?:\.\d{3})*(?:,\d+)?$|^-?\d+(?:[.,]\d+)?$")
LABEL_RE = re.compile(r"^(?P<label>[^\d:\s][^:]{0,70}?)[\s.]*:\s*$")
REF_LINE_RE = re.compile(r"\d[\d.,]*\s*(?:a|ate|-)\s*\d|inferior|superior|menor|maior|nao ha valores", re.IGNORECASE)
IGNORED_LABELS = (
    "material", "coleta", "liberacao", "metodo", "valor de referencia", "valores de referencia", "nota", "obs",
    "sr (a)", "idade", "dr (a)", "data", "nro", "documento", "celulas contadas", "resultado", "homens", "mulheres",
    "eritrograma", "leucograma", "local", "prescricao", "responsavel",
)
# "Leucocitos................p/mL:" -> nome "Leucocitos", unidade "p/mL"
UNIT_DOTS_RE = re.compile(r"^(?P<nome>.*?\S)\s*\.{2,}\s*(?P<unit>[^\s.]\S*)$")
UNIT_SLASH_RE = re.compile(r"^.*?[^\s/]\s*(?P<unit>/\s*(?:ml|mm3|campo|µl|ul))$", re.IGNORECASE)
UNIT_PAREN_RE = re.compile(r"^(?P<nome>.*?)\s*\((?P<unit>[^)]*(?:/|%|dl|l|fl|pg|mm3)[^)]*)\)\s*$", re.IGNORECASE)
MATERIAL_RE = re.compile(r"^\s*material\s*:?\s*(?P<resto>.*)$", re.IGNORECASE)


def block_material(lines: list[str]) -> str:
    """Titulo + material do bloco ("EAS / Urina jato medio"), usado para separar urina de sangue."""
    cheias = [" ".join(l.split()) for l in lines if l.strip()][:8]
    partes: list[str] = cheias[:1]
    for k, linha in enumerate(cheias):
        m = MATERIAL_RE.match(linha)
        if m:
            resto = m.group("resto").strip()
            partes.append(resto or (cheias[k + 1] if k + 1 < len(cheias) else ""))
            break
    return " / ".join(p for p in partes if p)


RESULTADO_TEXTO_RE = re.compile(
    r"^(?:nao\s+)?(?:reagente|reativo|detectado|detectavel)s?$|^(?:negativo|positivo|ausentes?|presentes?|indeterminado|inconclusivo)$"
)


def titulo_acima(lines: list[str], index: int) -> str | None:
    """Titulo real do exame nas linhas acima de um rotulo generico ("Indice")."""
    for i in range(index - 1, -1, -1):
        candidato = " ".join(lines[i].split()).strip(" _:-.")
        if not candidato or len(candidato) > 100 or e_generico(candidato) or ":" in lines[i]:
            continue
        baixo = normalize(candidato)
        if baixo.startswith(IGNORED_LABELS) or NUM_LINE_RE.match(candidato) or REF_LINE_RE.search(baixo):
            continue
        if RESULTADO_TEXTO_RE.match(baixo):
            continue  # "NAO REAGENTE" e o resultado, nao o titulo do exame
        letras = [c for c in candidato if c.isalpha()]
        if len(letras) >= 3 and sum(c.isupper() for c in letras) / len(letras) >= 0.72:
            return candidato
    return None


def resolver_generico(exame: str, lines: list[str], index: int) -> tuple[str, bool]:
    """"Indice" sozinho vira "<TITULO> - Indice"; sem titulo, nao vai para o grafico."""
    if not e_generico(exame):
        return exame, True
    titulo = titulo_acima(lines, index)
    return (f"{titulo} - {exame}", True) if titulo else (exame, False)


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


def block_hora(lines: list[str]) -> str:
    match = COLETA_RE.search("\n".join([l for l in lines if l.strip()][:12]))
    return (match.group(2) or "").zfill(5) if match and match.group(2) else ""


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


def _make_result(path: Path, date: str | None, exame: str, raw: str, numeric: float | None, unit: str, reference: str,
                 material: str = "", grafico: bool = True) -> LabResult:
    escolhida = select_reference(reference, PERFIL.get("sexo"), PERFIL.get("idade"))  # type: ignore[arg-type]
    ref_min, ref_max = limites_referencia(escolhida)
    unidade, fonte = unidade_valida(unit), "laudo"
    if not unidade:
        unidade, fonte = unidade_da_referencia(escolhida or reference), "referencia"
    exame_id, exame_nome, sistema = identificar(exame, material, unidade)
    return LabResult(
        arquivo=path.name, data=date, exame=exame, valor_texto=raw, valor_numerico=numeric, unidade=unidade,
        referencia=reference, ref_min=ref_min, ref_max=ref_max, classificacao=classificar(numeric, ref_min, ref_max),
        exame_id=exame_id, exame_nome=exame_nome, sistema=sistema, material=material,
        unidade_fonte=fonte if unidade else "", grafico=grafico,
        motivo="" if grafico else "rotulo generico sem titulo do exame", arquivos=[path.name],
    )


def _prefixo_painel(titulo: str) -> str:
    t = normalize(titulo)
    if "eletroforese" in t:
        return "Eletroforese "
    if re.search(r"\bttpa\b|tromboplastina\s+parcial|\b[ak]ptt\b", t):
        return "TTPA "  # "Tempo paciente" do TTPA nao e o do tempo de protrombina
    return ""


def _e_subtitulo(linha: str) -> bool:
    if ":" in linha or linha.startswith(("|", "_", "-", "(")) or NUM_LINE_RE.match(linha):
        return False
    letras = [c for c in linha if c.isalpha()]
    return len(letras) >= 3 and sum(c.isupper() for c in letras) / len(letras) >= 0.8


def extract_panel(path: Path, lines: list[str], date: str | None, heading: str, material: str = "") -> list[LabResult]:
    """Paineis como hemograma e bilirrubinas: "Nome......:" seguido do valor e da faixa."""
    clean = [" ".join(x.split()) for x in lines]
    clean = [x for x in clean if x]
    results: list[LabResult] = []
    secao = ""  # subtitulo dentro do bloco (COAGULOGRAMA traz TAP e KPTT juntos)
    for i, line in enumerate(clean):
        label = _is_label(line)
        if not label:
            if _e_subtitulo(line):
                secao = line
            continue
        prefix = _prefixo_painel(secao) or _prefixo_painel(heading)
        if prefix == "TTPA " and not re.match(r"(?:tempo|razao|relacao)\b", normalize(label)):
            prefix = ""  # "Contagem de plaquetas" do coagulograma continua sendo plaquetas
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
            elif values and not values[-1][1] and len(nxt) <= 14 and not nxt[0].isdigit() and unidade_valida(nxt):
                values[-1] = (values[-1][0], nxt)
        if not values:
            continue
        raw, unit = values[-1]  # leucograma/eletroforese: % e absoluto -> usa o absoluto
        nome = label
        paren = UNIT_PAREN_RE.match(label)
        if paren:
            nome, unit = paren.group("nome").strip(" ."), unit or paren.group("unit")
        pontos = UNIT_DOTS_RE.match(nome)
        if pontos and unidade_valida(pontos.group("unit")):
            nome, unit = pontos.group("nome").strip(" ."), unit or pontos.group("unit")
        barra = UNIT_SLASH_RE.match(nome)
        if barra and not unit:
            unit = barra.group("unit")  # "Hemacias/ml": o nome fica inteiro (o mapa usa "espermatozoides/ml")
        nome, grafico = resolver_generico(nome, clean, i)
        unit = unidade_valida(unit)  # sem unidade valida, _make_result tenta a da referencia
        results.append(_make_result(path, date, prefix + nome, f"{raw} {unit}".strip(), parse_number(raw), unit, reference,
                                    material=material, grafico=grafico))
    return results


def extract_results(path: Path, text: str, date: str | None) -> list[LabResult]:
    idade = IDADE_RE.search(text)
    PERFIL["idade"] = int(idade.group(1)) if idade else None
    all_lines = text.splitlines()
    results: list[LabResult] = []
    for start, end in split_blocks(all_lines):
        lines = all_lines[start:end]
        bdate = block_date(lines, date)
        material = block_material(lines)
        inicio = len(results)
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
            linha_titulo = next((i for i in range(index - 1, -1, -1) if " ".join(lines[i].split()) == exame), index)
            exame, grafico = resolver_generico(exame, lines, linha_titulo)
            results.append(_make_result(path, bdate, exame, raw_value,
                                        parse_number(match.group("number")), (match.group("unit") or "").strip(),
                                        reference_near(lines, index), material=material, grafico=grafico))
        if not found:
            heading = " ".join(lines[0].split()) if lines else ""
            results.extend(extract_panel(path, lines, bdate, heading, material))
        for r in results[inicio:]:
            r.coleta_hora = block_hora(lines)
    return results


# ------------------------------------------------------------------ Consolidacao da serie

MOTIVO_SEM_UNIDADE = "sem unidade numa serie em "
MOTIVO_CONFLITO = "outro valor na mesma data"
MOTIVO_SEM_TITULO = "rotulo generico sem titulo do exame"
MOTIVO_TECNICO = "contagem tecnica do exame, nao e marcador"


def chave_unidade(u: str | None) -> str:
    """"p/mL" = "/mL", "milhões/mm³" = "milhoes/mm3", "µL" = "uL": mesma unidade escrita diferente."""
    k = normalize(u or "").replace("μ", "u").replace("µ", "u").replace("³", "3").replace("²", "2").replace(" ", "")
    return re.sub(r"^p/", "/", k)


def _dominante(contagem: Counter) -> str | None:
    if not contagem:
        return None
    unidade, n = contagem.most_common(1)[0]
    return unidade if n >= 2 and n * 2 > sum(contagem.values()) else None


def consolidar(resultados: list[dict]) -> tuple[list[dict], list[dict]]:
    """Normaliza a lista de resultados (dicts) e decide o que vai para o grafico.

    Idempotente: a API chama de novo sobre o JSON ja consolidado + envios.
    - unidade: rejeita texto do laudo, tenta a da referencia, e so no fim usa
      UNIDADE_PADRAO (marcada como "padrao", apenas exibicao);
    - id: recalculado com material/unidade (urina x sangue);
    - classificacao: SOMENTE de ref_min/ref_max;
    - ponto sem unidade numa serie com unidade dominante sai do grafico;
    - (marcador, data, valor) repetido vira um registro com todos os arquivos;
      valores diferentes na mesma data vao para os conflitos e so um fica no grafico.
    Retorna (resultados, conflitos).
    """
    saida: list[dict] = []
    for original in resultados:
        r = dict(original)
        r.setdefault("material", "")
        r["arquivos"] = sorted(set(r.get("arquivos") or []) | ({r["arquivo"]} if r.get("arquivo") else set()))
        motivo = r.get("motivo") or ""
        if motivo.startswith((MOTIVO_SEM_UNIDADE, MOTIVO_CONFLITO)):
            r["grafico"], r["motivo"] = True, ""  # decisoes da serie: refeitas abaixo
        else:
            r["grafico"], r["motivo"] = r.get("grafico", True) is not False and not motivo, motivo
        fonte = r.get("unidade_fonte", "laudo")
        unidade = "" if fonte == "padrao" else unidade_valida(r.get("unidade"))
        if unidade:
            fonte = fonte or "laudo"
        else:
            unidade = unidade_da_referencia(r.get("referencia") or "")
            fonte = "referencia" if unidade else ""
        r["unidade"], r["unidade_fonte"] = unidade, fonte
        if r.get("exame"):
            r["exame_id"], r["exame_nome"], r["sistema"] = identificar(r["exame"], r["material"], unidade)
        elif not r.get("exame_id"):
            r["exame_id"], r["exame_nome"], r["sistema"] = identificar(None)
        if r["exame_id"] == "sem_titulo" and r["grafico"]:
            r["grafico"], r["motivo"] = False, MOTIVO_SEM_TITULO
        if r["exame_id"] in NAO_MARCADORES and r["grafico"]:
            r["grafico"], r["motivo"] = False, MOTIVO_TECNICO
        r.setdefault("ref_min", None)
        r.setdefault("ref_max", None)
        r["classificacao"] = classificar(r.get("valor_numerico"), r["ref_min"], r["ref_max"])
        saida.append(r)

    serie: dict[str, Counter] = defaultdict(Counter)
    for r in saida:
        if r["unidade"] and r.get("valor_numerico") is not None:
            serie[r["exame_id"]][chave_unidade(r["unidade"])] += 1
    dominante = {mid: _dominante(c) for mid, c in serie.items()}
    for r in saida:
        dom = dominante.get(r["exame_id"])
        if r["grafico"] and dom and not r["unidade"] and r.get("valor_numerico") is not None:
            r["grafico"], r["motivo"] = False, MOTIVO_SEM_UNIDADE + dom

    # mesma (marcador, data, valor): um registro so, com todos os arquivos
    unicos: dict[tuple, dict] = {}
    finais: list[dict] = []
    ordem = sorted(saida, key=lambda r: (not r["grafico"], not r["unidade"], r.get("arquivo") or ""))
    for r in ordem:
        if r.get("valor_numerico") is None or not r.get("data"):
            finais.append(r)
            continue
        chave = (r["exame_id"], r["data"], r["valor_numerico"])
        if chave in unicos:
            unicos[chave]["arquivos"] = sorted(set(unicos[chave]["arquivos"]) | set(r["arquivos"]))
            continue
        unicos[chave] = r
        finais.append(r)

    # valores diferentes na mesma data: so um no grafico
    grupos: dict[tuple, list[dict]] = defaultdict(list)
    for r in finais:
        if r["grafico"] and r.get("valor_numerico") is not None and r.get("data"):
            grupos[(r["exame_id"], r["data"])].append(r)
    conflitos: list[dict] = []
    for (mid, data), rs in sorted(grupos.items()):
        if len(rs) < 2:
            continue
        dom = dominante.get(mid)
        # unidade da serie; depois a coleta mais recente do dia; depois mais laudos confirmando
        rs.sort(key=lambda r: (chave_unidade(r["unidade"]) != dom, "".join(chr(0x10FFFF - ord(c)) for c in r.get("coleta_hora") or ""),
                               -len(r["arquivos"]), r["arquivos"][0] if r["arquivos"] else ""))
        escolhido = rs[0]
        for r in rs[1:]:
            r["grafico"], r["motivo"] = False, MOTIVO_CONFLITO
        conflitos.append({
            "exame_id": mid, "exame_nome": escolhido["exame_nome"], "data": data,
            "escolhido": escolhido["valor_numerico"],
            "valores": [{"valor": r["valor_numerico"], "valor_texto": r.get("valor_texto"), "unidade": r["unidade"],
                         "coleta_hora": r.get("coleta_hora", ""),
                         "arquivos": r["arquivos"], "no_grafico": r is escolhido} for r in rs],
        })

    # mesma unidade com grafias diferentes (mg/dl x mg/dL, uIU x µIU): a serie usa a mais comum
    grafias: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for r in finais:
        if r["unidade"]:
            grafias[(r["exame_id"], chave_unidade(r["unidade"]))][r["unidade"]] += 1
    for r in finais:
        if r["unidade"]:
            contagem = grafias[(r["exame_id"], chave_unidade(r["unidade"]))]
            r["unidade"] = max(contagem, key=lambda u: (contagem[u], u != u.lower(), "µ" in u, u))

    for r in finais:
        if not r["unidade"] and r["exame_id"] in UNIDADE_PADRAO:
            r["unidade"], r["unidade_fonte"] = UNIDADE_PADRAO[r["exame_id"]], "padrao"
    finais.sort(key=lambda r: (r.get("data") or "", r.get("arquivo") or ""))
    return finais, conflitos


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


def chave_texto(text: str, digest: str) -> str:
    """Chave de duplicidade: o portal pode gerar bytes diferentes para o mesmo laudo."""
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest() if text.strip() else digest


def analisar_pdf(pdf: Path, vistos: dict[str, str], nome: str | None = None) -> tuple[ExamFile, list[LabResult], list[Achado]]:
    """Processa um PDF. `vistos` (chave_texto -> nome) acumula os ja lidos para
    marcar duplicados; `nome` permite registrar um nome diferente do arquivo em
    disco (usado pelo upload do painel). Usado pela linha de comando e pela API."""
    nome = nome or pdf.name
    digest = sha256(pdf)
    text, pages = extract_text(pdf)
    chave = chave_texto(text, digest)
    if chave in vistos:
        return (ExamFile(nome, None, "duplicado", pages, digest, True, duplicado_de=vistos[chave],
                         aviso=f"conteudo identico a {vistos[chave]}", hash_texto=chave), [], [])
    vistos[chave] = nome
    date = first_date(text, nome)
    tipo = classify_file(nome, text)
    aviso = ""
    if tipo == "laboratorial" and _mentions_image(normalize(nome)):
        aviso = "nome indica exame de imagem, mas o conteudo e laboratorial"
    item = ExamFile(nome, date, tipo, pages, digest, bool(text.strip()), aviso=aviso, hash_texto=chave)
    results: list[LabResult] = []
    findings: list[Achado] = []
    if tipo == "laboratorial":
        results = extract_results(pdf, text, date)
    elif tipo == "imagem" and text.strip():
        findings = extract_achados_seguro(nome, date, text)
    if nome != pdf.name:
        for r in results:
            r.arquivo = nome
    return item, results, findings


def write_csv(path: Path, rows: Iterable[object], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            dados = row if isinstance(row, dict) else asdict(row)
            writer.writerow({k: "; ".join(v) if isinstance(v, list) else v for k, v in dados.items() if k in fieldnames})


def write_summary(path: Path, files: list[ExamFile], results: list[dict]) -> None:
    abnormal = [r for r in results if r["classificacao"] in {"acima", "abaixo"}]
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
        for r in sorted(abnormal, key=lambda x: (x["data"] or "", x["exame"])):
            lines.append(f"| {r['data'] or '-'} | {r['exame']} | {r['valor_texto']} | {r['classificacao']} | {', '.join(r['arquivos'])} |")
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
    parser.add_argument("--enviados", type=Path, help="Pasta com os PDFs enviados pelo painel (entram depois da origem)")
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
            (Path(temp) / "origem").mkdir()
            pdfs = [(p, "") for p in find_pdfs(args.origem, Path(temp) / "origem")]
            if args.enviados and args.enviados.is_dir():
                # Depois da origem: um envio igual a um laudo do zip vira "duplicado".
                pdfs += [(p, "envio") for p in sorted(args.enviados.glob("*.pdf")) if not p.name.startswith(".")]
        except Exception as exc:
            parser.error(str(exc))
        if not pdfs:
            parser.error("Nenhum PDF encontrado")
        vistos: dict[str, str] = {}
        for pdf, origem in pdfs:
            try:
                item, novos, achados_pdf = analisar_pdf(pdf, vistos)
                item.origem = origem
                files.append(item)
                results.extend(novos)
                findings.extend(achados_pdf)
            except Exception as exc:
                errors.append({"arquivo": pdf.name, "erro": str(exc)})

    consolidados, conflitos = consolidar([asdict(x) for x in results])
    write_csv(args.saida / "catalogo.csv", files, list(ExamFile.__annotations__))
    write_csv(args.saida / "resultados.csv", consolidados, list(LabResult.__annotations__))
    payload = {"aviso": "Organizacao automatica; nao e diagnostico medico.", "arquivos": [asdict(x) for x in files], "resultados": consolidados, "achados": [asdict(x) for x in findings], "erros": errors}
    (args.saida / "resultados.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.saida / "conflitos.json").write_text(json.dumps(conflitos, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(args.saida / "resumo.md", files, consolidados)
    dups = [f for f in files if f.tipo == "duplicado"]
    divergentes = [f for f in files if f.aviso and f.tipo != "duplicado"]
    print(f"Concluido: {len(files)} PDFs ({len(files) - len(dups)} unicos), {len(consolidados)} resultados, "
          f"{len(findings)} achados de imagem, {len(errors)} erros.")
    if dups:
        print(f"ATENCAO: {len(dups)} PDF(s) com conteudo repetido, ignorados (confira o download no portal).")
    if conflitos:
        print(f"ATENCAO: {len(conflitos)} data(s) com valores diferentes para o mesmo marcador (ver conflitos.json).")
    if divergentes:
        print(f"ATENCAO: {len(divergentes)} PDF(s) com nome de exame de imagem, mas conteudo laboratorial.")
    print(f"Saida: {args.saida.resolve()}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
