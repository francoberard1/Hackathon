import io
import json
import unittest
from unittest.mock import patch

from splitia.app import create_app
from splitia.logic import data_access, models
from splitia.logic.receipt_review import ReceiptReviewValidationError, validate_receipt_review_submission
from splitia.logic.receipt_service import (
    ReceiptAuthenticationError,
    ReceiptConfigurationError,
    ReceiptResponseError,
    ReceiptTransportError,
    build_receipt_draft,
)


class ReceiptReviewLogicTests(unittest.TestCase):
    def test_computes_exact_shares_with_tax_and_tip_splits(self):
        members = [
            {"id": 1, "name": "Ana"},
            {"id": 2, "name": "Ben"},
            {"id": 3, "name": "Caro"},
        ]
        form = FakeMultiDict(
            {
                "description": "Dinner at Demo",
                "payer_id": "1",
                "subtotal_amount": "35.00",
                "tax_amount": "3.00",
                "tip_amount": "2.00",
                "total_amount": "40.00",
                "currency": "ARS",
                "item_name[]": ["Burger", "Pasta"],
                "item_amount[]": ["20.00", "15.00"],
                "item_user_id[]": ["1", "2"],
                "item_enabled[]": ["1", "1"],
                "tax_split_participants": ["1", "2", "3"],
                "tip_split_participants": ["1", "2"],
            }
        )

        result = validate_receipt_review_submission(form, members)

        self.assertEqual(result["participant_ids"], [1, 2, 3])
        self.assertEqual(
            result["share_amounts_by_user"],
            {
                1: 22.0,
                2: 17.0,
                3: 1.0,
            },
        )

    def test_rejects_total_mismatch(self):
        members = [{"id": 1, "name": "Ana"}]
        form = FakeMultiDict(
            {
                "description": "Coffee",
                "payer_id": "1",
                "subtotal_amount": "5.00",
                "tax_amount": "0.00",
                "tip_amount": "0.00",
                "total_amount": "6.00",
                "item_name[]": ["Coffee"],
                "item_amount[]": ["5.00"],
                "item_user_id[]": ["1"],
                "item_enabled[]": ["1"],
            }
        )

        with self.assertRaises(ReceiptReviewValidationError):
            validate_receipt_review_submission(form, members)


