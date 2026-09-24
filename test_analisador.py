import io
import shutil
import unittest
from unittest import mock

from collections import defaultdict
from pathlib import Path

import analisar_exames as A
from analisar_exames import classification, classify_file, parse_number, reference_bounds, select_reference
from achados import conclusao, extrair_achados, niveis_em
from mapa_exames import identificar


class ParseNumberTests(unittest.TestCase):
    def test_decimal_comma(self):
        self.assertEqual(parse_number("519,61"), 519.61)

    def test_thousands_and_comma(self):
        self.assertEqual(parse_number("1.250,5"), 1250.5)

    def test_decimal_dot(self):
        # Antes da correcao, "5.0" virava 50 e "0.8" virava 8.
        self.assertEqual(parse_number("5.0"), 5.0)
        self.assertEqual(parse_number("0.8"), 0.8)
        self.assertEqual(parse_number("12.75"), 12.75)

    def test_thousands_dot_only(self):
        self.assertEqual(parse_number("6.500"), 6500.0)
        self.assertEqual(parse_number("250.000"), 250000.0)


class ClassificationTests(unittest.TestCase):
    def test_range(self):
        self.assertEqual(classification(3.0, "Valor de Referencia: 0 a 5,0 mg/L"), "dentro")
        self.assertEqual(classification(7.0, "Valor de Referencia: 0 a 5,0 mg/L"), "acima")

    def test_range_with_decimal_dot(self):
        self.assertEqual(classification(0.9, "Valor de referencia: 0.5 a 1.2 mg/dL"), "dentro")
        self.assertEqual(classification(0.4, "Valor de referencia: 0.5 a 1.2 mg/dL"), "abaixo")

    def test_upper_limit(self):
        self.assertEqual(classification(3.0, "Inferior ou igual a 5,0 mg/L"), "dentro")
        self.assertEqual(classification(6.0, "Inferior ou igual a 5,0 mg/L"), "acima")

    def test_bounds(self):
        self.assertEqual(reference_bounds("Valor de referencia: 70 a 99 mg/dL")[:2], (70.0, 99.0))
        self.assertEqual(reference_bounds("Inferior a 130 mg/dL")[:2], (None, 130.0))
        self.assertEqual(reference_bounds("Superior a 40 mg/dL")[:2], (40.0, None))


class ClassifyFileTests(unittest.TestCase):
    def test_unimed_names(self):
        casos = {
            "10261186_32355016_Rm_Coluna_Cervical.pdf": "imagem",
            "8898546_27424156_Rx_Coluna_Lombo_Sacra_5_Incidencias.pdf": "imagem",
            "8928075_27529174_Rm_Coluna_Lombo_Sacra_Coccigea_.pdf": "imagem",
            "9800813_30627165_TC_Coluna_Lombar_.pdf": "imagem",
            "9581129_anatomo_patologico.pdf": "anatomopatologico",
            "123_Laboratorial.pdf": "laboratorial",
        }
        for nome, tipo in casos.items():
            self.assertEqual(classify_file(nome, ""), tipo, nome)

    def test_content_beats_filename(self):
        lab = "COLESTEROL LDL\nMaterial:\nSoro\nColeta:\n17/08/2026\nResultado:\n125\nmg/dL\nValor de Referencia: inferior a 115"
        self.assertEqual(classify_file("10261186_32355016_Rm_Coluna_Cervical.pdf", lab), "laboratorial")
        rm = "RESSONANCIA MAGNETICA DA COLUNA CERVICAL\nTecnica: ...\nIMPRESSAO DIAGNOSTICA: protrusao C5-C6"
        self.assertEqual(classify_file("123_laboratorial.pdf", rm), "imagem")

    def test_lab_words_are_not_image(self):
        # "tc" e "rm" dentro de palavras nao podem disparar
        self.assertEqual(classify_file("123_Hemograma_Completo.pdf", "FORMULA LEUCOCITARIA"), "laboratorial")
        self.assertEqual(classify_file("x.pdf", "HORMONIO TIREOESTIMULANTE (TSH)"), "laboratorial")


class TabelasReferenciaTests(unittest.TestCase):
    """Formatos reais de tabelas de referencia (valores genericos)."""

    TESTO = ("Feminino:\nPre-puberes: Sem valor de referencia definido\nMenacme:\nFase folicular: 0,18 a 1,68 ng/dL\n"
             "Masculino:\n0 a 16 anos.......: Sem valor de referencia definido\n17 a 40 anos......: 3,40 a 24,60 ng/dL\n"
             "41 a 60 anos......: 2,67 a 18,30 ng/dL\nSuperior a 60 anos: 1,86 a 19,00 ng/dL")

    def test_sexo_e_idade(self):
        self.assertEqual(reference_bounds(select_reference(self.TESTO, "M", 50))[:2], (2.67, 18.3))
        self.assertEqual(reference_bounds(select_reference(self.TESTO, "M", 65))[:2], (1.86, 19.0))
        self.assertEqual(classification(4.7, select_reference(self.TESTO, "M", 50)), "dentro")

    def test_sem_sexo_nao_chuta(self):
        self.assertEqual(select_reference(self.TESTO, None, 50), "")
        self.assertEqual(classification(4.7, select_reference(self.TESTO, None, 50)), "nao determinado")

    def test_idade_nao_e_limite(self):
        ref = "Masculino:\n21 a 49 anos....: 47,01 a 980,56 ng/dL\nSuperior ou igual a 50 anos: 127,18 a 1020,36 ng/dL\nFeminino:\n21 a 49 anos: 7,21 a 79,31 ng/dL"
        self.assertEqual(reference_bounds(select_reference(ref, "M", 50))[:2], (127.18, 1020.36))

    def test_categoria_preferida(self):
        vitd = ("Deficiencia......: Inferior a 20 ng/mL\nAdequado para populacao em geral ate 65 anos: 20,0 a 60,0 ng/mL\n"
                "Ideal*...........: 30,0 a 60,0 ng/mL\nRisco de intoxicacao: Superior a 100,0 ng/mL")
        self.assertEqual(classification(50.0, select_reference(vitd, "M", 50)), "dentro")
        a1c = ("Nao diabeticos.....: Inferior a 5,7%\nRisco de desenvolvimento de diabetes: 5,7 a 6,4%\n"
               "Diabeticos.........: Igual ou superior a 6,5%\nMetas terapeuticas para controle glicemico:\n"
               "Em adultos diabeticos.: Inferior a 7,0%\nEm criancas diabeticas: Inferior a 8,0%")
        self.assertEqual(reference_bounds(select_reference(a1c, None, 50))[:2], (None, 5.7))

    def test_secoes_adulto_gestante_pediatrico(self):
        t4 = ("Adultos.............: de 0,75 a 1,22 ng/dL\nGestantes:\n1o trimestre........: de 0,85 a 1,35 ng/dL\n"
              "Pediatricos:\n< 1 mes...................: Nao disponivel\nDe 2 a 12 anos.....: de 0,84 a 1,32 ng/dL")
        self.assertEqual(reference_bounds(select_reference(t4, "M", 50))[:2], (0.75, 1.22))
        tg = ("Para adultos acima de 20 anos:\nCom jejum: Inferior a 150 mg/dL\nSem jejum: Inferior a 175 mg/dL\n"
              "Para criancas e adolescentes de 0 a 9 anos:\nCom jejum: Inferior a 75 mg/dL")
        sel = select_reference(tg, "M", 50)
        # Faixas que discordam (com/sem jejum) nao dao ref_min/ref_max unico; como a
        # classificacao sai SO dos limites, fica "nao determinado" (antes 200 dava "acima"
        # sem limite nenhum no grafico que justificasse).
        self.assertEqual(A.limites_referencia(sel), (None, None))
        self.assertEqual(classification(200.0, sel), "nao determinado")
        self.assertEqual(classification(160.0, sel), "nao determinado")

    def test_meta_por_risco(self):
        ldl = "VALORES DE ALVO TERAPEUTICO SUGERIDO PARA CATEGORIA DE RISCO\n| BAIXO | INFERIOR A 115 mg/dL\n| ALTO | INFERIOR A 70 mg/dL"
        self.assertEqual(classification(125.0, ldl), "nao determinado")


