#!/usr/bin/env python3
"""API do painel React.

Le o resultados.json produzido pelo analisador e expoe endpoints agregados.
Opcionalmente (ANALISADOR_UPLOAD_DIR definido) aceita envio de PDFs pelo
painel: cada PDF passa pelo mesmo analisador e o resultado fica num arquivo
separado (resultados_upload.json), mesclado na leitura. O resultados.json
principal continua somente leitura (volume :ro no Docker).
"""

from __future__ import annotations

import json
import os
import io
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

import analisar_exames
from mapa_exames import SISTEMAS, identificar

RESULT_DIR = Path(os.environ.get("ANALISADOR_RESULT_DIR", "resultado"))
UPLOAD_DIR = Path(os.environ["ANALISADOR_UPLOAD_DIR"]) if os.environ.get("ANALISADOR_UPLOAD_DIR") else None
MAX_UPLOAD = int(os.environ.get("ANALISADOR_UPLOAD_MAX_MB", "25")) * 1024 * 1024
analisar_exames.PERFIL["sexo"] = os.environ.get("ANALISADOR_SEXO") or None
FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"
NOME_TITULAR = os.environ.get("ANALISADOR_NOME", "")
FORA = {"acima", "abaixo"}

app = FastAPI(title="Painel de exames", docs_url=None, redoc_url=None, openapi_url=None)

_cache: dict[str, Any] = {"mtime": None, "dados": None}
_lock = Lock()


def _enriquecer(r: dict[str, Any]) -> dict[str, Any]:
    """Recalcula id/nome/sistema a partir do titulo extraido: assim uma mudanca
    no mapa_exames.py (ex.: exame que saiu de "Outros") vale na hora, sem
    precisar rodar o analisador de novo sobre todos os PDFs."""
    if r.get("exame"):
        r["exame_id"], r["exame_nome"], r["sistema"] = identificar(r.get("exame"))
    elif not r.get("exame_id"):
        r["exame_id"], r["exame_nome"], r["sistema"] = identificar(None)
    r.setdefault("ref_min", None)
    r.setdefault("ref_max", None)
    return r


def _arquivo_upload() -> Path | None:
    return UPLOAD_DIR / "resultados_upload.json" if UPLOAD_DIR else None


def _ler_upload() -> dict[str, Any]:
    caminho = _arquivo_upload()
    if not caminho or not caminho.exists():
        return {"arquivos": [], "resultados": [], "achados": []}
    return json.loads(caminho.read_text(encoding="utf-8"))


def _mesclar(principal: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    """Junta os envios pelo painel ao resultado principal, ignorando PDFs que o
    analisador principal ja processou (mesmo sha256, mesmo texto ou mesmo nome)."""
    base = principal.get("arquivos", [])
    shas = {a.get("sha256") for a in base}
    textos = {a.get("hash_texto") for a in base if a.get("hash_texto")}
    nomes = {a.get("arquivo") for a in base}
    aceitos = {
        a["arquivo"] for a in extra.get("arquivos", [])
        if a.get("sha256") not in shas and a.get("hash_texto") not in textos and a["arquivo"] not in nomes
    }
    saida = dict(principal)
    saida["arquivos"] = base + [dict(a, origem="upload") for a in extra.get("arquivos", []) if a["arquivo"] in aceitos]
    saida["resultados"] = principal.get("resultados", []) + [r for r in extra.get("resultados", []) if r["arquivo"] in aceitos]
    saida["achados"] = principal.get("achados", []) + [a for a in extra.get("achados", []) if a["arquivo"] in aceitos]
    return saida


def carregar() -> dict[str, Any]:
    caminho = RESULT_DIR / "resultados.json"
    extra = _arquivo_upload()
    tem_extra = bool(extra and extra.exists())
    if not caminho.exists() and not tem_extra:
        raise HTTPException(404, f"Nenhuma análise encontrada em {RESULT_DIR}. Execute o analisador ou envie um PDF pelo painel.")
    mtime = (caminho.stat().st_mtime if caminho.exists() else 0, extra.stat().st_mtime if tem_extra else 0)
    with _lock:
        if _cache["mtime"] != mtime:
            bruto = json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {"arquivos": [], "resultados": [], "achados": [], "erros": []}
            bruto = _mesclar(bruto, _ler_upload())
            bruto["resultados"] = [_enriquecer(r) for r in bruto.get("resultados", [])]
            _cache.update(mtime=mtime, dados=bruto, gerado_em=max(mtime))
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
                "origem": a.get("origem", "analisador"),
                "pdf": _achar_pdf(a["arquivo"]) is not None,
                "status": "achados" if achados_por_arquivo.get(a["arquivo"]) else _status_documento(len(rs), len(fora), a.get("tipo", "")),
            }
        )
    return sorted(saida, key=lambda d: d.get("data") or "", reverse=True)


