#!/usr/bin/env python3
"""Audita o resultados.json do processamento e lista o que parece errado.

Uso no servidor (so biblioteca padrao):
    python3 auditar_laudos.py /srv/saude/painel/resultados.json

Mostra so nome do arquivo, data e o motivo; nunca o texto do laudo nem dados
pessoais, para a saida poder ser colada em uma conversa.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ARTICULACOES = {"ombro", "cotovelo", "punho_mao", "quadril", "joelho", "tornozelo_pe", "membros_inferiores"}
DATA_MINIMA = "2000-01-01"  # antes disso e quase sempre a data de nascimento lida no lugar do exame


def auditar(payload: dict, hoje: str | None = None) -> list[tuple[str, str]]:
    """[(arquivo, problema)] em ordem de arquivo."""
    hoje = hoje or date.today().isoformat()
    problemas: list[tuple[str, str]] = []
    arquivos = [a for a in payload.get("arquivos", []) if a.get("tipo") != "duplicado"]
    resultados_por_arquivo = Counter(r.get("arquivo") for r in payload.get("resultados", []))
    achados_por_arquivo: dict[str, list[dict]] = defaultdict(list)
    for a in payload.get("achados", []):
        achados_por_arquivo[a.get("arquivo")].append(a)

    datas_antigas = Counter(a["data"] for a in arquivos if a.get("data") and a["data"] < DATA_MINIMA)

    for a in arquivos:
        nome, d, tipo = a.get("arquivo", "?"), a.get("data"), a.get("tipo")
        if not a.get("texto_extraido"):
            problemas.append((nome, "PDF sem texto (escaneado): nada foi lido, precisa de OCR"))
            continue
        if not d:
            problemas.append((nome, "sem data do exame"))
        elif d < DATA_MINIMA:
            extra = f" (a mesma data aparece em {datas_antigas[d]} arquivos)" if datas_antigas[d] > 1 else ""
            problemas.append((nome, f"data {d} antiga demais: provavelmente a data de nascimento{extra}"))
        elif d > hoje:
            problemas.append((nome, f"data {d} no futuro"))
        if a.get("aviso"):
            problemas.append((nome, f"aviso: {a['aviso']}"))
        if tipo == "laboratorial" and not resultados_por_arquivo.get(nome):
            problemas.append((nome, "laboratorial sem nenhum resultado lido"))
        if tipo == "imagem":
            achados = achados_por_arquivo.get(nome, [])
            if not achados:
                problemas.append((nome, "laudo de imagem sem achado (conclusao nao encontrada)"))
            for ac in achados:
                regiao = ac.get("regiao")
                if regiao == "outros":
                    problemas.append((nome, "regiao do corpo nao reconhecida (caiu em 'Outras regioes')"))
                if regiao in ARTICULACOES and not ac.get("lado"):
                    problemas.append((nome, f"{regiao} sem lado (direito/esquerdo)"))
                if ac.get("modalidade") == "imagem":
                    problemas.append((nome, "modalidade nao reconhecida (RM/TC/RX/US)"))
                if len((ac.get("trecho") or "").strip()) < 20:
                    problemas.append((nome, f"{regiao}: conclusao vazia ou curta demais"))
                if ac.get("data") != d:
                    problemas.append((nome, f"{regiao}: data do achado ({ac.get('data')}) diferente da do arquivo"))

    for r in payload.get("resultados", []):
        if not r.get("data"):
            problemas.append((r.get("arquivo", "?"), f"resultado sem data: {r.get('exame')}"))
    for e in payload.get("erros", []):
        problemas.append((e.get("arquivo", "?"), f"erro ao processar: {e.get('erro')}"))

    vistos, unicos = set(), []
    for p in problemas:
        if p not in vistos:
            vistos.add(p)
            unicos.append(p)
    return sorted(unicos)


def main() -> int:
    caminho = Path(sys.argv[1] if len(sys.argv) > 1 else "/srv/saude/painel/resultados.json")
    payload = json.loads(caminho.read_text(encoding="utf-8"))
    arquivos = [a for a in payload.get("arquivos", []) if a.get("tipo") != "duplicado"]
    tipos = Counter(a.get("tipo") for a in arquivos)
    print(f"{len(arquivos)} arquivos unicos: " + ", ".join(f"{n} {t}" for t, n in sorted(tipos.items())))
    print(f"{len(payload.get('resultados', []))} resultados, {len(payload.get('achados', []))} achados de imagem")
    problemas = auditar(payload)
    atual = None
    for arquivo, problema in problemas:
        if arquivo != atual:
            print(f"\n{arquivo}")
            atual = arquivo
        print(f"  - {problema}")
    print(f"\n{len(problemas)} problema(s) em {len({a for a, _ in problemas})} arquivo(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
