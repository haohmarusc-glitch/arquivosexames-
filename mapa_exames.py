"""Normaliza nomes de exames e associa cada marcador a um sistema do corpo.

Laboratorios diferentes escrevem o mesmo exame de formas diferentes
("COLESTEROL LDL", "LDL-COLESTEROL", "LDL COLESTEROL CALCULADO"...).
Sem normalizar, o grafico de evolucao fica fragmentado.

Para adicionar um exame: inclua uma entrada em MARCADORES com o id,
o nome de exibicao, o sistema e os padroes (em minusculas, sem acento).
A ordem importa: padroes mais especificos devem vir antes dos genericos.
"""

from __future__ import annotations

import re
import unicodedata

SISTEMAS: dict[str, str] = {
    "tireoide": "Tireoide",
    "coracao": "Coração e lipídios",
    "figado": "Fígado",
    "pancreas": "Glicemia e pâncreas",
    "rins": "Rins e urina",
    "sangue": "Sangue",
    "inflamacao": "Inflamação",
    "vitaminas": "Vitaminas e minerais",
    "hormonios": "Hormônios",
    "prostata": "Próstata",
    "testiculos": "Testículos e espermograma",
    "proteinas": "Proteínas",
    "outros": "Outros",
}

# (id, nome de exibicao, sistema, padroes)
MARCADORES: list[tuple[str, str, str, tuple[str, ...]]] = [
    # Eletroforese antes de albumina/proteinas para nao misturar series (% x g/dL)
    ("eletroforese_albumina", "Eletroforese: albumina", "proteinas", (r"eletroforese.*albumina",)),
    ("eletroforese_alfa1", "Eletroforese: alfa 1", "proteinas", (r"eletroforese.*alfa\s*1",)),
    ("eletroforese_alfa2", "Eletroforese: alfa 2", "proteinas", (r"eletroforese.*alfa\s*2",)),
    ("eletroforese_beta1", "Eletroforese: beta 1", "proteinas", (r"eletroforese.*beta\s*1",)),
    ("eletroforese_beta2", "Eletroforese: beta 2", "proteinas", (r"eletroforese.*beta\s*2",)),
    ("eletroforese_gama", "Eletroforese: gama", "proteinas", (r"eletroforese.*gama",)),
    ("eletroforese_relacao_ag", "Eletroforese: relação A/G", "proteinas", (r"eletroforese.*relacao",)),
    ("eletroforese_proteinas", "Eletroforese: proteínas totais", "proteinas", (r"eletroforese.*proteinas",)),
    ("relacao_ag", "Relação albumina/globulina", "proteinas", (r"relacao\s+a\s*/\s*g",)),
    ("proteinas_totais", "Proteínas totais", "proteinas", (r"proteinas\s+totais",)),
    ("globulina", "Globulina", "proteinas", (r"^globulina",)),
    ("lpa", "Lipoproteína (a)", "coracao", (r"lipoproteina\s*\(?a\)?", r"\blp\s*\(a\)")),
    ("relacao_psa", "Relação PSA livre/total", "prostata", (r"relacao\s+psa",)),
    ("psa_livre", "PSA livre", "prostata", (r"psa\s+livre",)),
    ("psa_total", "PSA total", "prostata", (r"psa\s+total", r"antigeno\s+prostatico")),
    ("dht", "Di-hidrotestosterona (DHT)", "hormonios", (r"di[\s-]*hidrotestosterona", r"\bdht\b")),
    ("testosterona_livre", "Testosterona livre", "hormonios", (r"testosterona\s+livre",)),
    ("testosterona_total", "Testosterona total", "hormonios", (r"testosterona(?:\s+total)?$",)),
    ("lh", "LH", "hormonios", (r"^lh\b", r"luteinizante")),
    ("fsh", "FSH", "hormonios", (r"^fsh\b", r"foliculo\s+estimulante")),
    ("estradiol", "Estradiol", "hormonios", (r"estradiol",)),
    ("prolactina", "Prolactina", "hormonios", (r"prolactina",)),
    ("shbg", "SHBG", "hormonios", (r"\bshbg\b",)),
    ("anti_tpo", "Anti-TPO", "tireoide", (r"anti[\s-]*tpo", r"tireoperoxidase")),
    ("nao_hdl", "Não-HDL", "coracao", (r"nao[\s-]*hdl",)),
    ("vldl", "VLDL", "coracao", (r"\bvldl\b",)),
    ("ldl", "LDL", "coracao", (r"\bldl\b",)),
    ("hdl", "HDL", "coracao", (r"\bhdl\b",)),
    ("colesterol_total", "Colesterol total", "coracao", (r"colesterol\s+total", r"^colesterol$")),
    ("triglicerides", "Triglicerídeos", "coracao", (r"triglicer",)),
    ("ck", "CK (CPK)", "coracao", (r"\bcpk\b", r"creatin[oa]\s*quinase", r"\bck\b")),
    ("hba1c", "Hemoglobina glicada", "pancreas", (r"glicad", r"\bhba1c\b", r"a1c")),
    ("glicose", "Glicose", "pancreas", (r"glicose", r"glicemia")),
    ("insulina", "Insulina", "pancreas", (r"insulina",)),
    ("tsh", "TSH", "tireoide", (r"\btsh\b", r"tireoestimulante")),
    ("t4_livre", "T4 livre", "tireoide", (r"t4\s*livre", r"tiroxina\s*livre")),
    ("t3", "T3", "tireoide", (r"\bt3\b",)),
    ("tgo", "AST (TGO)", "figado", (r"\btgo\b", r"\bast\b", r"aspartato")),
    ("tgp", "ALT (TGP)", "figado", (r"\btgp\b", r"\balt\b", r"alanina")),
    ("ggt", "Gama-GT", "figado", (r"gama[\s-]*g", r"\bggt\b", r"glutamiltransferase")),
    ("fosfatase_alcalina", "Fosfatase alcalina", "figado", (r"fosfatase\s+alcalina",)),
    ("bilirrubina_total", "Bilirrubina total", "figado", (r"bilirrubina\s+total",)),
    ("bilirrubina_direta", "Bilirrubina direta", "figado", (r"bilirrubina\s+direta",)),
    ("bilirrubina_indireta", "Bilirrubina indireta", "figado", (r"bilirrubina\s+indireta",)),
    ("albumina", "Albumina", "figado", (r"albumina",)),
    ("creatinina", "Creatinina", "rins", (r"creatinina",)),
    ("ureia", "Ureia", "rins", (r"ureia",)),
    ("acido_urico", "Ácido úrico", "rins", (r"acido\s+urico",)),
    ("tfg", "Taxa de filtração glomerular", "rins", (r"filtracao\s+glomerular", r"\btfg\b", r"\begfr\b")),
    ("potassio", "Potássio", "rins", (r"potassio",)),
    ("sodio", "Sódio", "rins", (r"sodio",)),
    # Urina tipo I (EAS), sedimento e urocultura: antes de "leucocitos"/"hemacias"
    # do hemograma, senao pontos /mL ou /campo caem na serie de sangue.
    # Bacterioscopia (Gram): contagem por campo (0 a ++++), nao por mL
    ("urina_gram_leucocitos", "Leucócitos polimorfonucleares (Gram)", "rins", (r"polimorfonuclea",)),
    # "Pesquisa de leucocitos" (urina de 1o jato) e outro exame que o sedimento do EAS
    ("urina_pesquisa_leucocitos", "Pesquisa de leucócitos (urina 1º jato)", "rins", (r"pesquisa\s+de\s+leucocitos",)),
    ("urina_leucocitos", "Leucócitos (urina)", "rins", (r"(?:urina|\beas\b|sediment|urocultura).*leucocitos",)),
    ("urina_hemacias", "Hemácias (urina)", "rins", (r"(?:urina|\beas\b|sediment|urocultura).*(?:hemacias|eritrocitos)",)),
    # Urina tipo I (EAS)
    ("urina_ph", "pH urinário", "rins", (r"^ph$", r"^ph\s+urin")),
    ("urina_densidade", "Densidade urinária", "rins", (r"^densidade$", r"densidade\s+urin")),
    ("urina_celulas_epiteliais_ml", "Células epiteliais por mL (urina)", "rins", (r"celulas\s+epiteliais.*p\s*/\s*ml",)),
    ("urina_celulas_epiteliais", "Células epiteliais (urina)", "rins", (r"celulas\s+epiteliais",)),
    ("urina_tipo1", "Urina tipo I", "rins", (r"urina\s+tipo", r"^eas$", r"sumario\s+de\s+urina")),
    # Coagulacao (tempo de protrombina) — fatores produzidos pelo figado
    # TTPA antes do TP: "razao paciente" e "tempo paciente" existem nos dois
    ("ttpa_paciente", "TTPA: tempo do paciente", "figado", (r"ttpa.*tempo\s+(?:do\s+)?paciente",)),
    ("ttpa_normal", "TTPA: tempo de controle", "figado", (r"ttpa.*tempo\s+(?:normal|controle)",)),
    ("ttpa_razao", "TTPA: razão paciente/normal", "figado", (r"ttpa.*(?:razao|relacao)",)),
    ("ttpa", "TTPA", "figado", (r"\bttpa\b", r"tromboplastina\s+parcial", r"\b[ak]ptt\b")),
    ("tp_rni", "RNI (tempo de protrombina)", "figado", (r"^rni$", r"^inr$", r"\brni\b")),
    ("tp_paciente", "Coagulação: tempo do paciente", "figado", (r"^tempo\s+(?:do\s+)?paciente",)),
    ("tp_normal", "Coagulação: tempo de controle", "figado", (r"^tempo\s+(?:normal|controle)",)),
    ("tp_razao", "Coagulação: razão paciente/normal", "figado", (r"razao\s+paciente",)),
    ("tp_atividade", "Atividade de protrombina", "figado", (r"atividade\s+(?:de\s+)?protrombina",)),
    ("anti_hbs", "Anti-HBs (imunidade hepatite B)", "figado", (r"anti[\s-]*hbs",)),
    ("hbsag", "HBsAg (hepatite B)", "figado", (r"\bhbsag\b",)),
    ("anti_hcv", "Anti-HCV (hepatite C)", "figado", (r"anti[\s-]*hcv",)),
    # Espermograma
    ("esperma_total", "Espermatozoides no ejaculado", "testiculos", (r"espermatozoides\s+no\s+ejaculado",)),
    ("esperma_concentracao", "Espermatozoides por mL", "testiculos", (r"espermatozoides\s*/?\s*ml",)),
    ("esperma_motil_progressiva", "Motilidade progressiva", "testiculos", (r"motilidade\s+progressiva",)),
    ("esperma_motil_nao_progressiva", "Motilidade não progressiva", "testiculos", (r"motilidade\s+nao\s+progressiva",)),
    ("esperma_imoveis", "Espermatozoides imóveis", "testiculos", (r"^imoveis$",)),
    ("esperma_normais", "Morfologia: formas normais", "testiculos", (r"^normais$", r"formas\s+normais")),
    ("esperma_vitalidade", "Vitalidade espermática", "testiculos", (r"^vitalidade$",)),
    ("vgm", "VGM (volume globular médio)", "sangue", (r"^vgm\b", r"^vcm\b")),
    ("hcm", "HCM (hemoglobina globular média)", "sangue", (r"^hbgm\b", r"^hcm\b")),
    ("chcm", "CHCM", "sangue", (r"^chbgm\b", r"^chcm\b")),
    ("rdw", "RDW", "sangue", (r"^rdw\b",)),
    ("neutrofilos_segmentados", "Neutrófilos segmentados", "sangue", (r"segmentados",)),
    ("bastonetes", "Bastonetes", "sangue", (r"bastonetes",)),
    ("eosinofilos", "Eosinófilos", "sangue", (r"eosinofilos",)),
    ("basofilos", "Basófilos", "sangue", (r"basofilos",)),
    ("linfocitos", "Linfócitos", "sangue", (r"linfocitos",)),
    ("monocitos", "Monócitos", "sangue", (r"monocitos",)),
    ("saturacao_transferrina", "Saturação da transferrina", "sangue", (r"saturacao\s+da\s+transferrina",)),
    ("hemoglobina", "Hemoglobina", "sangue", (r"^hemoglobina$", r"hemoglobina\s*\(?hb\)?$")),
    ("hematocrito", "Hematócrito", "sangue", (r"hematocrito",)),
    ("hemacias", "Hemácias", "sangue", (r"hemacias", r"eritrocitos")),
    ("leucocitos", "Leucócitos", "sangue", (r"leucocitos",)),
    ("plaquetas", "Plaquetas", "sangue", (r"plaquetas",)),
    ("ferritina", "Ferritina", "sangue", (r"ferritina",)),
    ("ferro", "Ferro sérico", "sangue", (r"\bferro\b",)),
    ("pcr", "Proteína C reativa", "inflamacao", (r"proteina\s+c\s+reativa", r"\bpcr\b")),
    ("vhs", "VHS", "inflamacao", (r"\bvhs\b", r"hemossedimentacao", r"sedimentacao")),
    ("fator_reumatoide", "Fator reumatoide", "inflamacao", (r"fator\s+reumatoide",)),
    ("vitamina_d", "Vitamina D", "vitaminas", (r"vitamina\s*d", r"hidroxivitamina", r"25[\s-]*oh")),
    ("vitamina_b12", "Vitamina B12", "vitaminas", (r"b\s*12", r"cobalamina")),
    ("vitamina_c", "Vitamina C", "vitaminas", (r"vitamina\s*c\b", r"acido\s+ascorbico")),
    ("vitamina_a", "Vitamina A", "vitaminas", (r"vitamina\s*a\b", r"retinol")),
    ("vitamina_b1", "Vitamina B1", "vitaminas", (r"vitamina\s*b\s*1\b", r"tiamina")),
    ("vitamina_b6", "Vitamina B6", "vitaminas", (r"vitamina\s*b\s*6\b", r"piridoxina")),
    ("vitamina_e", "Vitamina E", "vitaminas", (r"vitamina\s*e\b", r"tocoferol")),
    ("acido_folico", "Ácido fólico", "vitaminas", (r"acido\s+folico", r"folato")),
    ("magnesio", "Magnésio", "vitaminas", (r"magnesio",)),
    ("calcio", "Cálcio", "vitaminas", (r"calcio",)),
]