class PainelTests(unittest.TestCase):
    TEXTO = (
        "HEMOGRAMA\nMaterial:\nSangue total com EDTA\nColeta:\n10/02/2025 - 09:18:24\nMetodo :\nCitometria\n \nERITROGRAMA\n"
        "Valor de referencia:\n \nHemacias (milhoes/mm3).............:\n4,95\n \n \n  4,32 a   5,66 milhoes/mm3\n"
        "Hemoglobina (g/dL).................:\n15,4\n \n13,3  a  16,7  g/dL\nLEUCOGRAMA\nValor de referencia:\n"
        "Leucocitos (/mm3)..................:\n4.870\n \n3.700  a  11.000 /mm3\nSegmentados........................:\n56,1\n \n2.733\n \n"
        "1.700 a   7.500 /mm3\nPlaquetas..........................:\n202.000\n \n/mm3\n150.000 a 450.000 /mm3\n"
        "Sr (a)\n:\nFULANO\nIdade\n:\n50 anos\n"
        "GLICOSE\nMaterial:\nSoro\nColeta:\n11/03/2025 - 09:00\nResultado:\n95\nmg/dL\nValor de Referencia:\nNormoglicemia: Inferior a 100 mg/dL\n"
    )

    def test_linha_em_branco_depois_do_titulo(self):
        # pypdf 6 insere " " entre o titulo e "Material:"
        texto = self.TEXTO.replace("HEMOGRAMA\nMaterial:", "HEMOGRAMA\n \nMaterial:").replace("GLICOSE\nMaterial:", "GLICOSE\n \nMaterial:")
        res = {r.exame_id: r for r in A.extract_results(Path("x.pdf"), texto, "2026-01-01")}
        self.assertIn("plaquetas", res)
        self.assertEqual(res["glicose"].data, "2025-03-11")

    def test_painel_e_data_por_bloco(self):
        res = {r.exame_id: r for r in A.extract_results(Path("x.pdf"), self.TEXTO, "2026-01-01")}
        self.assertEqual(res["hemacias"].valor_numerico, 4.95)
        self.assertEqual(res["hemacias"].unidade, "milhoes/mm3")
        self.assertEqual((res["leucocitos"].valor_numerico, res["leucocitos"].ref_min), (4870.0, 3700.0))
        self.assertEqual(res["neutrofilos_segmentados"].valor_numerico, 2733.0)  # absoluto, nao o %
        self.assertEqual(res["plaquetas"].valor_numerico, 202000.0)
        self.assertEqual(res["hemacias"].data, "2025-02-10")
        self.assertEqual(res["glicose"].data, "2025-03-11")
        self.assertEqual(res["glicose"].classificacao, "dentro")


class MapaTests(unittest.TestCase):
    def test_variants_same_id(self):
        for nome in ("COLESTEROL LDL", "LDL-COLESTEROL", "LDL COLESTEROL CALCULADO"):
            self.assertEqual(identificar(nome)[0], "ldl")

    def test_not_confused(self):
        self.assertEqual(identificar("COLESTEROL NAO-HDL")[0], "nao_hdl")
        self.assertEqual(identificar("VLDL COLESTEROL")[0], "vldl")
        self.assertEqual(identificar("HEMOGLOBINA GLICADA")[0], "hba1c")
        self.assertEqual(identificar("BILIRRUBINA TOTAL")[0], "bilirrubina_total")

    def test_vitamina_c_nao_cai_em_outros(self):
        self.assertEqual(identificar("VITAMINA C")[0], "vitamina_c")
        self.assertEqual(identificar("ACIDO ASCORBICO (VITAMINA C)")[2], "vitaminas")

    def test_eletroforese_nao_mistura_com_albumina(self):
        self.assertEqual(identificar("Eletroforese Albumina")[0], "eletroforese_albumina")
        self.assertEqual(identificar("Albumina")[0], "albumina")
        self.assertEqual(identificar("Relação PSA Livre / PSA Total")[0], "relacao_psa")
        self.assertEqual(identificar("TESTOSTERONA TOTAL")[0], "testosterona_total")

    def test_system(self):
        self.assertEqual(identificar("TGP - ALANINA AMINOTRANSFERASE")[2], "figado")
        self.assertEqual(identificar("CREATININA")[2], "rins")

    def test_unknown(self):
        self.assertEqual(identificar("Exame nao identificado")[0], "nao_identificado")
        self.assertEqual(identificar("DOSAGEM XYZ")[2], "outros")


class AchadosTests(unittest.TestCase):
    LAUDO = (
        "RESSONANCIA MAGNETICA DA COLUNA CERVICAL\nTecnica: sequencias sagitais.\n"
        "Achados: corpos vertebrais alinhados.\nIMPRESSAO DIAGNOSTICA:\n"
        "Protrusao discal C4-C5. Hernia discal C5/C6 com contato radicular a direita.\n"
        "Dr. Exemplo CRM 0000"
    )

    def test_levels(self):
        self.assertEqual(niveis_em("hernia C5/C6 e C6-7, L5-S1, D11-D12"), ["C5-C6", "C6-C7", "L5-S1", "T11-T12"])

    def test_conclusion_stops_at_signature(self):
        self.assertNotIn("CRM", conclusao(self.LAUDO))
        self.assertIn("C5/C6", conclusao(self.LAUDO))

    def test_extract(self):
        (a,) = extrair_achados("rm.pdf", "2024-05-01", self.LAUDO)
        self.assertEqual((a.modalidade, a.regiao), ("ressonancia", "cervical"))
        self.assertEqual(a.niveis, ["C4-C5", "C5-C6"])
        self.assertIn("hernia", a.termos)
        self.assertIn("radicular", a.termos)

    def test_levels_win_over_title(self):
        texto = "RM DA COLUNA LOMBO-SACRA\nIMPRESSAO:\nAlteracoes pos-cirurgicas com artrodese L4-L5 e L5-S1."
        achados = extrair_achados("Rm_Coluna_Lombo_Sacra_Coccigea_.pdf", None, texto)
        self.assertEqual([(a.regiao, a.niveis) for a in achados], [("lombar", ["L4-L5", "L5-S1"])])

    def test_relatorio_sem_conclusao(self):
        texto = ("TOMOGRAFIA COMPUTADORIZADA DA COLUNA LOMBAR\nTecnica: cortes axiais.\nRelatorio\n"
                 "Artrodese anterior (ALIF) em L5-S1. Pequeno abaulamento discal em L4-L5.\n"
                 "Observacao: Tres series de imagens foram fornecidas.")
        (a,) = extrair_achados("tc.pdf", None, texto)
        self.assertEqual(a.regiao, "lombar")
        self.assertEqual(set(a.niveis), {"L5-S1", "L4-L5"})
        self.assertIn("artrodese", a.termos)
        self.assertNotIn("Observacao", a.trecho)

    def test_negation(self):
        texto = "RM DA COLUNA TORACICA\nCONCLUSAO: alteracoes degenerativas T7-T8, sem compressao medular. Nao ha hernia discal."
        (a,) = extrair_achados("x.pdf", None, texto)
        self.assertEqual(a.termos, ["degenerativo"])

    def test_region_from_header_when_no_level(self):
        texto = "RM DO JOELHO ESQUERDO\nCONCLUSAO: lesao do menisco medial. Derrame articular."
        (a,) = extrair_achados("x.pdf", None, texto)
        self.assertEqual((a.regiao, a.lado), ("joelho", "esquerdo"))



