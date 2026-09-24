#!/usr/bin/env python3
"""Importa imagens DICOM (zips baixados do portal / PACS) para o Orthanc do painel.

Uso (no VPS, com o Orthanc publicado so em 127.0.0.1:8042):

    .venv/bin/python importar_imagens.py /srv/saude/imagens/*.zip
    .venv/bin/python importar_imagens.py pasta_com_dicoms/ --orthanc http://127.0.0.1:8042

Para cada arquivo DICOM encontrado (dentro de zips, subpastas ou zips dentro
de zips) o script:

1. ANONIMIZA os dados do paciente antes de sair do disco: nome, ID, data de
   nascimento, endereco, telefone, numero de atendimento e tags privadas do
   fabricante (que as vezes repetem o nome). Qualquer outro campo de texto que
   ainda contenha o nome ou o ID original e apagado.
2. Envia ao Orthanc (POST /instances). Reimportar o mesmo zip nao duplica nada:
   o Orthanc reconhece a imagem pelo SOPInstanceUID.

Atencao: alguns aparelhos (ultrassom, raio-X antigo) "queimam" o nome do
paciente nos pixels da imagem. Isso NAO e removido aqui — o site continua
protegido por senha (basic_auth no Caddy).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import unicodedata
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import pydicom
from pydicom.dataset import Dataset

MAX_ARQUIVO = 2 * 1024 * 1024 * 1024  # 2 GB por membro de zip (sanidade)

# Tags removidas por completo (identificam o paciente ou o atendimento).
TAGS_REMOVER = [
    "PatientBirthDate", "PatientBirthTime", "PatientBirthName", "PatientMotherBirthName",
    "OtherPatientIDs", "OtherPatientIDsSequence", "OtherPatientNames", "PatientAddress",
    "PatientTelephoneNumbers", "MedicalRecordLocator", "IssuerOfPatientID",
    "PatientInsurancePlanCodeSequence", "MilitaryRank", "EthnicGroup", "PatientReligiousPreference",
    "AccessionNumber", "AdmissionID", "RequestAttributesSequence", "PatientComments",
    "PersonName", "ResponsiblePerson", "PatientWeight", "PatientSize",
]
NOME_ANONIMO = "PACIENTE"
ID_ANONIMO = "PAINEL"
VRS_TEXTO = {"PN", "LO", "SH", "LT", "ST", "UT", "CS"}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", str(texto)).encode("ascii", "ignore").decode()
    return "".join(c for c in texto.upper() if c.isalnum() or c == " ").strip()


def _tokens_identificadores(ds: Dataset) -> list[str]:
    """Pedacos do nome/ID original que nao podem sobrar em nenhum campo."""
    tokens: list[str] = []
    nome = str(ds.get("PatientName", "") or "")
    for parte in _normalizar(nome.replace("^", " ")).split():
        if len(parte) >= 4:  # evita apagar "DE", "DA"...
            tokens.append(parte)
    pid = _normalizar(str(ds.get("PatientID", "") or "")).replace(" ", "")
    if len(pid) >= 4:
        tokens.append(pid)
    return tokens


def anonimizar(ds: Dataset) -> Dataset:
    tokens = _tokens_identificadores(ds)
    for tag in TAGS_REMOVER:
        if tag in ds:
            delattr(ds, tag)
    ds.remove_private_tags()
    ds.PatientName = NOME_ANONIMO
    ds.PatientID = ID_ANONIMO

    def varrer(d: Dataset) -> None:
        for elem in list(d):
            if elem.VR == "SQ":
                for item in elem.value or []:
                    varrer(item)
                continue
            if elem.keyword in ("PatientName", "PatientID") or elem.VR not in VRS_TEXTO or elem.value in (None, ""):
                continue
            valores = elem.value if isinstance(elem.value, (list, pydicom.multival.MultiValue)) else [elem.value]
            texto = _normalizar(" ".join(str(v) for v in valores).replace("^", " "))
            if tokens and any(t in texto.split() or (len(t) > 8 and t in texto.replace(" ", "")) for t in tokens):
                elem.value = ""

    if tokens:
        varrer(ds)
    ds.PatientIdentityRemoved = "YES"
    ds.DeidentificationMethod = "painel-exames: tags removidas; pixels nao"
    return ds


SOP_DICOMDIR = "1.2.840.10008.1.3.10"  # indice do CD/pasta, nao e imagem


def e_indice(nome: str) -> bool:
    return Path(nome).name.upper() in ("DICOMDIR", "DICOMDIR.DCM")


def parece_dicom(dados: bytes) -> bool:
    return len(dados) >= 132 and dados[128:132] == b"DICM"


def encontrar_dicoms(caminho: Path) -> Iterator[tuple[str, bytes]]:
    """Gera (nome, bytes) de cada DICOM em um arquivo, zip ou pasta."""
    if caminho.is_dir():
        for p in sorted(caminho.rglob("*")):
            if p.is_file() and not e_indice(p.name):
                yield from encontrar_dicoms(p)
        return
    with caminho.open("rb") as f:
        cabeca = f.read(132)
    if cabeca.startswith(b"PK"):
        with zipfile.ZipFile(caminho) as z:
            yield from _dicoms_no_zip(z, caminho.name, profundidade=0)
    elif parece_dicom(cabeca):
        yield caminho.name, caminho.read_bytes()


def _dicoms_no_zip(z: zipfile.ZipFile, origem: str, profundidade: int) -> Iterator[tuple[str, bytes]]:
    for m in z.infolist():
        if m.is_dir() or m.file_size > MAX_ARQUIVO or "__MACOSX" in m.filename or e_indice(m.filename):
            continue
        with z.open(m) as f:
            cabeca = f.read(132)
        if parece_dicom(cabeca):
            yield f"{origem}/{m.filename}", z.read(m)
        elif cabeca.startswith(b"PK") and profundidade < 2:
            with zipfile.ZipFile(io.BytesIO(z.read(m))) as interno:
                yield from _dicoms_no_zip(interno, f"{origem}/{m.filename}", profundidade + 1)


@dataclass
class Orthanc:
    url: str
    usuario: str | None = None
    senha: str | None = None
    timeout: float = 120

    def _req(self, caminho: str, dados: bytes | None = None, metodo: str = "GET") -> dict | list:
        req = urllib.request.Request(self.url.rstrip("/") + caminho, data=dados, method=metodo)
        if dados is not None:
            req.add_header("Content-Type", "application/dicom")
        if self.usuario:
            cred = base64.b64encode(f"{self.usuario}:{self.senha or ''}".encode()).decode()
            req.add_header("Authorization", f"Basic {cred}")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            corpo = r.read()
        return json.loads(corpo) if corpo else {}

    def enviar(self, dicom: bytes) -> str:
        """Retorna 'Success' (novo) ou 'AlreadyStored'."""
        r = self._req("/instances", dicom, "POST")
        return r.get("Status", "Success") if isinstance(r, dict) else "Success"


@dataclass
class Relatorio:
    novos: int = 0
    repetidos: int = 0
    erros: list[str] = field(default_factory=list)
    estudos: dict[str, str] = field(default_factory=dict)


def importar(caminhos: list[Path], orthanc: Orthanc, simular: bool = False) -> Relatorio:
    rel = Relatorio()
    for caminho in caminhos:
        if not caminho.exists():
            rel.erros.append(f"{caminho}: não existe")
            continue
        antes = rel.novos + rel.repetidos
        try:
            for nome, dados in encontrar_dicoms(caminho):
                try:
                    ds = pydicom.dcmread(io.BytesIO(dados), force=True)
                    if str(ds.get("SOPClassUID", "")) == SOP_DICOMDIR or "SOPInstanceUID" not in ds:
                        continue  # indice ou arquivo sem imagem
                    anonimizar(ds)
                    saida = io.BytesIO()
                    ds.save_as(saida, enforce_file_format=True)
                    chave = f"{ds.get('StudyDate', '')} {ds.get('Modality', '')} {ds.get('StudyDescription', '')}".strip()
                    rel.estudos[str(ds.get("StudyInstanceUID", ""))] = chave
                    if simular:
                        rel.novos += 1
                        continue
                    status = orthanc.enviar(saida.getvalue())
                    if status == "AlreadyStored":
                        rel.repetidos += 1
                    else:
                        rel.novos += 1
                except urllib.error.HTTPError as exc:
                    # O Orthanc respondeu, mas recusou: mostra o motivo que ele deu.
                    detalhe = exc.read()[:400].decode("utf-8", "replace").replace("\n", " ")
                    rel.erros.append(f"{nome}: Orthanc respondeu HTTP {exc.code}: {detalhe}")
                    if len(rel.erros) >= 3 and not (rel.novos or rel.repetidos):
                        raise RuntimeError("O Orthanc recusou as primeiras imagens: " + " | ".join(rel.erros)) from exc
                except (urllib.error.URLError, OSError) as exc:
                    raise RuntimeError(f"Orthanc indisponível em {orthanc.url}: {exc}") from exc
                except Exception as exc:  # um arquivo ruim nao para o resto
                    rel.erros.append(f"{nome}: {type(exc).__name__}: {exc}")
        except zipfile.BadZipFile:
            rel.erros.append(f"{caminho}: zip corrompido")
            continue
        total = rel.novos + rel.repetidos - antes
        print(f"{caminho.name}: {total} imagem(ns) DICOM", file=sys.stderr)
    return rel


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("caminhos", nargs="+", type=Path, help="zips, pastas ou arquivos DICOM")
    ap.add_argument("--orthanc", default="http://127.0.0.1:8042")
    ap.add_argument("--usuario")
    ap.add_argument("--senha")
    ap.add_argument("--simular", action="store_true", help="so le e anonimiza, sem enviar")
    args = ap.parse_args()
    try:
        rel = importar(args.caminhos, Orthanc(args.orthanc, args.usuario, args.senha), simular=args.simular)
    except RuntimeError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2
    print(f"\nImagens novas: {rel.novos} | já estavam no Orthanc: {rel.repetidos} | erros: {len(rel.erros)}")
    for uid, desc in sorted(rel.estudos.items(), key=lambda x: x[1]):
        print(f"  estudo: {desc}")
    for e in rel.erros[:20]:
        print(f"  erro: {e}")
    return 1 if rel.erros and not (rel.novos or rel.repetidos) else 0


if __name__ == "__main__":
    raise SystemExit(main())