# ------------------------------------------------------------------ PDFs (abrir / baixar / imprimir)

# Pastas onde procurar o PDF original de cada documento: os enviados pelo painel
# e, opcionalmente, outras pastas (somente leitura) separadas por ":".
PDF_DIRS = ([UPLOAD_DIR / "pdfs"] if UPLOAD_DIR else []) + [
    Path(x) for x in os.environ.get("ANALISADOR_PDF_DIR", "").split(":") if x.strip()
]
_cache_pdfs: dict[str, Any] = {"quando": 0.0, "indice": {}}


def _indice_pdfs() -> dict[str, Path]:
    """nome do arquivo -> caminho real. So entram arquivos dentro das pastas
    configuradas, entao o endpoint nunca serve nada fora delas."""
    agora = time.time()
    if agora - _cache_pdfs["quando"] < 30:
        return _cache_pdfs["indice"]
    indice: dict[str, Path] = {}
    for pasta in PDF_DIRS:
        if not pasta.is_dir():
            continue
        for arq in pasta.rglob("*"):
            if arq.is_file() and arq.suffix.lower() == ".pdf" and not arq.name.startswith("."):
                indice.setdefault(arq.name, arq)
    _cache_pdfs.update(quando=agora, indice=indice)
    return indice


def _achar_pdf(arquivo: str) -> Path | None:
    return _indice_pdfs().get(Path(arquivo or "").name)


@app.get("/api/documentos/{arquivo}/pdf")
def baixar_pdf(arquivo: str, baixar: bool = False) -> FileResponse:
    caminho = _achar_pdf(arquivo)
    if caminho is None:
        raise HTTPException(404, "O PDF original desse documento não está guardado no servidor.")
    return FileResponse(
        caminho,
        media_type="application/pdf",
        filename=caminho.name,
        content_disposition_type="attachment" if baixar else "inline",
    )


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


# ------------------------------------------------------------------ Upload

_NOME_SEGURO = re.compile(r"[^A-Za-z0-9._-]+")
_lock_upload = Lock()


def _nome_seguro(nome: str) -> str:
    base = Path(nome or "exame.pdf").name
    base = _NOME_SEGURO.sub("_", base).strip("._") or "exame"
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
    return base[-120:]