class MapaOutrosTests(unittest.TestCase):
    """Exames que antes caiam em "Outros" e agora vao para o orgao certo."""

    def test_reclassificados(self):
        casos = {
            "Di-Hidrotestosterona (Dht)": "hormonios",
            "Rni": "figado",
            "Tempo Paciente": "figado",
            "Anticorpos Anti Hbs": "figado",
            "Ph": "rins",
            "Densidade": "rins",
            "Células Epiteliais........P/Ml": "rins",
            "Motilidade Progressiva": "testiculos",
            "Motilidade Não Progressiva": "testiculos",
            "Nº De Espermatozoides /Ml": "testiculos",
            "Imóveis": "testiculos",
            "PSA TOTAL": "prostata",
        }
        for titulo, sistema in casos.items():
            with self.subTest(titulo=titulo):
                self.assertEqual(identificar(titulo)[2], sistema)

    def test_motilidade_nao_confunde(self):
        self.assertNotEqual(identificar("Motilidade Não Progressiva")[0], identificar("Motilidade Progressiva")[0])


class UploadMesclaTests(unittest.TestCase):
    def test_upload_repetido_do_principal_e_ignorado(self):
        import api
        principal = {"arquivos": [{"arquivo": "a.pdf", "sha256": "x", "hash_texto": "t1"}], "resultados": [{"arquivo": "a.pdf"}], "achados": []}
        extra = {
            "arquivos": [{"arquivo": "b.pdf", "sha256": "x"}, {"arquivo": "c.pdf", "sha256": "y", "hash_texto": "t1"}, {"arquivo": "d.pdf", "sha256": "z"}],
            "resultados": [{"arquivo": "b.pdf"}, {"arquivo": "c.pdf"}, {"arquivo": "d.pdf"}],
            "achados": [],
        }
        m = api._mesclar(principal, extra)
        self.assertEqual([a["arquivo"] for a in m["arquivos"]], ["a.pdf", "d.pdf"])
        self.assertEqual([r["arquivo"] for r in m["resultados"]], ["a.pdf", "d.pdf"])

    def test_nome_seguro(self):
        import api
        self.assertEqual(api._nome_seguro("../../etc/passwd"), "passwd.pdf")
        self.assertEqual(api._nome_seguro("Exame João 01.pdf"), "Exame_Jo_o_01.pdf")


def _pdf_simples(texto: str) -> bytes:
    """PDF minimo valido com uma linha de texto (sem dependencias externas)."""
    import io as _io
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    w = PdfWriter()
    pagina = w.add_blank_page(width=300, height=200)
    fonte = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    pagina[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): w._add_object(fonte)})})
    conteudo = DecodedStreamObject()
    conteudo.set_data(f"BT /F1 10 Tf 20 150 Td ({texto}) Tj ET".encode("latin-1"))
    pagina[NameObject("/Contents")] = w._add_object(conteudo)
    buf = _io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _zip(arquivos: dict[str, bytes]) -> bytes:
    import io as _io
    import zipfile as _zf
    buf = _io.BytesIO()
    with _zf.ZipFile(buf, "w") as z:
        for nome, dados in arquivos.items():
            z.writestr(nome, dados)
    return buf.getvalue()


class ExpandirUploadTests(unittest.TestCase):
    def test_pdf_passa_direto(self):
        import api
        pdf = _pdf_simples("Laudo 01/02/2024")
        pdfs, avisos = api._expandir("a.pdf", pdf)
        self.assertEqual([n for n, _ in pdfs], ["a.pdf"])
        self.assertEqual(avisos, [])

    def test_zip_com_pdfs_em_subpasta_e_lixo(self):
        import api
        z = _zip({"laudos/Laudo_1.pdf": _pdf_simples("um"), "Laudo_2.PDF": _pdf_simples("dois"),
                  "__MACOSX/._Laudo_1.pdf": b"x", "leia.txt": b"oi", "IM0001": b"\0" * 128 + b"DICM"})
        pdfs, avisos = api._expandir("Laudos.zip", z)
        self.assertEqual(sorted(n for n, _ in pdfs), ["Laudo_1.pdf", "Laudo_2.PDF"])
        self.assertEqual(avisos[0]["status"], "info")
        self.assertIn("DICOM", avisos[0]["erro"])

    def test_zip_dentro_de_zip(self):
        import api
        interno = _zip({"x.pdf": _pdf_simples("x")})
        pdfs, _ = api._expandir("fora.zip", _zip({"dentro.zip": interno}))
        self.assertEqual([n for n, _ in pdfs], ["x.pdf"])

    def test_zip_so_dicom_explica(self):
        import api
        pdfs, avisos = api._expandir("Exame_RM.zip", _zip({"DICOM/IM0001": b"\0" * 128 + b"DICM", "DICOMDIR": b"x"}))
        self.assertEqual(pdfs, [])
        self.assertIn("DICOM", avisos[0]["erro"])

    def test_formatos_recusados_com_motivo(self):
        import api
        casos = {"foto.jpg": b"\xff\xd8\xff", "laudo.docx": b"PK\x03\x04lixo", "img.dcm": b"\0" * 128 + b"DICM", "x.bin": b"abc"}
        for nome, dados in casos.items():
            with self.subTest(nome=nome):
                pdfs, avisos = api._expandir(nome, dados)
                self.assertEqual(pdfs, [])
                self.assertEqual(avisos[0]["status"], "erro")
                self.assertTrue(avisos[0]["erro"])

    def test_zip_bomb_barrado(self):
        import api
        antigo = api.MAX_ZIP_TOTAL
        api.MAX_ZIP_TOTAL = 1000
        try:
            pdfs, avisos = api._expandir("grande.zip", _zip({"a.pdf": b"%PDF" + b"0" * 5000}))
        finally:
            api.MAX_ZIP_TOTAL = antigo
        self.assertEqual(pdfs, [])
        self.assertIn("grande demais", avisos[0]["erro"])


def _tem_httpx() -> bool:
    try:
        import httpx  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_tem_httpx(), "precisa do httpx (pip install httpx) para o TestClient")
