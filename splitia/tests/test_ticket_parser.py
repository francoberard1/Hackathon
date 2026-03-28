import unittest

from splitia.logic.ticket_parser import extract_candidate_lines, normalize_ocr_text, parse_ticket_text


ITALIAN_RECEIPT = """
TRATTORIA DONNA CONCETTA
DEMETRA S.R.L.
VIA AMERIGO VESPUCCI, 11
20123 MILANO (MI)
TEL. 375 9108923
P.IVA 10666140966

GENTILE OSPITE, IL SUO CONTO

Tavolo: 1

3 COPERTO CENA 6.00
1 ACQUA NATURALE 2.50
1 ACQUA FRIZZANTE 2.50
2 CAFFE ESPRESSO 3.00
1 INVOLTINI MELANZANE 8.00
3 GNOCCHETTI ALLO SCARPARIELLO 39.00

Totale EUR 61.00
"""

SPANISH_RECEIPT = """
RESTAURANTE EL PUENTE
CALLE MAYOR 123
TEL 34911222333

2 CUBIERTO 4,00
1 AGUA MINERAL 2,50
1 CAFE DOBLE 3,20
1 PROPINA 1,30

TOTAL 11,00
"""

ENGLISH_RECEIPT = """
CITY DINER
45 KING STREET
PHONE 5551234567

1 SERVICE CHARGE 3.00
2 WATER 5.00
1 COFFEE 4.50

TOTAL 12.50
"""

NOISY_RECEIPT = """
OSTERIA ROMA
VIA GARIBALDI 8
TEL 39021234567

1x ACQUA FRIZZANTE .... 2.50
1 INVOLTINI MELANZANE EUR 8,00
3 COPERTO CENA *** 6.00

TOTALE 16,50
"""


class TicketParserTests(unittest.TestCase):
    def test_parses_full_italian_receipt(self):
        parsed = parse_ticket_text(ITALIAN_RECEIPT)

        self.assertEqual(len(parsed["items"]), 6)
        self.assertEqual(parsed["subtotal"], 61.0)
        self.assertEqual(parsed["total_detected"], 61.0)
        self.assertFalse(parsed["warnings"])
        self.assertIn("3 COPERTO CENA", [item["name"] for item in parsed["items"]])
        self.assertIn("1 INVOLTINI MELANZANE", [item["name"] for item in parsed["items"]])

    def test_keeps_restaurant_lines_in_spanish(self):
        parsed = parse_ticket_text(SPANISH_RECEIPT)

        names = [item["name"] for item in parsed["items"]]
        self.assertEqual(names, ["2 CUBIERTO", "1 AGUA MINERAL", "1 CAFE DOBLE", "1 PROPINA"])
        self.assertEqual(parsed["subtotal"], 11.0)
        self.assertEqual(parsed["total_detected"], 11.0)

    def test_keeps_restaurant_lines_in_english(self):
        parsed = parse_ticket_text(ENGLISH_RECEIPT)

        names = [item["name"] for item in parsed["items"]]
        self.assertEqual(names, ["1 SERVICE CHARGE", "2 WATER", "1 COFFEE"])
        self.assertEqual(parsed["subtotal"], 12.5)
        self.assertEqual(parsed["total_detected"], 12.5)

    def test_tolerates_light_ocr_noise(self):
        parsed = parse_ticket_text(NOISY_RECEIPT)

        names = [item["name"] for item in parsed["items"]]
        self.assertEqual(names, ["1x ACQUA FRIZZANTE", "1 INVOLTINI MELANZANE EUR", "3 COPERTO CENA"])
        self.assertEqual(parsed["subtotal"], 16.5)
        self.assertEqual(parsed["total_detected"], 16.5)

    def test_excludes_header_lines_without_prices(self):
        normalized = normalize_ocr_text(ITALIAN_RECEIPT)
        candidate_lines = extract_candidate_lines(normalized)

        self.assertNotIn("Tavolo: 1", candidate_lines)
        self.assertNotIn("VIA AMERIGO VESPUCCI, 11", candidate_lines)
        self.assertNotIn("TEL. 375 9108923", candidate_lines)

    def test_warns_when_total_exceeds_detected_items(self):
        parsed = parse_ticket_text(
            """
            BISTRO TEST
            1 WATER 2.50
            TOTAL 5.00
            """
        )

        self.assertIn("Some item lines may be missing", parsed["warnings"][0])


if __name__ == "__main__":
    unittest.main()