class ReceiptRouteTests(unittest.TestCase):
    def setUp(self):
        models.reset_data()
        self.group_id = models.create_group("Hackathon")
        self.ana_id = models.create_user("Ana", self.group_id)
        self.ben_id = models.create_user("Ben", self.group_id)
        self.caro_id = models.create_user("Caro", self.group_id)
        self.app = create_app()
        self.client = self.app.test_client()

    def tearDown(self):
        models.reset_data()

    def test_add_expense_page_renders_receipt_review_container(self):
        response = self.client.get(f"/add_expense/{self.group_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Review Ticket Draft", response.data)

    def test_receipt_draft_requires_image(self):
        response = self.client.post("/api/receipt/draft", data={})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Missing uploaded image file.")
        self.assertEqual(response.get_json()["error_code"], "invalid_receipt_upload")

    def test_receipt_draft_returns_json_when_extraction_succeeds(self):
        draft = {
            "description": "Dinner at Parador",
            "total_amount": 20.0,
            "currency": "ARS",
            "payer_name": "",
            "participants": [],
            "tip_amount": 2.0,
            "notes": "Review required",
            "confidence": 0.82,
            "needs_review": True,
            "merchant_name": "Parador",
            "subtotal_amount": 16.0,
            "tax_amount": 2.0,
            "extracted_items": [{"name": "Milanesa", "amount": 16.0}],
        }

        with patch("splitia.app.build_receipt_draft", return_value=draft):
            response = self.client.post(
                "/api/receipt/draft",
                data={"receipt_image": (io.BytesIO(b"fake-image"), "receipt.png")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["merchant_name"], "Parador")

    def test_receipt_draft_returns_clear_ssl_error(self):
        with patch(
            "splitia.app.build_receipt_draft",
            side_effect=ReceiptTransportError("TLS certificate verification failed while contacting Gemini."),
        ):
            response = self.client.post(
                "/api/receipt/draft",
                data={"receipt_image": (io.BytesIO(b"fake-image"), "receipt.png")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["error_code"], "gemini_transport_error")

    def test_receipt_draft_returns_clear_auth_error(self):
        with patch(
            "splitia.app.build_receipt_draft",
            side_effect=ReceiptAuthenticationError("Gemini rejected the configured API key."),
        ):
            response = self.client.post(
                "/api/receipt/draft",
                data={"receipt_image": (io.BytesIO(b"fake-image"), "receipt.png")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["error_code"], "gemini_auth_error")

    def test_receipt_draft_returns_clear_configuration_error(self):
        with patch(
            "splitia.app.build_receipt_draft",
            side_effect=ReceiptConfigurationError("GEMINI_API_KEY contains a placeholder value."),
        ):
            response = self.client.post(
                "/api/receipt/draft",
                data={"receipt_image": (io.BytesIO(b"fake-image"), "receipt.png")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["error_code"], "receipt_configuration_error")

    def test_receipt_draft_returns_clear_response_error(self):
        with patch(
            "splitia.app.build_receipt_draft",
            side_effect=ReceiptResponseError("Gemini returned an invalid structured response."),
        ):
            response = self.client.post(
                "/api/receipt/draft",
                data={"receipt_image": (io.BytesIO(b"fake-image"), "receipt.png")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["error_code"], "gemini_response_error")

    def test_receipt_review_creates_expense_with_exact_shares(self):
        response = self.client.post(
            f"/add_expense/{self.group_id}/receipt/review",
            data={
                "description": "Dinner at Demo",
                "merchant_name": "Demo",
                "currency": "ARS",
                "subtotal_amount": "35.00",
                "tax_amount": "3.00",
                "tip_amount": "2.00",
                "total_amount": "40.00",
                "payer_id": str(self.ana_id),
                "expense_date": "2026-03-28",
                "notes": "Reviewed",
                "item_name[]": ["Burger", "Pasta"],
                "item_amount[]": ["20.00", "15.00"],
                "item_user_id[]": [str(self.ana_id), str(self.ben_id)],
                "item_enabled[]": ["1", "1"],
                "tax_split_participants": [str(self.ana_id), str(self.ben_id), str(self.caro_id)],
                "tip_split_participants": [str(self.ana_id), str(self.ben_id)],
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(data_access.expenses), 1)
        shares = sorted(data_access.expense_shares.values(), key=lambda share: share["user_id"])
        self.assertEqual(
            [(share["user_id"], round(share["amount"], 2)) for share in shares],
            [
                (self.ana_id, 22.0),
                (self.ben_id, 17.0),
                (self.caro_id, 1.0),
            ],
        )

    def test_manual_add_expense_still_uses_explicit_share_inputs(self):
        response = self.client.post(
            f"/add_expense/{self.group_id}",
            data={
                "description": "Taxi",
                "total_amount": "12.00",
                "payer_id": str(self.ana_id),
                f"participant_{self.ana_id}": "on",
                f"participant_{self.ben_id}": "on",
                f"share_amount_{self.ana_id}": "6.00",
                f"share_amount_{self.ben_id}": "6.00",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        shares = sorted(data_access.expense_shares.values(), key=lambda share: share["user_id"])
        self.assertEqual(
            [(share["user_id"], round(share["amount"], 2)) for share in shares],
            [
                (self.ana_id, 6.0),
                (self.ben_id, 6.0),
            ],
        )


class ReceiptServiceTests(unittest.TestCase):
    @patch.dict("os.environ", {"GEMINI_API_KEY": "AIzaSyValidLookingButRejectedKey123456789012"}, clear=False)
    @patch("splitia.logic.receipt_service.request.urlopen")
    def test_invalid_api_key_400_is_classified_as_auth_error(self, mock_urlopen):
        provider_error = error_payload("INVALID_ARGUMENT", "API key not valid. Please pass a valid API key.")
        mock_urlopen.side_effect = __import__("urllib.error").error.HTTPError(
            "https://example.com",
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(provider_error),
        )

        with self.assertRaises(ReceiptAuthenticationError):
            build_receipt_draft(FakeUpload())


class FakeMultiDict(dict):
    def get(self, key, default=None):
        value = super().get(key, default)
        if isinstance(value, list):
            return value[0] if value else default
        return value

    def getlist(self, key):
        value = super().get(key, [])
        if isinstance(value, list):
            return value
        if value == "":
            return []
        return [value]


class FakeUpload:
    filename = "receipt.png"
    mimetype = "image/png"

    def __init__(self, image_bytes: bytes = b"fake-image"):
        self._image_bytes = image_bytes
        self.stream = io.BytesIO(image_bytes)

    def read(self):
        return self._image_bytes


def error_payload(status: str, message: str) -> bytes:
    return json.dumps({"error": {"status": status, "message": message}}).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