class UploadEndpointTests(unittest.TestCase):
    def test_envio_de_zip_pela_api(self):
        import importlib
        import os
        import tempfile as _tf
        from fastapi.testclient import TestClient
        with _tf.TemporaryDirectory() as up, _tf.TemporaryDirectory() as res:
            os.environ["ANALISADOR_UPLOAD_DIR"] = up
            os.environ["ANALISADOR_RESULT_DIR"] = res
            import api
            api = importlib.reload(api)
            try:
                c = TestClient(api.app)
                z = _zip({"Laudo_A.pdf": _pdf_simples("Data do exame: 10/03/2024 Laudo A"),
                          "Laudo_B.pdf": _pdf_simples("Data do exame: 11/03/2024 Laudo B"),
                          "foto.jpg": b"\xff\xd8"})
                r = c.post("/api/upload", files=[("arquivos", ("Laudos.zip", z, "application/zip")),
                                                  ("arquivos", ("RM.zip", _zip({"IM1": b"\0" * 128 + b"DICM"}), "application/zip"))])
                self.assertEqual(r.status_code, 200)
                envios = r.json()["envios"]
                adicionados = [e["arquivo"] for e in envios if e["status"] == "adicionado"]
                self.assertEqual(sorted(adicionados), ["Laudo_A.pdf", "Laudo_B.pdf"])
                self.assertTrue(any(e["arquivo"] == "RM.zip" and e["status"] == "erro" for e in envios))
                self.assertTrue((Path(up) / "pdfs" / "Laudo_A.pdf").exists())
                # reenviar o mesmo zip nao duplica
                r2 = c.post("/api/upload", files=[("arquivos", ("Laudos.zip", z, "application/zip"))])
                self.assertTrue(all(e["status"] in ("duplicado", "info") for e in r2.json()["envios"]))
            finally:
                os.environ.pop("ANALISADOR_UPLOAD_DIR", None)
                os.environ.pop("ANALISADOR_RESULT_DIR", None)
                importlib.reload(api)


class ImagensApiTests(unittest.TestCase):
    ESTUDOS = [
        {"ID": "e1", "MainDicomTags": {"StudyDate": "20230228", "StudyDescription": "RM - COLUNA CERVICAL", "StudyInstanceUID": "1.2.3"}, "PatientMainDicomTags": {"PatientName": "PACIENTE"}},
        {"ID": "e2", "MainDicomTags": {"StudyDate": "20251031", "StudyDescription": "", "StudyInstanceUID": "4.5.6"}},
    ]
    SERIES = [
        {"ID": "s1", "ParentStudy": "e1", "MainDicomTags": {"Modality": "MR", "SeriesDescription": "SAG T2"}, "Instances": ["a", "b", "c"]},
        {"ID": "s2", "ParentStudy": "e1", "MainDicomTags": {"Modality": "MR", "SeriesDescription": "AX T2"}, "Instances": ["d"]},
        {"ID": "s3", "ParentStudy": "e2", "MainDicomTags": {"Modality": "US", "SeriesDescription": "PANTURRILHA"}, "Instances": ["e"]},
    ]

    def _api(self, url="http://orthanc:8042"):
        import api
        api.ORTHANC_URL = url
        api._cache_imagens.update(quando=0.0, dados=None)
        return api

    def test_desligado_sem_url(self):
        api = self._api("")
        self.assertEqual(api.imagens(), {"habilitado": False, "estudos": []})

    def test_lista_estudos_e_liga_laudo_do_dia(self):
        api = self._api()
        resp = {"/studies?expand": self.ESTUDOS, "/series?expand": self.SERIES}
        with mock.patch.object(api, "_orthanc_get", side_effect=lambda c: resp[c]), \
             mock.patch.object(api, "documentos", return_value=[{"arquivo": "Laudo_2023-02-28.pdf", "data": "2023-02-28"}]):
            r = api.imagens()
        self.assertTrue(r["habilitado"])
        e2, e1 = r["estudos"]
        self.assertEqual(e1["data"], "2023-02-28")
        self.assertEqual((e1["series"], e1["imagens"], e1["modalidades"]), (2, 4, ["MR"]))
        self.assertEqual(e1["laudos"], ["Laudo_2023-02-28.pdf"])
        self.assertEqual(e1["visualizador"], "/ohif/viewer?StudyInstanceUIDs=1.2.3")
        self.assertEqual(e2["descricao"], "PANTURRILHA")  # sem StudyDescription usa a serie
        self.assertNotIn("PACIENTE", str(r))  # nada do paciente sai pela API

    def test_orthanc_fora_do_ar(self):
        import urllib.error
        api = self._api()
        with mock.patch.object(api, "_orthanc_get", side_effect=urllib.error.URLError("x")):
            r = api.imagens()
        self.assertIn("indisponível", r["erro"])


def _tem_pydicom() -> bool:
    try:
        import pydicom  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_tem_pydicom(), "precisa do pydicom (pip install pydicom)")
class ImportarImagensTests(unittest.TestCase):
    def _dicom(self) -> bytes:
        import io as _io
        from pydicom.dataset import Dataset, FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian, generate_uid
        ds = Dataset()
        fm = FileMetaDataset()
        fm.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"
        fm.MediaStorageSOPInstanceUID = generate_uid()
        fm.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta = fm
        ds.SOPClassUID, ds.SOPInstanceUID = fm.MediaStorageSOPClassUID, fm.MediaStorageSOPInstanceUID
        ds.StudyInstanceUID, ds.SeriesInstanceUID = generate_uid(), generate_uid()
        ds.PatientName = "SOUZA^JEFFERSON IRINEU DE"
        ds.PatientID = "26032116"
        ds.PatientBirthDate = "19760615"
        ds.AccessionNumber = "3153968"
        ds.StudyDate, ds.Modality, ds.StudyDescription = "20230228", "MR", "RM - COLUNA CERVICAL"
        ds.ImageComments = "Paciente Jefferson Souza"
        ds.ReferringPhysicianName = "HOFFMANN^CASSIANO"
        ds.add_new(0x00091010, "LO", "SOUZA JEFFERSON")
        buf = _io.BytesIO()
        ds.save_as(buf, enforce_file_format=True)
        return buf.getvalue()

    def test_acha_dicom_em_zip_aninhado_e_ignora_resto(self):
        import tempfile as _tf
        import importar_imagens as I
        dcm = self._dicom()
        z = _zip({"DICOM/S1/IM0001": dcm, "exam/DICOMDIR": b"\0" * 128 + b"DICM" + b"x" * 100, "Viewer.exe": b"MZ" + b"0" * 300, "outro.zip": _zip({"IM2": dcm})})
        with _tf.TemporaryDirectory() as d:
            arq = Path(d) / "exame.zip"
            arq.write_bytes(z)
            nomes = [n for n, _ in I.encontrar_dicoms(arq)]
        self.assertEqual(len(nomes), 2)

    def test_anonimiza_sem_sobrar_nome(self):
        import io as _io
        import pydicom
        import importar_imagens as I
        ds = I.anonimizar(pydicom.dcmread(_io.BytesIO(self._dicom())))
        texto = repr(ds).upper()
        for proibido in ("JEFFERSON", "SOUZA", "26032116", "19760615", "3153968"):
            self.assertNotIn(proibido, texto)
        self.assertEqual(ds.StudyDescription, "RM - COLUNA CERVICAL")
        self.assertEqual(str(ds.ReferringPhysicianName), "HOFFMANN^CASSIANO")


