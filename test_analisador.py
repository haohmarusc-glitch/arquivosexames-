import unittest
from unittest import mock

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
        self.assertEqual(classification(200.0, sel), "acima")
        self.assertEqual(classification(160.0, sel), "nao determinado")  # acima com jejum, dentro sem jejum

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
        z = _zip({"DICOM/S1/IM0001": dcm, "DICOMDIR": b"x" * 200, "Viewer.exe": b"MZ" + b"0" * 300, "outro.zip": _zip({"IM2": dcm})})
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
