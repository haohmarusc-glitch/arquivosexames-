#!/usr/bin/env python3
"""API somente leitura para o painel React.

Le o resultados.json produzido pelo analisador e expoe endpoints agregados.
Deve rodar ligada a 127.0.0.1 e ser acessada por tunel SSH.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from mapa_exames import SISTEMAS, identificar

RESULT_DIR = Path(os.environ.get("ANALISADOR_RESULT_DIR", "resultado"))
FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"
NOME_TITULAR = os.environ.get("ANALISADOR_NOME", "")
FORA = {"acima", "abaixo"}

app = FastAPI(title="Painel de exames", docs_url=None, redoc_url=None, openapi_url=None)

_cache: dict[str, Any] = {"mtime": None, "dados": None}
_lock = Lock()


def _enriquecer(r: dict[str, Any]) -> dict[str, Any]:
    """Aceita JSONs antigos (sem exame_id/ref_min) recalculando o que faltar."""
    if not r.get("exame_id"):
        r["exame_id"], r["exame_nome"], r["sistema"] = identificar(r.get("exame"))
    r.setdefault("ref_min", None)
    r.setdefault("ref_max", None)
    return r


def carregar() -> dict[str, Any]:
    caminho = RESULT_DIR / "resultados.json"
    if not caminho.exists():
        raise HTTPException(404, f"Nenhuma análise encontrada em {RESULT_DIR}. Execute o analisador primeiro.")
    mtime = caminho.stat().st_mtime
    with _lock:
        if _cache["mtime"] != mtime:
            bruto = json.loads(caminho.read_text(encoding="utf-8"))
            bruto["resultados"] = [_enriquecer(r) for r in bruto.get("resultados", [])]
            _cache.update(mtime=mtime, dados=bruto, gerado_em=mtime)
        return _cache["dados"]


def _ultimos_por_marcador(resultados: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    ultimos: dict[str, dict[str, Any]] = {}
    for r in resultados:
        if r["exame_id"] == "nao_identificado" or r.get("valor_numerico") is None:
            continue
        atual = ultimos.get(r["exame_id"])
        if atual is None or (r.get("data") or "") >= (atual.get("data") or ""):
            ultimos[r["exame_id"]] = r
    return ultimos


def _status_documento(n_resultados: int, n_fora: int, tipo: str) -> str:
    if tipo != "laboratorial":
        return "sem_valores"
    if n_resultados == 0:
        return "sem_valores"
    return "atencao" if n_fora else "normal"


def _unicos(dados: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in dados.get("arquivos", []) if a.get("tipo") != "duplicado"]


@app.get("/api/resumo")
def resumo() -> dict[str, Any]:
    dados = carregar()
    todos = dados.get("arquivos", [])
    arquivos, resultados = _unicos(dados), dados["resultados"]
    datas = sorted(a["data"] for a in arquivos if a.get("data"))
    ultima_data = datas[-1] if datas else None
    do_ultimo = [r for r in resultados if r.get("data") == ultima_data]
    ultimos = _ultimos_por_marcador(resultados)
    atencao = sorted(
        (
            {
                "id": r["exame_id"],
                "nome": r["exame_nome"],
                "valor": r["valor_numerico"],
                "unidade": r.get("unidade", ""),
                "classificacao": r["classificacao"],
                "data": r.get("data"),
            }
            for r in ultimos.values()
            if r["classificacao"] in FORA
        ),
        key=lambda x: x["nome"],
    )
    return {
        "titular": NOME_TITULAR,
        "gerado_em": _cache.get("gerado_em"),
        "total_documentos": len(arquivos),
        "total_resultados": len(resultados),
        "total_marcadores": len(ultimos),
        "sem_texto": sum(1 for a in arquivos if not a.get("texto_extraido")),
        "erros": len(dados.get("erros", [])),
        "duplicados": sum(1 for a in todos if a.get("tipo") == "duplicado"),
        "nome_divergente": sum(1 for a in arquivos if a.get("aviso")),
        "periodo": {"inicio": datas[0] if datas else None, "fim": ultima_data},
        "ultimo_exame": {
            "data": ultima_data,
            "marcadores": len({r["exame_id"] for r in do_ultimo}),
            "arquivos": sorted({r["arquivo"] for r in do_ultimo}),
        },
        "atencao": atencao,
    }


@app.get("/api/documentos")
def documentos() -> list[dict[str, Any]]:
    dados = carregar()
    por_arquivo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in dados["resultados"]:
        por_arquivo[r["arquivo"]].append(r)
    achados_por_arquivo: dict[str, set[str]] = defaultdict(set)
    for a in dados.get("achados", []):
        achados_por_arquivo[a["arquivo"]].add(a["regiao"])
    saida = []
    for a in _unicos(dados):
        rs = por_arquivo.get(a["arquivo"], [])
        fora = [r for r in rs if r["classificacao"] in FORA]
        saida.append(
            {
                "arquivo": a["arquivo"],
                "data": a.get("data"),
                "tipo": a.get("tipo"),
                "paginas": a.get("paginas"),
                "texto_extraido": a.get("texto_extraido"),
                "resultados": len(rs),
                "fora": len(fora),
                "sistemas": sorted({r["sistema"] for r in rs if r["sistema"] != "outros"}),
                "regioes": sorted(achados_por_arquivo.get(a["arquivo"], set())),
                "aviso": a.get("aviso", ""),
                "status": "achados" if achados_por_arquivo.get(a["arquivo"]) else _status_documento(len(rs), len(fora), a.get("tipo", "")),
            }
        )
    return sorted(saida, key=lambda d: d.get("data") or "", reverse=True)


@app.get("/api/marcadores")
def marcadores() -> list[dict[str, Any]]:
    dados = carregar()
    contagem: dict[str, int] = defaultdict(int)
    for r in dados["resultados"]:
        if r.get("valor_numerico") is not None:
            contagem[r["exame_id"]] += 1
    saida = [
        {
            "id": mid,
            "nome": r["exame_nome"],
            "sistema": r["sistema"],
            "unidade": r.get("unidade", ""),
            "medicoes": contagem[mid],
            "ultimo_valor": r["valor_numerico"],
            "ultima_data": r.get("data"),
            "classificacao": r["classificacao"],
        }
        for mid, r in _ultimos_por_marcador(dados["resultados"]).items()
    ]
    return sorted(saida, key=lambda m: (-m["medicoes"], m["nome"]))


@app.get("/api/marcadores/{marcador_id}")
def serie(marcador_id: str) -> dict[str, Any]:
    dados = carregar()
    pontos = [
        {
            "data": r.get("data"),
            "valor": r["valor_numerico"],
            "valor_texto": r.get("valor_texto"),
            "unidade": r.get("unidade", ""),
            "ref_min": r.get("ref_min"),
            "ref_max": r.get("ref_max"),
            "referencia": r.get("referencia", ""),
            "classificacao": r["classificacao"],
            "arquivo": r["arquivo"],
        }
        for r in dados["resultados"]
        if r["exame_id"] == marcador_id and r.get("valor_numerico") is not None and r.get("data")
    ]
    if not pontos:
        raise HTTPException(404, "Marcador sem valores numéricos datados.")
    pontos.sort(key=lambda p: p["data"])
    exemplo = next(r for r in dados["resultados"] if r["exame_id"] == marcador_id)
    return {"id": marcador_id, "nome": exemplo["exame_nome"], "sistema": exemplo["sistema"], "pontos": pontos}


@app.get("/api/sistemas")
def sistemas() -> list[dict[str, Any]]:
    ultimos = _ultimos_por_marcador(carregar()["resultados"])
    agregados: dict[str, dict[str, Any]] = {
        sid: {"id": sid, "nome": nome, "marcadores": 0, "fora": 0} for sid, nome in SISTEMAS.items()
    }
    for r in ultimos.values():
        s = agregados[r["sistema"] if r["sistema"] in agregados else "outros"]
        s["marcadores"] += 1
        s["fora"] += r["classificacao"] in FORA
    return list(agregados.values())


REGIOES_VALIDAS = {
    "cervical", "toracica", "lombar", "sacral", "ombro", "cotovelo", "punho_mao",
    "quadril", "joelho", "tornozelo_pe", "renal", "escrotal", "prostata", "parede_abdominal", "outros",
}


def _achados_manuais() -> list[dict[str, Any]]:
    """Le RESULT_DIR/achados_manuais.json (opcional), editado a mao no servidor."""
    caminho = RESULT_DIR / "achados_manuais.json"
    if not caminho.exists():
        return []
    try:
        itens = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(500, f"achados_manuais.json invalido: linha {exc.lineno}, coluna {exc.colno}.") from exc
    saida = []
    for item in itens if isinstance(itens, list) else []:
        regiao = item.get("regiao", "outros")
        saida.append(
            {
                "arquivo": item.get("fonte", "registro manual"),
                "data": item.get("data"),
                "modalidade": item.get("tipo", "registro manual"),
                "regiao": regiao if regiao in REGIOES_VALIDAS else "outros",
                "niveis": [str(n).upper() for n in item.get("niveis", [])],
                "niveis_historicos": [str(n).upper() for n in item.get("niveis_historicos", [])],
                "termos": item.get("termos", []),
                "lado": item.get("lado", ""),
                "titulo": item.get("titulo", ""),
                "trecho": item.get("descricao", ""),
                "origem": "manual",
            }
        )
    return saida


@app.get("/api/achados")
def achados() -> list[dict[str, Any]]:
    dados = carregar()
    # Achados gerados por uma versao mais antiga do analisador podem nao ter
    # "niveis_historicos" (campo adicionado depois): sem o default aqui, o
    # frontend quebra a pagina inteira ao tentar ler esse campo ausente.
    todos = [dict(a, titulo="", niveis_historicos=a.get("niveis_historicos", [])) for a in dados.get("achados", [])] + _achados_manuais()
    return sorted(todos, key=lambda a: a.get("data") or "", reverse=True)


# Frontend compilado (npm run build). Em desenvolvimento, o Vite serve o frontend.
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str) -> FileResponse:
        arquivo = (FRONTEND_DIST / caminho).resolve()
        if caminho and arquivo.is_file() and FRONTEND_DIST.resolve() in arquivo.parents:
            return FileResponse(arquivo)
        return FileResponse(FRONTEND_DIST / "index.html")