@unittest.skipUnless(_tem_httpx(), "precisa do httpx para o TestClient")
class BaixarImprimirTests(unittest.TestCase):
    ID = "0123abcd-0123abcd-0123abcd-0123abcd-0123abcd"

    def setUp(self):
        import tempfile as _tf
        from fastapi.testclient import TestClient
        import api
        self.api = api
        self.tmp = _tf.TemporaryDirectory()
        pasta = Path(self.tmp.name) / "pdfs"
        pasta.mkdir()
        (pasta / "Laudo_A.pdf").write_bytes(_pdf_simples("A"))
        (Path(self.tmp.name) / "segredo.txt").write_text("nao")
        self._dirs = api.PDF_DIRS
        api.PDF_DIRS = [pasta]
        api._cache_pdfs.update(quando=0.0, indice={})
        api.ORTHANC_URL = "http://orthanc:8042"
        self.c = TestClient(api.app)

    def tearDown(self):
        self.api.PDF_DIRS = self._dirs
        self.api._cache_pdfs.update(quando=0.0, indice={})
        self.api.ORTHANC_URL = ""
        self.tmp.cleanup()

    def test_pdf_abrir_e_baixar(self):
        r = self.c.get("/api/documentos/Laudo_A.pdf/pdf")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertIn("inline", r.headers["content-disposition"])
        r = self.c.get("/api/documentos/Laudo_A.pdf/pdf?baixar=true")
        self.assertIn("attachment", r.headers["content-disposition"])

    def test_pdf_nao_sai_da_pasta(self):
        for nome in ("..%2Fsegredo.txt", "segredo.txt", "nao_existe.pdf", "..%2F..%2Fetc%2Fpasswd"):
            with self.subTest(nome=nome):
                r = self.c.get(f"/api/documentos/{nome}/pdf")
                self.assertEqual(r.status_code, 404)
                self.assertNotIn(b"nao", r.content)

    def test_ids_invalidos_recusados(self):
        for url in ("/api/imagens/..%2Fsystem/series", "/api/imagens/abc/zip", "/api/imagens/instancia/x.png"):
            with self.subTest(url=url):
                self.assertEqual(self.c.get(url).status_code, 404)

    def test_series_em_ordem(self):
        resp = {
            f"/studies/{self.ID}": {"MainDicomTags": {"StudyDate": "20250723", "StudyDescription": "RX LOMBAR"}},
            f"/studies/{self.ID}/series": [
                {"ID": "s2", "MainDicomTags": {"SeriesNumber": "2", "Modality": "DX", "SeriesDescription": "PERFIL"}},
                {"ID": "s1", "MainDicomTags": {"SeriesNumber": "1", "Modality": "DX", "SeriesDescription": "AP"}},
            ],
            "/series/s1/instances": [{"ID": "i3", "MainDicomTags": {"InstanceNumber": "10"}}, {"ID": "i1", "MainDicomTags": {"InstanceNumber": "2"}}],
            "/series/s2/instances": [{"ID": "i9", "MainDicomTags": {}}],
        }
        with mock.patch.object(self.api, "_orthanc_get", side_effect=lambda c: resp[c]):
            r = self.c.get(f"/api/imagens/{self.ID}/series").json()
        self.assertEqual(r["data"], "2025-07-23")
        self.assertEqual([s["descricao"] for s in r["series"]], ["AP", "PERFIL"])
        self.assertEqual(r["series"][0]["imagens"], ["i1", "i3"])

    def test_zip_do_exame(self):
        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): self.close()
        with mock.patch.object(self.api, "_orthanc_get", return_value={"MainDicomTags": {"StudyDate": "20251031", "StudyDescription": "US ARTICULAR"}}), \
             mock.patch.object(self.api.urllib.request, "urlopen", return_value=Resp(b"PK\x03\x04zip")):
            r = self.c.get(f"/api/imagens/{self.ID}/zip")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"PK\x03\x04zip")
        self.assertIn('Imagens_2025-10-31_US_ARTICULAR.zip', r.headers["content-disposition"])

if __name__ == "__main__":
    unittest.main()


class HistoricoTests(unittest.TestCase):
    def test_nao_vaza_para_frase_vizinha(self):
        from achados import extrair_achados
        texto = (
            "RESSONANCIA MAGNETICA DA COLUNA CERVICAL\n"
            "Comparado ao exame anterior, a protrusao discal em C4-C5 apresenta resolucao completa.\n"
            "Ha discreto aumento da hernia discal em C6-C7, com contato radicular.\n"
            "Relatorio\nProtrusao em C4-C5 com resolucao. Hernia em C6-C7, aumentada.\n"
        )
        (a,) = extrair_achados("rm_cervical.pdf", None, texto)
        self.assertEqual(a.niveis_historicos, ["C4-C5"])
        self.assertIn("C6-C7", a.niveis)
        self.assertNotIn("C6-C7", a.niveis_historicos)

    def test_mesma_frase_marca_historico(self):
        from achados import extrair_achados
        texto = "RM LOMBAR\nRelatorio\nHernia em L4-L5, atualmente com resolucao completa do quadro."
        (a,) = extrair_achados("rm.pdf", None, texto)
        self.assertEqual(a.niveis_historicos, ["L4-L5"])


def _r(**kw):
    """Resultado minimo no formato do resultados.json (para consolidar/API)."""
    base = {"arquivo": "a.pdf", "data": "2025-01-01", "exame": "GLICOSE", "valor_texto": "", "valor_numerico": 90.0,
            "unidade": "mg/dL", "referencia": "", "ref_min": 70.0, "ref_max": 99.0, "classificacao": "dentro"}
    base.update(kw)
    return base


