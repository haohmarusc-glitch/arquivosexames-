#!/usr/bin/env python3
"""Gera um resultados.json FICTICIO para desenvolver o painel sem dados reais.

Uso: python exemplo/gerar_demo.py  -> cria exemplo/demo/resultados.json
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from achados import extrair_achados  # noqa: E402
from mapa_exames import identificar  # noqa: E402
from dataclasses import asdict  # noqa: E402
import shutil  # noqa: E402

random.seed(7)

DATAS = ["2022-03-14", "2022-09-02", "2023-02-20", "2023-10-12", "2024-04-08", "2024-11-21", "2025-06-10", "2026-03-05"]

# titulo no laudo, unidade, ref_min, ref_max, valor inicial, deriva por coleta
MARCADORES = [
    ("COLESTEROL TOTAL", "mg/dL", None, 190, 178, 4.5),
    ("COLESTEROL LDL", "mg/dL", None, 130, 112, 4.0),
    ("COLESTEROL HDL", "mg/dL", 40, None, 46, -0.6),
    ("TRIGLICERIDEOS", "mg/dL", None, 150, 128, 3.5),
    ("GLICOSE", "mg/dL", 70, 99, 91, 1.1),
    ("HEMOGLOBINA GLICADA", "%", 4.0, 5.6, 5.3, 0.05),
    ("TGO - ASPARTATO AMINOTRANSFERASE", "U/L", 5, 40, 26, 1.2),
    ("TGP - ALANINA AMINOTRANSFERASE", "U/L", 7, 41, 31, 1.8),
    ("GAMA GT", "U/L", 8, 61, 44, 2.0),
    ("BILIRRUBINA TOTAL", "mg/dL", 0.2, 1.2, 0.7, 0.02),
    ("CREATININA", "mg/dL", 0.7, 1.3, 1.0, 0.01),
    ("UREIA", "mg/dL", 15, 45, 32, 0.4),
    ("TSH", "µUI/mL", 0.4, 4.5, 2.1, 0.05),
    ("T4 LIVRE", "ng/dL", 0.9, 1.8, 1.2, 0.0),
    ("HEMOGLOBINA", "g/dL", 13.5, 17.5, 15.1, -0.05),
    ("LEUCOCITOS", "/mm³", 4000, 11000, 6500, 20),
    ("PLAQUETAS", "mil/mm³", 150, 450, 240, -1),
    ("PROTEINA C REATIVA", "mg/L", None, 5.0, 2.4, 0.2),
    ("VITAMINA D - 25 HIDROXI", "ng/mL", 30, 100, 34, -0.8),
    ("VITAMINA B12", "pg/mL", 200, 900, 410, 5),
]


def ref_texto(lo: float | None, hi: float | None, un: str) -> str:
    fmt = lambda x: f"{x:g}".replace(".", ",")  # noqa: E731
    if lo is None:
        return f"Valor de referencia: inferior a {fmt(hi)} {un}"
    if hi is None:
        return f"Valor de referencia: superior a {fmt(lo)} {un}"
    return f"Valor de referencia: {fmt(lo)} a {fmt(hi)} {un}"


def classificar(v: float, lo: float | None, hi: float | None) -> str:
    if lo is not None and v < lo:
        return "abaixo"
    if hi is not None and v > hi:
        return "acima"
    return "dentro"


arquivos, resultados = [], []
for i, data in enumerate(DATAS):
    nome = f"{data}_Laboratorial_DEMO.pdf"
    arquivos.append({"arquivo": nome, "data": data, "tipo": "laboratorial", "paginas": random.randint(3, 9), "sha256": "demo", "texto_extraido": True})
    for titulo, un, lo, hi, v0, deriva in MARCADORES:
        if i % 2 and titulo.startswith(("VITAMINA", "T4", "PROTEINA")):
            continue  # nem toda coleta tem todos os exames
        ruido = random.uniform(-1, 1) * abs(v0) * 0.04
        v = round(v0 + deriva * i + ruido, 2 if v0 < 10 else 0)
        mid, mnome, sis = identificar(titulo)
        resultados.append({
            "arquivo": nome, "data": data, "exame": titulo,
            "valor_texto": f"{v:g} {un}".replace(".", ","), "valor_numerico": v, "unidade": un,
            "referencia": ref_texto(lo, hi, un), "ref_min": lo, "ref_max": hi,
            "classificacao": classificar(v, lo, hi), "exame_id": mid, "exame_nome": mnome, "sistema": sis,
        })

LAUDOS_IMAGEM = [
    ("2023-06-30_Ressonancia_joelho_DEMO.pdf", "2023-06-30",
     "RESSONANCIA MAGNETICA DO JOELHO ESQUERDO\nCONCLUSAO:\nLesao degenerativa do corno posterior do menisco medial. Pequeno derrame articular."),
    ("2024-09-18_Ressonancia_coluna_toracica_DEMO.pdf", "2024-09-18",
     "RESSONANCIA MAGNETICA DA COLUNA TORACICA\nIMPRESSAO DIAGNOSTICA:\nDiscretas alteracoes degenerativas T7-T8 e T8-T9, sem compressao medular."),
    ("2025-01-15_Ultrassonografia_ombro_DEMO.pdf", "2025-01-15",
     "ULTRASSONOGRAFIA DO OMBRO DIREITO\nIMPRESSAO:\nTendinopatia do supraespinhal, sem ruptura."),
]
achados = []
for nome, data, texto in LAUDOS_IMAGEM:
    arquivos.append({"arquivo": nome, "data": data, "tipo": "imagem", "paginas": 2, "sha256": "demo", "texto_extraido": True})
    achados += [asdict(a) for a in extrair_achados(nome, data, texto)]
arquivos.append({"arquivo": "2022-11-02_Radiografia_torax_DEMO.pdf", "data": "2022-11-02", "tipo": "imagem", "paginas": 1, "sha256": "demo", "texto_extraido": False})

saida = Path(__file__).parent / "demo"
saida.mkdir(exist_ok=True)
payload = {"aviso": "DADOS FICTICIOS PARA DESENVOLVIMENTO.", "arquivos": arquivos, "resultados": resultados, "achados": achados, "erros": []}
(saida / "resultados.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
shutil.copy(Path(__file__).parent / "achados_manuais.exemplo.json", saida / "achados_manuais.json")
print(f"Demo: {len(arquivos)} documentos, {len(resultados)} resultados -> {saida / 'resultados.json'}")