def _gravar_json(caminho: Path, dados: dict[str, Any]) -> None:
    """Escrita atomica: um erro no meio nao deixa o arquivo pela metade."""
    fd, tmp = tempfile.mkstemp(dir=caminho.parent, prefix=".upload-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, caminho)


def _resumo_envio(item: dict[str, Any], resultados: list[dict[str, Any]], achados: list[dict[str, Any]]) -> dict[str, Any]:
    por_sistema: dict[str, list[str]] = defaultdict(list)
    fora = 0
    for r in resultados:
        mid, nome, sistema = identificar(r.get("exame"))
        if mid == "nao_identificado":
            continue
        if nome not in por_sistema[sistema]:
            por_sistema[sistema].append(nome)
        fora += r.get("classificacao") in FORA
    return {
        "arquivo": item["arquivo"],
        "status": "adicionado",
        "tipo": item.get("tipo"),
        "data": item.get("data"),
        "resultados": len(resultados),
        "fora": fora,
        "sistemas": [{"id": sid, "nome": SISTEMAS.get(sid, sid), "marcadores": nomes} for sid, nomes in sorted(por_sistema.items())],
        "regioes": sorted({a.get("regiao", "outros") for a in achados}),
        "aviso": item.get("aviso", ""),
    }


@app.get("/api/upload")
def upload_status() -> dict[str, Any]:
    return {"habilitado": UPLOAD_DIR is not None, "limite_mb": MAX_UPLOAD // (1024 * 1024)}


# Limites para ZIPs enviados pelo painel (protecao contra "zip bomb").
MAX_ZIP_MEMBROS = 500
MAX_ZIP_TOTAL = int(os.environ.get("ANALISADOR_ZIP_MAX_MB", "300")) * 1024 * 1024
_EXT_IMAGEM = (".dcm", ".dicom", ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic")


def _motivo_recusa(nome: str, conteudo: bytes) -> str:
    """Mensagem clara para arquivos que nao sao PDF nem ZIP."""
    baixo = nome.lower()
    if conteudo[128:132] == b"DICM" or baixo.endswith((".dcm", ".dicom")):
        return "Imagem DICOM (raio-X, ressonância…): o painel lê só o texto dos laudos. Envie o PDF do laudo desse exame."
    if baixo.endswith(_EXT_IMAGEM):
        return "Foto/imagem não é lida. Envie o laudo em PDF."
    if baixo.endswith((".doc", ".docx", ".odt", ".txt", ".rtf")):
        return "Formato de documento não suportado. Salve/exporte como PDF e envie de novo."
    return "Formato não suportado. Envie PDF de laudo ou um .zip com PDFs dentro."


def _expandir(nome: str, conteudo: bytes) -> tuple[list[tuple[str, bytes]], list[dict[str, Any]]]:
    """Transforma um arquivo enviado em uma lista de PDFs (nome, bytes).

    - PDF: ele mesmo.
    - ZIP: todos os PDFs de dentro (inclusive em subpastas e em ZIPs dentro do
      ZIP, um nivel). Outros arquivos do ZIP sao ignorados e contados.
    - Outros: vira um erro com explicacao.
    """
    if conteudo.startswith(b"%PDF"):
        return [(nome, conteudo)], []
    if not conteudo.startswith(b"PK"):
        return [], [{"arquivo": nome, "status": "erro", "erro": _motivo_recusa(nome, conteudo)}]

    pdfs: list[tuple[str, bytes]] = []
    erros: list[dict[str, Any]] = []
    ignorados = dicom = 0

    def ler_zip(dados: bytes, profundidade: int) -> None:
        nonlocal ignorados, dicom
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            membros = [m for m in z.infolist() if not m.is_dir()]
            if len(membros) > MAX_ZIP_MEMBROS:
                raise ValueError(f"ZIP com arquivos demais (máximo {MAX_ZIP_MEMBROS}).")
            if sum(m.file_size for m in membros) > MAX_ZIP_TOTAL:
                raise ValueError(f"ZIP grande demais depois de descompactado (máximo {MAX_ZIP_TOTAL // (1024 * 1024)} MB).")
            for m in membros:
                base = Path(m.filename).name
                baixo = base.lower()
                if base.startswith(".") or "__MACOSX" in m.filename:
                    continue
                if baixo.endswith(".pdf"):
                    if m.file_size > MAX_UPLOAD:
                        erros.append({"arquivo": base, "status": "erro", "erro": f"PDF maior que {MAX_UPLOAD // (1024 * 1024)} MB dentro do ZIP."})
                    else:
                        pdfs.append((base, z.read(m)))
                elif baixo.endswith(".zip") and profundidade == 0 and m.file_size <= MAX_ZIP_TOTAL:
                    ler_zip(z.read(m), 1)
                elif baixo.endswith((".dcm", ".dicom")) or "." not in base:
                    dicom += 1  # DICOM costuma vir sem extensao
                else:
                    ignorados += 1

    try:
        ler_zip(conteudo, 0)
    except (zipfile.BadZipFile, ValueError, RuntimeError) as exc:
        msg = str(exc) if isinstance(exc, ValueError) else "ZIP corrompido ou protegido por senha."
        return [], [{"arquivo": nome, "status": "erro", "erro": msg}]

    if not pdfs and not erros:
        if dicom:
            erro = "Esse ZIP só tem imagens DICOM (raio-X, ressonância…), sem laudo em PDF. O painel lê o texto dos laudos — envie o PDF do laudo."
        else:
            erro = "Nenhum PDF encontrado dentro do ZIP."
        erros.append({"arquivo": nome, "status": "erro", "erro": erro})
    elif dicom or ignorados:
        partes = []
        if dicom:
            partes.append(f"{dicom} imagem(ns) DICOM")
        if ignorados:
            partes.append(f"{ignorados} arquivo(s) que não são PDF")
        erros.append({"arquivo": nome, "status": "info", "erro": f"{len(pdfs)} PDF(s) lidos do ZIP; ignorados: {', '.join(partes)}."})
    return pdfs, erros


@app.post("/api/upload")
async def upload(arquivos: list[UploadFile] = File(...)) -> dict[str, Any]:
    if UPLOAD_DIR is None:
        raise HTTPException(503, "Envio desabilitado: defina ANALISADOR_UPLOAD_DIR (pasta gravável) no container.")
    pasta_pdfs = UPLOAD_DIR / "pdfs"
    pasta_pdfs.mkdir(parents=True, exist_ok=True, mode=0o700)
    saida: list[dict[str, Any]] = []

    with _lock_upload:
        atual = carregar() if (RESULT_DIR / "resultados.json").exists() or _arquivo_upload().exists() else {"arquivos": []}
        extra = _ler_upload()
        vistos = {a["hash_texto"]: a["arquivo"] for a in atual.get("arquivos", []) if a.get("hash_texto")}
        shas = {a.get("sha256"): a["arquivo"] for a in atual.get("arquivos", [])}
        nomes = {a["arquivo"] for a in atual.get("arquivos", [])}
        mudou = False

        for enviado in arquivos:
            original = Path(enviado.filename or "arquivo").name
            conteudo = await enviado.read(MAX_UPLOAD + 1)
            if len(conteudo) > MAX_UPLOAD:
                saida.append({"arquivo": original, "status": "erro", "erro": f"Arquivo maior que {MAX_UPLOAD // (1024 * 1024)} MB."})
                continue
            pdfs, avisos = _expandir(original, conteudo)
            saida.extend(avisos)
            for nome_pdf, dados in pdfs:
                nome = _nome_seguro(nome_pdf)
                if not dados.startswith(b"%PDF"):
                    saida.append({"arquivo": nome, "status": "erro", "erro": "O arquivo tem extensão .pdf mas não é um PDF válido."})
                    continue
                fd, tmp = tempfile.mkstemp(dir=pasta_pdfs, prefix=".envio-", suffix=".pdf")
                os.write(fd, dados)
                os.close(fd)
                tmp_path = Path(tmp)
                try:
                    digest = analisar_exames.sha256(tmp_path)
                    if digest in shas:
                        saida.append({"arquivo": nome, "status": "duplicado", "igual_a": shas[digest]})
                        tmp_path.unlink()
                        continue
                    # Mesmo nome com conteudo diferente: acrescenta sufixo em vez de sobrescrever.
                    final = nome
                    n = 2
                    while final in nomes or (pasta_pdfs / final).exists():
                        final = f"{Path(nome).stem}_{n}.pdf"
                        n += 1
                    item, resultados, achados_pdf = analisar_exames.analisar_pdf(tmp_path, vistos, nome=final)
                    if item.tipo == "duplicado":
                        saida.append({"arquivo": nome, "status": "duplicado", "igual_a": item.duplicado_de})
                        tmp_path.unlink()
                        continue
                    os.replace(tmp_path, pasta_pdfs / final)
                    os.chmod(pasta_pdfs / final, 0o600)
                    reg, res, ach = asdict(item), [asdict(r) for r in resultados], [asdict(a) for a in achados_pdf]
                    extra.setdefault("arquivos", []).append(reg)
                    extra.setdefault("resultados", []).extend(res)
                    extra.setdefault("achados", []).extend(ach)
                    shas[digest] = final
                    nomes.add(final)
                    mudou = True
                    saida.append(_resumo_envio(reg, res, ach))
                except Exception as exc:  # layout inesperado nao derruba o envio dos demais
                    tmp_path.unlink(missing_ok=True)
                    saida.append({"arquivo": nome, "status": "erro", "erro": f"Não foi possível ler o PDF ({type(exc).__name__})."})

        if mudou:
            _gravar_json(_arquivo_upload(), extra)  # type: ignore[arg-type]
    return {"envios": saida}


@app.delete("/api/upload/{arquivo}")
def remover_upload(arquivo: str) -> dict[str, Any]:
    """Remove um PDF enviado pelo painel (so os enviados; o resultado principal nao e tocado)."""
    if UPLOAD_DIR is None:
        raise HTTPException(503, "Envio desabilitado.")
    with _lock_upload:
        extra = _ler_upload()
        if not any(a["arquivo"] == arquivo for a in extra.get("arquivos", [])):
            raise HTTPException(404, "Esse documento não foi enviado pelo painel.")
        for chave in ("arquivos", "resultados", "achados"):
            extra[chave] = [x for x in extra.get(chave, []) if x.get("arquivo") != arquivo]
        _gravar_json(_arquivo_upload(), extra)  # type: ignore[arg-type]
        pdf = (UPLOAD_DIR / "pdfs" / _nome_seguro(arquivo))
        if pdf.resolve().parent == (UPLOAD_DIR / "pdfs").resolve():
            pdf.unlink(missing_ok=True)
    return {"removido": arquivo}


# ------------------------------------------------------------------ Imagens (Orthanc)

ORTHANC_URL = os.environ.get("ORTHANC_URL", "").rstrip("/")
_cache_imagens: dict[str, Any] = {"quando": 0.0, "dados": None}


def _orthanc_get(caminho: str) -> Any:
    with urllib.request.urlopen(ORTHANC_URL + caminho, timeout=10) as r:
        return json.loads(r.read())


def _data_dicom(valor: str | None) -> str | None:
    v = (valor or "").strip()
    return f"{v[:4]}-{v[4:6]}-{v[6:8]}" if len(v) >= 8 and v[:8].isdigit() else None


@app.get("/api/imagens")
def imagens() -> dict[str, Any]:
    """Estudos de imagem guardados no Orthanc, com o link do visualizador OHIF
    e os laudos do painel com a mesma data. Nao devolve nada do paciente."""
    if not ORTHANC_URL:
        return {"habilitado": False, "estudos": []}
    agora = time.time()
    if _cache_imagens["dados"] is not None and agora - _cache_imagens["quando"] < 30:
        return _cache_imagens["dados"]
    try:
        estudos = _orthanc_get("/studies?expand")
        series = _orthanc_get("/series?expand")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"habilitado": True, "erro": f"Servidor de imagens indisponível ({type(exc).__name__}).", "estudos": []}

    series_por_estudo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for se in series:
        tags = se.get("MainDicomTags", {})
        series_por_estudo[se.get("ParentStudy")].append(
            {"modalidade": tags.get("Modality", ""), "descricao": tags.get("SeriesDescription", ""), "imagens": len(se.get("Instances", []))}
        )
    try:
        docs = documentos()
    except Exception:  # sem resultados.json ainda: imagens continuam funcionando
        docs = []
    laudos_por_data: dict[str, list[str]] = defaultdict(list)
    for d in docs:
        if d.get("data"):
            laudos_por_data[d["data"]].append(d["arquivo"])

    saida = []
    for es in estudos:
        tags = es.get("MainDicomTags", {})
        uid = tags.get("StudyInstanceUID", "")
        data = _data_dicom(tags.get("StudyDate"))
        ss = series_por_estudo.get(es.get("ID"), [])
        saida.append({
            "id": es.get("ID"),
            "data": data,
            "descricao": tags.get("StudyDescription", "") or ", ".join(sorted({s["descricao"] for s in ss if s["descricao"]}))[:120],
            "modalidades": sorted({s["modalidade"] for s in ss if s["modalidade"]}),
            "series": len(ss),
            "imagens": sum(s["imagens"] for s in ss),
            "visualizador": f"/ohif/viewer?StudyInstanceUIDs={urllib.parse.quote(uid)}",
            "laudos": laudos_por_data.get(data or "", []),
        })
    resposta = {"habilitado": True, "estudos": sorted(saida, key=lambda e: e["data"] or "", reverse=True)}
    _cache_imagens.update(quando=agora, dados=resposta)
    return resposta


_ID_ORTHANC = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{8}){4}$")


def _validar_id(ident: str) -> str:
    if not ORTHANC_URL:
        raise HTTPException(503, "Servidor de imagens não configurado.")
    if not _ID_ORTHANC.match(ident or ""):
        raise HTTPException(404, "Exame não encontrado.")
    return ident


def _numero(v: Any) -> float:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return 1e9


@app.get("/api/imagens/{estudo}/series")
def series_do_estudo(estudo: str) -> dict[str, Any]:
    """Series e imagens (em ordem) de um exame, para a pagina de impressao."""
    _validar_id(estudo)
    try:
        info = _orthanc_get(f"/studies/{estudo}")
        series = _orthanc_get(f"/studies/{estudo}/series")
        saida = []
        for se in sorted(series, key=lambda x: _numero(x.get("MainDicomTags", {}).get("SeriesNumber"))):
            instancias = _orthanc_get(f"/series/{se['ID']}/instances")
            ordem = sorted(instancias, key=lambda i: _numero(i.get("MainDicomTags", {}).get("InstanceNumber")))
            tags = se.get("MainDicomTags", {})
            saida.append({
                "id": se["ID"],
                "numero": tags.get("SeriesNumber", ""),
                "modalidade": tags.get("Modality", ""),
                "descricao": tags.get("SeriesDescription", ""),
                "imagens": [i["ID"] for i in ordem],
            })
    except urllib.error.HTTPError as exc:
        raise HTTPException(404 if exc.code == 404 else 502, "Exame não encontrado no servidor de imagens.") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise HTTPException(502, "Servidor de imagens indisponível.") from exc
    tags = info.get("MainDicomTags", {})
    return {"id": estudo, "data": _data_dicom(tags.get("StudyDate")), "descricao": tags.get("StudyDescription", ""), "series": saida}


@app.get("/api/imagens/instancia/{instancia}.png")
def imagem_png(instancia: str) -> Response:
    """Uma imagem pronta para tela/impressao (PNG gerado pelo Orthanc)."""
    _validar_id(instancia)
    try:
        with urllib.request.urlopen(f"{ORTHANC_URL}/instances/{instancia}/preview", timeout=30) as r:
            dados = r.read()
    except urllib.error.HTTPError as exc:
        raise HTTPException(404, "Imagem não encontrada.") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise HTTPException(502, "Servidor de imagens indisponível.") from exc
    return Response(dados, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})