class UrinaSangueTests(unittest.TestCase):
    """1. Leucocitos/hemacias do EAS, sedimento e urocultura nao entram no hemograma."""

    SEDIMENTO = (
        "SEDIMENTO URINARIO QUANTITATIVO\nMaterial:\nUrina jato medio\nColeta:\n24/09/2025 - 08:00\n"
        "Leucocitos.........:\n2.100\n/mL\nAte 10.000 /mL\nHemacias...........:\n900\n/mL\nAte 10.000 /mL\n"
    )
    HEMOGRAMA = PainelTests.TEXTO

    def test_sedimento_vira_id_de_urina(self):
        res = {r.exame_id: r for r in A.extract_results(Path("u.pdf"), self.SEDIMENTO, None)}
        self.assertEqual(res["urina_leucocitos"].valor_numerico, 2100.0)
        self.assertEqual(res["urina_hemacias"].valor_numerico, 900.0)
        self.assertEqual(res["urina_leucocitos"].sistema, "rins")
        self.assertNotIn("leucocitos", res)
        self.assertNotIn("hemacias", res)

    def test_hemograma_continua_no_sangue(self):
        res = {r.exame_id for r in A.extract_results(Path("h.pdf"), self.HEMOGRAMA, None)}
        self.assertIn("leucocitos", res)
        self.assertIn("hemacias", res)

    def test_secao_ou_unidade_de_urina(self):
        for material, unidade in (("EAS / Urina", ""), ("UROCULTURA", ""), ("", "UFC/mL"), ("", "/campo"), ("", "p/mL")):
            self.assertEqual(identificar("Leucocitos", material, unidade)[0], "urina_leucocitos", (material, unidade))
        self.assertEqual(identificar("Hemacias", "", "/campo")[0], "urina_hemacias")
        self.assertEqual(identificar("Leucocitos", "Sangue total com EDTA", "/mm3")[0], "leucocitos")
        self.assertEqual(identificar("Hemacias", "Sangue", "milhoes/mm3")[0], "hemacias")

    def test_consolidar_reclassifica_json_antigo_pela_unidade(self):
        rs, _ = A.consolidar([_r(exame="Leucocitos", valor_numerico=100000.0, unidade="UFC/mL", data="2024-03-08")])
        self.assertEqual(rs[0]["exame_id"], "urina_leucocitos")

    def test_ponto_sem_unidade_fora_da_serie_de_sangue(self):
        rs, _ = A.consolidar([
            _r(arquivo="h1.pdf", exame="Leucocitos", valor_numerico=5000.0, unidade="/mm3", data="2025-01-01"),
            _r(arquivo="h2.pdf", exame="Leucocitos", valor_numerico=6000.0, unidade="/mm3", data="2025-02-01"),
            _r(arquivo="u.pdf", exame="Leucocitos", valor_numerico=25100.0, unidade="", data="2025-05-31"),
        ])
        sem = next(r for r in rs if r["valor_numerico"] == 25100.0)
        self.assertFalse(sem["grafico"])
        self.assertIn("/mm3", sem["motivo"])
        self.assertTrue(all(r["grafico"] for r in rs if r is not sem))


class IndiceTests(unittest.TestCase):
    """2. "Indice" sozinho nao junta sorologias diferentes."""

    TEXTO = (
        "ANTI-HBS\nMaterial:\nSoro\nColeta:\n10/02/2025\nIndice.............:\n12,50\nInferior a 1,00\n"
        "ANTI-HCV\nMaterial:\nSoro\nColeta:\n10/02/2025\nIndice.............:\n0,08\nInferior a 1,00\n"
    )

    def test_titulo_real_vem_das_linhas_acima(self):
        res = A.extract_results(Path("s.pdf"), self.TEXTO, None)
        ids = {r.exame_id for r in res}
        self.assertEqual(ids, {"anti_hbs_indice", "anti_hcv_indice"})
        self.assertTrue(all(r.grafico for r in res))

    def test_formato_resultado_com_titulo_indice(self):
        texto = ("ANTI-HBS\nMaterial:\nSoro\nColeta:\n10/02/2025\nINDICE\n \n \nResultado:\n12,50\n"
                 "Valor de Referencia:\nInferior a 1,00\n")
        res = A.extract_results(Path("s.pdf"), texto, None)
        self.assertEqual([r.exame_id for r in res], ["anti_hbs_indice"])

    def test_sem_titulo_nao_vai_para_o_grafico(self):
        self.assertEqual(A.resolver_generico("Indice", ["Material: Soro", "12,5"], 1), ("Indice", False))
        rs, _ = A.consolidar([_r(exame="Índice", valor_numerico=3.0, unidade="", ref_min=None, ref_max=1.0)])
        self.assertFalse(rs[0]["grafico"])
        self.assertEqual(rs[0]["exame_id"], "sem_titulo")

    def test_indice_nao_mistura_com_quantitativo(self):
        self.assertNotEqual(identificar("ANTI-HBS - Indice")[0], identificar("ANTI-HBS")[0])


class DuplicatasConflitosTests(unittest.TestCase):
    """3. (marcador, data, valor) repetido vira um ponto; valores diferentes vao para conflitos."""

    def test_mesmo_valor_um_ponto_com_todos_os_arquivos(self):
        rs, conf = A.consolidar([
            _r(arquivo="hemo_a.pdf", exame="Plaquetas", valor_numerico=202000.0, unidade="/mm3", data="2026-04-08"),
            _r(arquivo="hemo_b.pdf", exame="Plaquetas", valor_numerico=202000.0, unidade="/mm3", data="2026-04-08"),
        ])
        self.assertEqual(len(rs), 1)
        self.assertEqual(rs[0]["arquivos"], ["hemo_a.pdf", "hemo_b.pdf"])
        self.assertEqual(conf, [])

    def test_valores_diferentes_vao_para_conflitos(self):
        rs, conf = A.consolidar([
            _r(arquivo="a.pdf", exame="Tempo do paciente", valor_numerico=12.5, unidade="s", data="2024-04-16"),
            _r(arquivo="b.pdf", exame="Tempo do paciente", valor_numerico=13.1, unidade="s", data="2024-04-16"),
        ])
        self.assertEqual(len(conf), 1)
        self.assertEqual(conf[0]["exame_id"], "tp_paciente")
        self.assertEqual(sorted(v["valor"] for v in conf[0]["valores"]), [12.5, 13.1])
        self.assertEqual(sum(r["grafico"] for r in rs), 1)

    def test_ttpa_nao_se_mistura_com_tempo_de_protrombina(self):
        texto = ("TTPA - TEMPO DE TROMBOPLASTINA PARCIAL ATIVADA\nMaterial:\nPlasma\nColeta:\n16/04/2024\n"
                 "Tempo do paciente..:\n31,2\nsegundos\n25,0 a 35,0 segundos\n")
        res = A.extract_results(Path("c.pdf"), texto, None)
        self.assertEqual([r.exame_id for r in res], ["ttpa_paciente"])

    def test_idempotente(self):
        entrada = [_r(arquivo="a.pdf", valor_numerico=90.0), _r(arquivo="b.pdf", valor_numerico=91.0)]
        rs1, c1 = A.consolidar(entrada)
        rs2, c2 = A.consolidar(rs1)
        self.assertEqual(c1, c2)
        self.assertEqual([(r["valor_numerico"], r["grafico"]) for r in rs1], [(r["valor_numerico"], r["grafico"]) for r in rs2])


class ClassificacaoPorLimitesTests(unittest.TestCase):
    """4. classificacao sai SO de ref_min/ref_max."""

    def test_regra(self):
        self.assertEqual(A.classificar(0.5, 0.7, 1.3), "abaixo")
        self.assertEqual(A.classificar(1.4, 0.7, 1.3), "acima")
        self.assertEqual(A.classificar(1.3, 0.7, 1.3), "dentro")
        self.assertEqual(A.classificar(8.0, None, 5.0), "acima")
        self.assertEqual(A.classificar(8.0, 10.0, None), "abaixo")
        self.assertEqual(A.classificar(8.0, None, None), "nao determinado")

    def test_json_antigo_divergente_e_corrigido(self):
        casos = [
            _r(exame="CREATININA", valor_numerico=1.4, ref_min=0.7, ref_max=1.3, classificacao="dentro"),
            _r(exame="PROTEINA C REATIVA", valor_numerico=0.2, ref_min=None, ref_max=0.5, classificacao="nao determinado"),
            _r(exame="VHS", valor_numerico=25.0, ref_min=None, ref_max=15.0, classificacao="dentro"),
            _r(exame="ANTI-HBS", valor_numerico=250.0, ref_min=10.0, ref_max=None, classificacao="abaixo"),
            _r(exame="COLESTEROL LDL", valor_numerico=125.0, ref_min=None, ref_max=None, classificacao="acima"),
        ]
        rs, _ = A.consolidar(casos)
        got = {r["exame_id"]: r["classificacao"] for r in rs}
        self.assertEqual(got, {"creatinina": "acima", "pcr": "dentro", "vhs": "acima", "anti_hbs": "dentro", "ldl": "nao determinado"})

    def test_extracao_sempre_coerente_com_os_limites(self):
        textos = (PainelTests.TEXTO, UrinaSangueTests.SEDIMENTO, IndiceTests.TEXTO)
        for texto in textos:
            for r in A.extract_results(Path("x.pdf"), texto, None):
                self.assertEqual(r.classificacao, A.classificar(r.valor_numerico, r.ref_min, r.ref_max), r.exame)

    def test_meta_por_risco_sem_limites(self):
        ldl = "VALORES DE ALVO TERAPEUTICO SUGERIDO PARA CATEGORIA DE RISCO\n| BAIXO | INFERIOR A 115 mg/dL"
        self.assertEqual(A.limites_referencia(ldl), (None, None))


