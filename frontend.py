#!/usr/bin/env python3
"""Painel privado para os resultados produzidos pelo analisador."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(page_title="Historico de exames", page_icon="🩺", layout="wide")
result_dir = Path(os.environ.get("ANALISADOR_RESULT_DIR", "resultado"))
catalog_path = result_dir / "catalogo.csv"
results_path = result_dir / "resultados.csv"

st.title("Histórico de exames")
st.caption("Organização automática para conferência. Não é diagnóstico médico.")

if not catalog_path.exists() or not results_path.exists():
    st.warning(f"Ainda não há análise em {result_dir.resolve()}. Execute o analisador primeiro.")
    st.stop()

catalog = pd.read_csv(catalog_path)
results = pd.read_csv(results_path)
catalog["data"] = pd.to_datetime(catalog["data"], errors="coerce")
results["data"] = pd.to_datetime(results["data"], errors="coerce")

c1, c2, c3, c4 = st.columns(4)
c1.metric("PDFs", len(catalog))
c2.metric("Resultados", len(results))
c3.metric("Sinalizados", int(results["classificacao"].isin(["acima", "abaixo"]).sum()))
c4.metric("Sem texto", int((~catalog["texto_extraido"].astype(bool)).sum()))

st.subheader("Resultados para conferência")
classes = st.multiselect(
    "Classificação",
    ["acima", "abaixo", "dentro", "nao determinado"],
    default=["acima", "abaixo"],
)
filtered = results[results["classificacao"].isin(classes)] if classes else results.iloc[0:0]
st.dataframe(
    filtered[["data", "exame", "valor_texto", "unidade", "classificacao", "arquivo"]]
    .sort_values("data", ascending=False),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Evolução de um marcador")
options = sorted(x for x in results["exame"].dropna().unique() if x != "Exame nao identificado")
if options:
    selected = st.selectbox("Exame", options)
    trend = results[(results["exame"] == selected) & results["valor_numerico"].notna()].copy()
    trend = trend.sort_values("data").set_index("data")
    if len(trend):
        st.line_chart(trend["valor_numerico"])
        st.dataframe(
            trend.reset_index()[["data", "valor_texto", "unidade", "referencia", "classificacao"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Não há valores numéricos suficientes para este marcador.")

st.subheader("Catálogo de documentos")
st.dataframe(
    catalog[["data", "tipo", "paginas", "arquivo"]].sort_values("data", ascending=False),
    use_container_width=True,
    hide_index=True,
)

with st.expander("Segurança e limites"):
    st.markdown(
        """
        - Confirme valores sinalizados no PDF original.
        - O painel não define atividade da artrite, diagnóstico ou tratamento.
        - Mantenha o serviço ligado somente a `127.0.0.1` e acesse por túnel SSH.
        - Não coloque exames nem a pasta de resultados no Git.
        """
    )