_COMPILADOS = [
    (mid, nome, sistema, tuple(re.compile(p) for p in padroes))
    for mid, nome, sistema, padroes in MARCADORES
]


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    return " ".join(texto.replace("_", " ").split()).strip(" :-.")


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _normalizar(texto)).strip("_") or "desconhecido"


# Rotulos que sozinhos nao dizem qual exame e ("Indice: 0,12" de uma sorologia).
# Sem o titulo real do exame, viram um marcador unico que junta sorologias diferentes.
GENERICO_RE = re.compile(
    r"^(?:indice|index|leitura|absorbancia|s\s*/\s*co|d\.?o\.?\s*/\s*c\.?o\.?|valor|titulo|resultado)(?:\s*\(.*\))?$"
)
INDICE_RE = re.compile(r"^(?P<titulo>.+?)\s+-\s+(?P<rotulo>indice|index|leitura|absorbancia|s\s*/\s*co)(?:\s*\(.*\))?$")

# Material/unidade que indicam urina (EAS, sedimento quantitativo, urocultura).
URINA_MATERIAL_RE = re.compile(r"urina|\beas\b|sedimento|urocultura|jato\s+medio")
URINA_UNIDADE_RE = re.compile(r"/\s*ml\b|/\s*campo|\bufc\b|p\s*/\s*ml|por\s+campo")
_PARA_URINA = {"leucocitos": "urina_leucocitos", "hemacias": "urina_hemacias"}