class UnidadeTests(unittest.TestCase):
    """5. Unidade nunca e texto do laudo."""

    def test_rejeita_texto_do_laudo(self):
        for lixo in ("Sr (a)", "Até 1,2", "Ate 1,2", ">= 39.000.000", "Notas:", "Nota", "Negativo", "Valor", "12", "a"):
            self.assertEqual(A.unidade_valida(lixo), "", lixo)

    def test_aceita_unidades_reais(self):
        for u in ("mg/dL", "/mm3", "milhoes/mm3", "%", "fL", "pg", "U/L", "UFC/mL", "x10³/µL", "mm/h", "segundos",
                  "µUI/mL", "mEq/L", "/campo", "ng/dL"):
            self.assertEqual(A.unidade_valida(u), u, u)

    def test_unidade_da_referencia(self):
        self.assertEqual(A.unidade_da_referencia("Valor de referencia: 70 a 99 mg/dL"), "mg/dL")
        self.assertEqual(A.unidade_da_referencia("Inferior a 1,00"), "")
        self.assertEqual(A.unidade_da_referencia("Ate 1,2 mg/dL"), "mg/dL")

    def test_painel_nao_pega_lixo_como_unidade(self):
        texto = ("CREATININA\nMaterial:\nSoro\nColeta:\n10/02/2025\nCreatinina.........:\n1,10\nSr (a)\n0,70 a 1,30 mg/dL\n")
        r = A.extract_results(Path("x.pdf"), texto, None)[0]
        self.assertEqual((r.unidade, r.unidade_fonte), ("mg/dL", "referencia"))

    def test_resultado_sem_unidade_usa_referencia(self):
        texto = "GLICOSE\nMaterial:\nSoro\nColeta:\n11/03/2025\nResultado:\n95\nValor de Referencia:\n70 a 99 mg/dL\n"
        r = A.extract_results(Path("x.pdf"), texto, None)[0]
        self.assertEqual(r.unidade, "mg/dL")

    def test_padrao_so_para_exibicao(self):
        rs, _ = A.consolidar([_r(exame="GLICOSE", unidade="Notas:", referencia="")])
        self.assertEqual((rs[0]["unidade"], rs[0]["unidade_fonte"]), ("mg/dL", "padrao"))
        # na reexecucao a padrao nao conta como unidade real da serie
        rs2, _ = A.consolidar(rs + [_r(arquivo="b.pdf", data="2025-02-01", unidade="mg/dL"),
                                    _r(arquivo="c.pdf", data="2025-03-01", unidade="mg/dL")])
        self.assertFalse(next(r for r in rs2 if r["arquivo"] == "a.pdf")["grafico"])


class ApiSerieTests(unittest.TestCase):
    """A API aplica as mesmas regras ao ler o resultados.json (e os envios)."""

    def test_serie_sem_duplicata_nem_urina(self):
        import importlib
        import json as _json
        import os
        import tempfile as _tf
        with _tf.TemporaryDirectory() as res:
            dados = {"arquivos": [], "achados": [], "resultados": [
                _r(arquivo="h1.pdf", exame="Leucocitos", valor_numerico=5000.0, unidade="/mm3", data="2024-05-01", ref_min=3700.0, ref_max=11000.0),
                _r(arquivo="h2.pdf", exame="Leucocitos", valor_numerico=5000.0, unidade="/mm3", data="2024-05-01", ref_min=3700.0, ref_max=11000.0),
                _r(arquivo="h3.pdf", exame="Leucocitos", valor_numerico=6000.0, unidade="/mm3", data="2024-06-01", ref_min=3700.0, ref_max=11000.0),
                _r(arquivo="u.pdf", exame="Leucocitos", valor_numerico=100000.0, unidade="UFC/mL", data="2024-03-08"),
                _r(arquivo="s.pdf", exame="Indice", valor_numerico=0.1, unidade=""),
            ]}
            (Path(res) / "resultados.json").write_text(_json.dumps(dados), encoding="utf-8")
            os.environ["ANALISADOR_RESULT_DIR"] = res
            import api
            api = importlib.reload(api)
            try:
                pontos = api.serie("leucocitos")["pontos"]
                self.assertEqual([(p["data"], p["valor"]) for p in pontos], [("2024-05-01", 5000.0), ("2024-06-01", 6000.0)])
                self.assertEqual(pontos[0]["arquivos"], ["h1.pdf", "h2.pdf"])
                self.assertEqual(api.serie("urina_leucocitos")["pontos"][0]["valor"], 100000.0)
                self.assertNotIn("sem_titulo", {m["id"] for m in api.marcadores()})
                self.assertEqual(api.conflitos(), [])
            finally:
                os.environ.pop("ANALISADOR_RESULT_DIR", None)
                importlib.reload(api)


@unittest.skipUnless(shutil.which("node"), "precisa do node para rodar o format.ts")
class EixoYTests(unittest.TestCase):
    """6. A largura do eixo Y cabe o maior rotulo ("100.000" nao vira "00.000")."""

    def _largura(self, ticks):
        import subprocess
        js = (f"import('./frontend/src/format.ts').then(m => console.log(m.larguraEixoY({ticks}) + ' ' + "
              f"m.fmtNum(Math.max(...{ticks}))))")
        out = subprocess.run(["node", "--experimental-strip-types", "--no-warnings", "-e", js], cwd=Path(__file__).parent,
                             capture_output=True, text=True, timeout=30, check=False)
        if out.returncode != 0:
            self.skipTest(f"node sem suporte a .ts: {out.stderr[:200]}")
        largura, rotulo = out.stdout.split()
        return int(largura), rotulo

    def test_cresce_com_o_rotulo(self):
        grande, rotulo = self._largura([0, 25000, 50000, 75000, 100000])
        pequena, _ = self._largura([0, 1, 2])
        self.assertEqual(rotulo, "100.000")
        self.assertGreaterEqual(grande, len(rotulo) * 7 + 8)  # ~7px por caractere a 12px
        self.assertLess(pequena, grande)


