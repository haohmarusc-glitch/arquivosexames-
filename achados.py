"""Extrai achados de laudos de imagem (RM, TC, RX, USG).

Copia o trecho de conclusao escrito pelo medico e identifica regiao do corpo,
niveis vertebrais e termos-chave. Nao interpreta nem cria diagnostico:
o painel exibe o texto original com o arquivo de origem.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


# So conta como cabecalho de secao quando a palavra fica sozinha na linha
# (opcionalmente com ":"), nunca no meio de uma frase como "...impressão na face ventral...".
SECAO_RE = re.compile(
    r"^[ \t]*(impress(?:a|ã)o\s+diagn(?:o|ó)stica|impress(?:a|ã)o|conclus(?:a|ã)o|opini(?:a|ã)o|diagn(?:o|ó)stico|relat(?:o|ó)rio)"
    r"[ \t]*:?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
FIM_SECAO_RE = re.compile(
    r"\n\s*(?:dr\.?\s*\(?a?\)?\s|dra\.?\s|crm|m[ée]dico\s*:|m[ée]dico\s+respons|assinado|laudo\s+liberado|laudado\s+por|liberado\s+em|"
    r"observa(?:c|ç)(?:a|ã)o|nota:|data\s+(?:do\s+)?laudo|nome\s*:|paciente\s+id)",
    re.IGNORECASE,
)

# Niveis vertebrais: C5-C6, C5/C6, C5-6, L5-S1, T12-L1, D11-D12
NIVEL_RE = re.compile(r"\b([CTDLS])\s?(\d{1,2})\s?[-/–]\s?([CTDLS])?\s?(\d{1,2})\b", re.IGNORECASE)
VERTEBRA_RE = re.compile(r"\b([CTDLS])(\d{1,2})\b")

REGIOES: list[tuple[str, tuple[str, ...]]] = [
    ("cervical", ("cervical", "cervicais")),
    ("toracica", ("toracic", "dorsal", "dorsais")),
    ("lombar", ("lombar", "lombo", "lombossac")),
    ("sacral", ("sacr", "coccig")),
    ("ombro", ("ombro", "manguito", "supraespinh", "glenoum")),
    ("cotovelo", ("cotovelo",)),
    ("punho_mao", ("punho", "mao ", "maos", "carpo", "dedos")),
    ("quadril", ("quadril", "coxofemoral", "acetab")),
    ("joelho", ("joelho", "menisco", "patela", "ligamento cruzado")),
    ("tornozelo_pe", ("tornozelo", "pe ", "pes ", "calcane", "tarso")),
    ("membros_inferiores", ("safena", "membro inferior", "membros inferiores", "trombose venosa profunda", "varizes")),
    ("renal", ("\\brim\\b", "rins", "renal", "nefro", "pielocalicinal")),
    ("escrotal", ("escroto", "testicul", "epididim", "bolsa escrotal", "pampiniforme", "cordao espermatico")),
    ("prostata", ("prostat",)),
    ("parede_abdominal", ("parede abdominal", "musculatura abdominal", "parede muscular")),
]

TERMOS: list[tuple[str, tuple[str, ...]]] = [
    ("hernia", ("hernia", "extrusao", "herniacao")),
    ("protrusao", ("protrusao", "abaulamento")),
    ("artrodese", ("artrodese", "parafusos pediculares", "espacador intersomatico", "fixacao")),
    ("estenose", ("estenose", "reducao da amplitude do canal", "compressao")),
    ("degenerativo", ("discopatia", "degenerativ", "espondilose", "osteofit", "desidratacao discal", "artrose")),
    ("listese", ("listese", "anterolistese", "retrolistese")),
    ("radicular", ("radicul", "raiz nervosa", "contato radicular")),
    ("fratura", ("fratura",)),
    ("lesao", ("tendin", "ruptura", "lesao")),
    ("inflamatorio", ("sinovite", "derrame articular", "edema osseo", "bursite")),
    ("calculo", ("calculo", "litiase", "nefrolitiase", "urolitiase")),
    ("esteatose", ("esteatose",)),
    ("varicocele", ("varicocele",)),
    ("cisto", ("cisto", "cistico")),
    ("insuficiencia_venosa", ("insuficiencia da veia", "insuficiencia venosa", "insuficiencia da safena", "veias colaterais insuficientes")),
    ("trombose", ("trombose", "trombo ")),
]

MODALIDADES = [
    ("ressonancia", ("ressonancia", "rm ", "r.m.")),
    ("tomografia", ("tomografia", "tc ")),
    ("radiografia", ("radiografia", "raio x", "raio-x", "rx ")),
    ("ultrassom", ("ultrasson", "ultrassom", "ecografia", "usg")),
]


@dataclass
class Achado:
    arquivo: str
    data: str | None
    modalidade: str
    regiao: str
    niveis: list[str] = field(default_factory=list)
    niveis_historicos: list[str] = field(default_factory=list)  # citados como resolvidos/anteriores no proprio laudo
    termos: list[str] = field(default_factory=list)
    lado: str = ""
    trecho: str = ""
    origem: str = "laudo"


def _nivel(letra1: str, n1: str, letra2: str | None, n2: str) -> str:
    l1 = "T" if letra1.upper() == "D" else letra1.upper()
    l2 = "T" if (letra2 or letra1).upper() == "D" else (letra2 or letra1).upper()
    return f"{l1}{int(n1)}-{l2}{int(n2)}"


def niveis_em(texto: str) -> list[str]:
    encontrados: list[str] = []
    for m in NIVEL_RE.finditer(texto):
        n = _nivel(m.group(1), m.group(2), m.group(3), m.group(4))
        if n not in encontrados:
            encontrados.append(n)
    return encontrados


def regiao_de_nivel(nivel: str) -> str:
    return {"C": "cervical", "T": "toracica", "L": "lombar", "S": "sacral"}[nivel[0]]


RESOLUCAO_RE = re.compile(
    r"resolu|nao mais (?:observ|visualiz|identific|evidenc)|regress|desapareceu|involuiu",
    re.IGNORECASE,
)


# Fim de frase: ponto, ponto-e-virgula, ou quebra de linha (laudos costumam
# quebrar linha a cada frase/item). Usado para nao deixar "resolucao" de uma
# frase "vazar" e marcar o nivel de OUTRA frase como resolvido por engano.
_FIM_FRASE = ".;\n"


def _nivel_historico(nivel: str, texto_norm: str) -> bool:
    """True se, na MESMA frase que menciona este nivel, o laudo disser que o
    achado se resolveu/regrediu (comparado a exame anterior). So olha dentro
    da frase para nao confundir com uma resolucao relatada para outro nivel
    em frase vizinha. Nao afirma cura clinica, so evita listar como atual algo
    que o proprio medico descreveu como resolvido."""
    for m in re.finditer(re.escape(nivel.lower()), texto_norm):
        ini = max((texto_norm.rfind(c, 0, m.start()) for c in _FIM_FRASE), default=-1)
        fim_candidatos = [texto_norm.find(c, m.end()) for c in _FIM_FRASE]
        fim_candidatos = [f for f in fim_candidatos if f != -1]
        fim = min(fim_candidatos) if fim_candidatos else len(texto_norm)
        frase = texto_norm[ini + 1 : fim]
        if RESOLUCAO_RE.search(frase):
            return True
    return False


def conclusao(texto: str) -> str:
    """Trecho da conclusao do laudo; se nao houver secao, usa o final do texto."""
    ultimo = None
    for m in SECAO_RE.finditer(texto):
        ultimo = m
    if ultimo:
        trecho = texto[ultimo.end():]
        fim = FIM_SECAO_RE.search(trecho)
        if fim:
            trecho = trecho[: fim.start()]
    else:
        trecho = texto[-900:]
    return " ".join(trecho.split())[:900]


NEGACAO_RE = re.compile(r"(?:\bsem\b|\bnao\b|ausencia|\bnega|livre de|nao se (?:observ|identific))[^.;]{0,30}$")


def _presente(termo: str, texto: str, negavel: bool) -> bool:
    for m in re.finditer(re.escape(termo), texto):
        if not negavel or not NEGACAO_RE.search(texto[max(0, m.start() - 40) : m.start()]):
            return True
    return False


def _detectar(tabela: list[tuple[str, tuple[str, ...]]], texto: str, negavel: bool = False) -> list[str]:
    return [chave for chave, termos in tabela if any(_presente(t, texto, negavel) for t in termos)]


def _lado(texto: str) -> str:
    d, e = re.search(r"\bdireit", texto), re.search(r"\besquerd", texto)
    if (d and e) or "bilateral" in texto:
        return "bilateral"
    return "direito" if d else "esquerdo" if e else ""


# Titulo de lado sozinho na linha, em maiusculas ("INFERIOR DIREITO", "OMBRO ESQUERDO"):
# laudos bilaterais (ex.: Doppler das duas pernas) trazem uma conclusao por lado.
TITULO_LADO_RE = re.compile(r"^[ \t]*[A-ZÀ-Ý][A-ZÀ-Ý \t/-]*\b(DIREIT[OA]|ESQUERD[OA])[ \t]*:?[ \t]*$", re.MULTILINE)


def secoes_por_lado(texto: str) -> list[tuple[str, str]]:
    """[(lado, texto da secao)] quando o laudo tem uma conclusao por lado; senao []."""
    titulos = list(TITULO_LADO_RE.finditer(texto))
    secoes: dict[str, str] = {}
    for i, m in enumerate(titulos):
        fim = titulos[i + 1].start() if i + 1 < len(titulos) else len(texto)
        lado = "direito" if m.group(1).startswith("DIREIT") else "esquerdo"
        corpo = texto[m.start():fim]
        if i + 1 < len(titulos):  # tira o comeco do proximo titulo ("DOPPLER VENOSO DO MEMBRO")
            linhas = corpo.rstrip().split("\n")
            while len(linhas) > 1 and linhas[-1].strip() and not re.search(r"[a-zà-ÿ]", linhas[-1]):
                linhas.pop()
            corpo = "\n".join(linhas)
        # O PDF pode repetir o laudo (uma copia por assinatura): fica a primeira secao com conclusao.
        if lado not in secoes and SECAO_RE.search(corpo):
            secoes[lado] = corpo
    return list(secoes.items()) if len(secoes) == 2 else []


def extrair_achados(arquivo: str, data: str | None, texto: str) -> list[Achado]:
    secoes = secoes_por_lado(texto)
    if secoes:
        cabecalho = texto[:1500]
        return [a for lado, corpo in secoes for a in _extrair(arquivo, data, corpo, cabecalho, lado)]
    return _extrair(arquivo, data, texto, texto[:1500], "")


def _extrair(arquivo: str, data: str | None, texto: str, inicio: str, lado_secao: str) -> list[Achado]:
    cabecalho = _norm(arquivo.replace("_", " ") + " " + inicio) + " "
    trecho = conclusao(texto)
    alvo = _norm(trecho) + " "
    texto_norm = _norm(texto)
    modalidade = next(iter(_detectar(MODALIDADES, cabecalho)), "imagem")
    # Niveis: procura no laudo INTEIRO, nao so no resumo/conclusao — a conclusao as vezes
    # cita menos niveis do que o corpo do laudo (ex.: resumo diz so C5-C6, mas o texto
    # tambem descreve C3-C4 e C7-T1).
    niveis = niveis_em(texto)
    historicos = [n for n in niveis if _nivel_historico(n, texto_norm)]
    regioes = _detectar(REGIOES, alvo)
    for n in niveis:
        r = regiao_de_nivel(n)
        if r not in regioes:
            regioes.append(r)
    if not regioes:  # a conclusao nao cita regiao nem nivel: usa o titulo do laudo
        regioes = _detectar(REGIOES, cabecalho)
    if not regioes:
        regioes = ["outros"]
    termos = _detectar(TERMOS, alvo, negavel=True)
    lado = lado_secao or _lado(alvo) or _lado(cabecalho)
    return [
        Achado(
            arquivo=arquivo,
            data=data,
            modalidade=modalidade,
            regiao=r,
            niveis=[n for n in niveis if regiao_de_nivel(n) == r] if r in ("cervical", "toracica", "lombar", "sacral") else [],
            niveis_historicos=[n for n in historicos if regiao_de_nivel(n) == r] if r in ("cervical", "toracica", "lombar", "sacral") else [],
            termos=termos,
            lado=lado if r not in ("cervical", "toracica", "lombar", "sacral") else "",
            trecho=trecho,
        )
        for r in regioes
    ]