def e_generico(exame: str | None) -> bool:
    return bool(exame) and bool(GENERICO_RE.match(_normalizar(exame)))


def e_urina(material: str | None = None, unidade: str | None = None) -> bool:
    return bool(URINA_MATERIAL_RE.search(_normalizar(material or ""))
                or URINA_UNIDADE_RE.search(_normalizar(unidade or "")))


def identificar(exame: str | None, material: str | None = None, unidade: str | None = None) -> tuple[str, str, str]:
    """Retorna (id, nome de exibicao, sistema) para o titulo extraido do laudo.

    `material`/`unidade` separam leucocitos/hemacias da urina (EAS, sedimento,
    urocultura) dos do hemograma, que tem o mesmo nome.
    """
    mid, nome, sistema = _identificar(exame)
    if mid in _PARA_URINA and e_urina(material, unidade):
        alvo = _PARA_URINA[mid]
        return next((m, n, s) for m, n, s, _ in _COMPILADOS if m == alvo)
    return mid, nome, sistema


def _identificar(exame: str | None) -> tuple[str, str, str]:
    if not exame or exame == "Exame nao identificado":
        return ("nao_identificado", "Exame não identificado", "outros")
    texto = _normalizar(exame)
    if GENERICO_RE.match(texto):
        return ("sem_titulo", "Exame sem título", "outros")
    indice = INDICE_RE.match(texto)
    if indice:
        mid, nome, sistema = _identificar(indice.group("titulo"))
        return (f"{mid}_indice", f"{nome} (índice)", sistema)
    for mid, nome, sistema, padroes in _COMPILADOS:
        if any(p.search(texto) for p in padroes):
            return (mid, nome, sistema)
    return (_slug(exame), " ".join(exame.split()).title(), "outros")