@app.get("/api/imagens/{estudo}/zip")
def baixar_estudo(estudo: str) -> StreamingResponse:
    """Exame inteiro em DICOM (zip), ja anonimizado na importacao."""
    _validar_id(estudo)
    try:
        info = _orthanc_get(f"/studies/{estudo}")
        resp = urllib.request.urlopen(f"{ORTHANC_URL}/studies/{estudo}/archive", timeout=300)
    except urllib.error.HTTPError as exc:
        raise HTTPException(404, "Exame não encontrado.") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise HTTPException(502, "Servidor de imagens indisponível.") from exc
    tags = info.get("MainDicomTags", {})
    desc = _NOME_SEGURO.sub("_", tags.get("StudyDescription", "") or "exame").strip("_")[:60] or "exame"
    nome = f"Imagens_{_data_dicom(tags.get('StudyDate')) or 'sem-data'}_{desc}.zip"

    def blocos():
        with resp:
            while True:
                bloco = resp.read(1024 * 1024)
                if not bloco:
                    break
                yield bloco

    return StreamingResponse(blocos(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{nome}"'})


# Frontend compilado (npm run build). Em desenvolvimento, o Vite serve o frontend.
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str) -> FileResponse:
        if caminho.startswith("api/") or caminho == "api":
            raise HTTPException(404, "Rota da API inexistente.")
        arquivo = (FRONTEND_DIST / caminho).resolve()
        if caminho and arquivo.is_file() and FRONTEND_DIST.resolve() in arquivo.parents:
            return FileResponse(arquivo)
        return FileResponse(FRONTEND_DIST / "index.html")