class UrinaLayoutRealTests(unittest.TestCase):
    """Layouts reais do laboratorio (PARCIAL DE URINA e BACTERIOSCOPIA - URINA)."""

    PARCIAL = (
        "PARCIAL DE URINA\n \nMaterial:\nUrina simples\nColeta:\n24/09/2025 - 09:39:52\n"
        "Analise de Elementos Figurados\n \nLeucócitos................p/mL:\n900\nInferior a 25.000/mL\n"
        "Hemácias..................p/mL:\n500\nInferior a 23.000/mL\n"
        "Células Epiteliais........p/mL:\n1.200\nInferior a 31.000/mL\n"
    )
    GRAM = (
        "BACTERIOSCOPIA - URINA\n \nMaterial:\nUrina simples\nColeta:\n24/09/2025 - 09:39:54\n"
        "Leucócitos Polimorfonucleares:\n0\n \nCélulas Epiteliais...........:\n0\n"
    )

    def test_unidade_dentro_do_rotulo(self):
        res = {r.exame_id: r for r in A.extract_results(Path("u.pdf"), self.PARCIAL, None)}
        self.assertEqual((res["urina_leucocitos"].valor_numerico, res["urina_leucocitos"].unidade), (900.0, "p/mL"))
        self.assertEqual(res["urina_leucocitos"].unidade_fonte, "laudo")
        self.assertEqual(res["urina_leucocitos"].exame, "Leucócitos")
        self.assertEqual(res["urina_hemacias"].valor_numerico, 500.0)
        self.assertEqual(res["urina_leucocitos"].coleta_hora, "09:39")

    def test_gram_nao_entra_na_serie_por_ml(self):
        ids = {r.exame_id for r in A.extract_results(Path("u.pdf"), self.GRAM, None)}
        self.assertIn("urina_gram_leucocitos", ids)
        self.assertNotIn("urina_leucocitos", ids)
        self.assertNotIn("leucocitos", ids)

    def test_duas_coletas_no_dia_grafico_fica_com_a_mais_recente(self):
        rs, conf = A.consolidar([
            _r(arquivo="x.pdf", exame="Hemoglobina", valor_numerico=17.2, unidade="g/dL", data="2024-05-01", coleta_hora="18:53"),
            _r(arquivo="x.pdf", exame="Hemoglobina", valor_numerico=15.5, unidade="g/dL", data="2024-05-01", coleta_hora="20:35"),
        ])
        self.assertEqual([r["valor_numerico"] for r in rs if r["grafico"]], [15.5])
        self.assertEqual(conf[0]["escolhido"], 15.5)


class CoagulogramaTests(unittest.TestCase):
    """COAGULOGRAMA com TAP e KPTT no mesmo bloco (laudo real de 2026)."""

    TEXTO = (
        "COAGULOGRAMA\n \nMaterial:\nSangue total com EDTA e plasma com\ncitrato\nColeta:\n08/04/2026 - 11:55:16\n"
        "Valor de referência:\nTEMPO DE PROTROMBINA (TAP)\n \nTempo paciente.......:\n13,3\n \nsegundos\n11,7 a 15,3 segundos\n \n"
        "RNI..................:\n1,00\n \n \nAté 1,2\n \n"
        "|                     INDICAÇÃO\n         | RNI |            |\n"
        "TEMPO DE TROMBOPLASTINA PARCIAL ATIVADO (KPTT)\n \nTempo paciente.......:\n29,3\n \nsegundos\n25,0 a 36,0 segundos\n \n"
        "Tempo normal.........:\n33,5\n \nsegundos\n \n \nRazão paciente/normal:\n0,87\n \n \nRazão paciente/normal até 1,30\n \n"
        "Contagem de plaquetas:\n201.000\n \n/mm3\n150.000 a 450.000 /mm3\n"
    )

    def test_tap_e_kptt_separados(self):
        res = {r.exame_id: r for r in A.extract_results(Path("c.pdf"), self.TEXTO, None)}
        self.assertEqual(res["tp_paciente"].valor_numerico, 13.3)
        self.assertEqual(res["ttpa_paciente"].valor_numerico, 29.3)
        self.assertEqual(res["ttpa_normal"].valor_numerico, 33.5)
        self.assertEqual(res["ttpa_razao"].valor_numerico, 0.87)
        self.assertEqual(res["tp_rni"].valor_numerico, 1.0)
        self.assertEqual(res["plaquetas"].valor_numerico, 201000.0)
        self.assertEqual(res["tp_paciente"].unidade, "segundos")
        self.assertEqual(res["tp_rni"].unidade, "")  # "Até 1,2" nao e unidade
        self.assertNotIn("tp_razao", res)


class PesquisaLeucocitosTests(unittest.TestCase):
    TEXTO = ("PESQUISA DE LEUCÓCITOS\n \nMaterial:\nUrina primeiro jato\nColeta:\n24/09/2025 - 09:39:56\n"
             "Método  :\nCitometria de fluxo\n \nResultado:\n2.100\n \n/mL\n \nValor de Referência:\nAté 10.000/mL\n")

    def test_primeiro_jato_nao_conflita_com_sedimento(self):
        r = A.extract_results(Path("p.pdf"), self.TEXTO, None)[0]
        self.assertEqual((r.exame_id, r.valor_numerico, r.ref_max), ("urina_pesquisa_leucocitos", 2100.0, 10000.0))
        _, conf = A.consolidar([A.asdict(r)] + [A.asdict(x) for x in A.extract_results(Path("u.pdf"), UrinaLayoutRealTests.PARCIAL, None)])
        self.assertEqual(conf, [])

    def test_unidade_equivalente(self):
        self.assertEqual(A.chave_unidade("p/mL"), A.chave_unidade("/mL"))
        self.assertEqual(A.chave_unidade("milhões/mm³"), A.chave_unidade("milhoes/mm3"))


class GrafiaUnidadeTests(unittest.TestCase):
    def test_serie_usa_uma_grafia_so(self):
        rs, _ = A.consolidar([
            _r(arquivo="a.pdf", data="2025-01-01", exame="TSH", valor_numerico=1.0, unidade="µIU/mL"),
            _r(arquivo="b.pdf", data="2025-02-01", exame="TSH", valor_numerico=1.1, unidade="µIU/mL"),
            _r(arquivo="c.pdf", data="2025-03-01", exame="TSH", valor_numerico=0.9, unidade="uIU/mL"),
            _r(arquivo="d.pdf", data="2025-01-01", exame="HDL", valor_numerico=40.0, unidade="mg/dL"),
            _r(arquivo="e.pdf", data="2025-02-01", exame="HDL", valor_numerico=35.0, unidade="mg/dl"),
        ])
        por_id = defaultdict(set)
        for r in rs:
            por_id[r["exame_id"]].add(r["unidade"])
        self.assertEqual(por_id["tsh"], {"µIU/mL"})
        self.assertEqual(len(por_id["hdl"]), 1)

    def test_resultado_textual_nao_vira_titulo(self):
        linhas = ["ANTICORPO ANTI-HEPATITE C", "Material: Soro", "NÃO REAGENTE", "Indice:"]
        self.assertEqual(A.titulo_acima(linhas, 3), "ANTICORPO ANTI-HEPATITE C")
        self.assertEqual(identificar("ANTICORPO ANTI-HEPATITE C - Indice")[0], "anti_hcv_indice")
