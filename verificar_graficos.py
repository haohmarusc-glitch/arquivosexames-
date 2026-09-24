#!/usr/bin/env python3
"""Confere os dados que alimentam os gráficos do painel Minha Saúde."""
from __future__ import annotations
import argparse, base64, json, os, re, statistics, sys, urllib.request
from collections import Counter
NOMES_GENERICOS = {"indice", "índice", "resultado", "exame nao identificado", "exame não identificado", "valor"}
UNIDADE_VALIDA = re.compile(r"^[%\wµμ/³².^\-\s()]{1,20}$")
PALAVRAS_SUSPEITAS = re.compile(r"\b(sr|sra|dr|dra|paciente|nome|pagina|página)\b", re.I)
def classificar(valor, ref_min, ref_max):
    if valor is None or (ref_min is None and ref_max is None):
        return None
    if ref_min is not None and valor < ref_min:
        return "abaixo"
    if ref_max is not None and valor > ref_max:
        return "acima"
    return "dentro"
def carregar_api(base, user, senha):
    headers = {"Accept": "application/json"}
    if user:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{user}:{senha or ''}".encode()).decode()
    def get(path):
        req = urllib.request.Request(base.rstrip("/") + path, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    lista = get("/api/marcadores")
    return {m["id"]: {"resumo": m, "detalhe": get(f"/api/marcadores/{m['id']}")} for m in lista}
def verificar(dados):
    erros, avisos, sem_unidade = [], [], []
    for mid, bloco in dados.items():
        resumo, det = bloco["resumo"], bloco["detalhe"]
        nome = resumo.get("nome", mid)
        pontos = det.get("pontos", [])
        tag = f"{nome} ({mid})"
        if resumo.get("medicoes") != len(pontos):
            erros.append(f"{tag}: lista diz {resumo.get('medicoes')} medições, detalhe tem {len(pontos)}")
        if pontos:
            ult = pontos[-1]
            if ult.get("data") != resumo.get("ultima_data") or ult.get("valor") != resumo.get("ultimo_valor"):
                erros.append(f"{tag}: último ponto diverge da lista")
        datas = [p.get("data") for p in pontos]
        if datas != sorted(datas):
            erros.append(f"{tag}: pontos fora de ordem cronológica")
        rep = sorted(d for d, n in Counter(datas).items() if n > 1)
        if rep:
            erros.append(f"{tag}: mais de um ponto na mesma data: {', '.join(rep)}")
        if nome.strip().lower() in NOMES_GENERICOS or mid.strip().lower() in NOMES_GENERICOS:
            erros.append(f"{tag}: nome genérico — provavelmente junta exames diferentes")
        unidades = Counter((p.get("unidade") or "").strip() for p in pontos)
        if len(unidades) > 1:
            dom = unidades.most_common(1)[0][0]
            fora = [f"{p['data']}={p.get('valor_texto')}[{p.get('unidade') or '∅'}]" for p in pontos if (p.get("unidade") or "").strip() != dom]
            erros.append(f"{tag}: unidades misturadas {dict(unidades)} → fora do padrão: {'; '.join(fora)}")
        for u in unidades:
            if u and (not UNIDADE_VALIDA.match(u) or PALAVRAS_SUSPEITAS.search(u)):
                erros.append(f"{tag}: unidade suspeita '{u}' (parece texto do laudo)")
        if pontos and set(unidades) == {""}:
            sem_unidade.append(nome)
        positivos = [p["valor"] for p in pontos if isinstance(p.get("valor"), (int, float)) and p["valor"] > 0]
        if len(positivos) >= 4:
            med = statistics.median(positivos)
            for p in pontos:
                v = p.get("valor")
                # Dentro da faixa de referência do próprio laudo não é discrepante
                # (ex.: eosinófilos 0 com referência 0 a 460 /mm3).
                if classificar(v, p.get("ref_min"), p.get("ref_max")) == "dentro":
                    continue
                if isinstance(v, (int, float)) and (v > med * 10 or (v == 0 and med > 1)):
                    erros.append(f"{tag}: valor discrepante {p['data']} {p.get('valor_texto')} (mediana {med:g}) — arquivo {p.get('arquivo')}")
        for p in pontos:
            esp = classificar(p.get("valor"), p.get("ref_min"), p.get("ref_max"))
            if esp and p.get("classificacao") != esp:
                erros.append(f"{tag}: {p['data']} valor {p.get('valor')} ref {p.get('ref_min')}–{p.get('ref_max')} está '{p.get('classificacao')}', deveria ser '{esp}'")
            if p.get("ref_min") is not None and p.get("ref_max") is not None and p["ref_min"] > p["ref_max"]:
                erros.append(f"{tag}: {p['data']} faixa invertida {p['ref_min']}–{p['ref_max']}")
    if sem_unidade:
        avisos.append(f"{len(sem_unidade)} marcadores sem unidade: {', '.join(sorted(sem_unidade))}")
    return erros, avisos
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("SAUDE_BASE", "http://localhost:8000"))
    ap.add_argument("--user", default=os.environ.get("SAUDE_USER"))
    ap.add_argument("--senha", default=os.environ.get("SAUDE_SENHA"))
    ap.add_argument("--arquivo")
    a = ap.parse_args()
    dados = json.load(open(a.arquivo, encoding="utf-8")) if a.arquivo else carregar_api(a.base, a.user, a.senha)
    erros, avisos = verificar(dados)
    print(f"Marcadores verificados: {len(dados)}")
    for x in avisos: print("AVISO ", x)
    for x in erros: print("ERRO  ", x)
    print(f"\n{len(erros)} erro(s), {len(avisos)} aviso(s)")
    return 1 if erros else 0
if __name__ == "__main__":
    sys.exit(main())
