import unittest

from splitia.logic.ticket_ocr import _build_language_candidates, _score_ocr_candidate_text, _score_ocr_text


class TicketOcrHelperTests(unittest.TestCase):
    def test_builds_multilingual_candidates_from_available_languages(self):
        candidates = _build_language_candidates(["eng", "ita", "spa", "osd"])

        self.assertEqual(candidates[0], "eng+spa+ita")
        self.assertIn("eng", candidates)
        self.assertIn("spa", candidates)
        self.assertIn("ita", candidates)

    def test_falls_back_to_english_when_language_list_is_empty(self):
        self.assertEqual(_build_language_candidates([]), ["eng"])

    def test_scores_receipt_like_text_above_empty_text(self):
        rich_score = _score_ocr_text("1 WATER 2.50\n2 COFFEE 5.00\nTOTAL 7.50")
        empty_score = _score_ocr_text("")

        self.assertGreater(rich_score, empty_score)

    def test_prefers_candidate_with_more_parsed_items_and_better_total_match(self):
        coherent = _score_ocr_candidate_text(
            "3 COPERTO CENA 6.00\n1 ACQUA NATURALE 2.50\n1 ACQUA FRIZZANTE 2.50\n2 CAFFE ESPRESSO 3.00\n1 INVOLTINI MELANZANE 8.00\n3 GNOCCHETTI ALLO SCARPARIELLO 39.00\nTOTALE 61.00"
        )
        distorted = _score_ocr_candidate_text(
            "1 ACQUA NATURALE 2.50\n1 ACQUA FRIZZANTE 2.50\n2 CAFFE ESPRESSO 31.00\n3 GNOCCHETTI ALLO SCARPARTELLC 99.00\nTOTALE 135.00"
        )

        self.assertGreater(coherent, distorted)


if __name__ == "__main__":
    unittest.main()
