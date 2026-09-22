import unittest

from analisar_exames import classification, parse_number


class AnalyzerTests(unittest.TestCase):
    def test_decimal_comma(self):
        self.assertEqual(parse_number("519,61"), 519.61)

    def test_range(self):
        self.assertEqual(classification(3.0, "Valor de Referencia: 0 a 5,0 mg/L"), "dentro")
        self.assertEqual(classification(7.0, "Valor de Referencia: 0 a 5,0 mg/L"), "acima")

    def test_upper_limit(self):
        self.assertEqual(classification(3.0, "Inferior ou igual a 5,0 mg/L"), "dentro")
        self.assertEqual(classification(6.0, "Inferior ou igual a 5,0 mg/L"), "acima")


if __name__ == "__main__":
    unittest.main()
