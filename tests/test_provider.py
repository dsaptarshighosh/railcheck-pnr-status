import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from api.provider import ApiMitraProvider, ProviderError, normalize_api_mitra
from api.validation import is_valid_pnr


VALID_RESPONSE = {
    "status": "ok",
    "pnr": "1234567890",
    "train_number": "13185",
    "train_name": "GANGA SAGAR EXP",
    "travel_date": "05-08-2026",
    "from": {"code": "ASN", "name": "Asansol Junction"},
    "to": {"code": "JYG", "name": "Jaynagar"},
    "chart_prepared": False,
    "passengers": [
        {"number": 1, "booking_status": "WL/14/GN", "current_status": "RAC", "coach": "B1", "berth_number": 52}
    ],
}


class StubResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int) -> bytes:
        return self.payload


class NormalizeTests(unittest.TestCase):
    def test_pnr_validation_requires_exactly_ten_ascii_digits(self):
        self.assertTrue(is_valid_pnr("6711667640"))
        for invalid in ("123456789", "12345678901", "12345abc90", "１２３４５６７８９０", ""):
            self.assertFalse(is_valid_pnr(invalid), invalid)

    def test_maps_provider_fields_without_filling_undocumented_schedule(self):
        result = normalize_api_mitra(VALID_RESPONSE)
        self.assertEqual(result["journeyDate"], "05 Aug 2026")
        self.assertEqual(result["from"], "Asansol Junction (ASN)")
        self.assertEqual(result["passengers"][0]["bookingStatus"], "WL/14/GN")
        self.assertEqual(result["passengers"][0]["currentStatus"], "RAC")
        self.assertEqual(result["passengers"][0]["coach"], "B1")
        self.assertEqual(result["passengers"][0]["berth"], "52")
        self.assertIsNone(result["departure"])
        self.assertIsNone(result["arrival"])
        self.assertEqual(result["chart"], "Not prepared")

    def test_extracts_confirmed_coach_and_berth_from_documented_status_text(self):
        payload = {**VALID_RESPONSE, "passengers": [{"number": 1, "booking_status": "CNF B1 52", "current_status": "CNF"}]}
        result = normalize_api_mitra(payload)
        self.assertEqual(result["passengers"][0]["coach"], "B1")
        self.assertEqual(result["passengers"][0]["berth"], "52")

    def test_rejects_empty_or_malformed_passengers(self):
        with self.assertRaises(ValueError):
            normalize_api_mitra({**VALID_RESPONSE, "passengers": []})
        with self.assertRaises(ValueError):
            normalize_api_mitra({**VALID_RESPONSE, "passengers": [{"number": 1}]})


class ProviderTests(unittest.TestCase):
    @patch("api.provider.urlopen")
    def test_calls_documented_endpoint_with_pnr_query_and_parses_json(self, mocked_urlopen):
        mocked_urlopen.return_value = StubResponse(json.dumps(VALID_RESPONSE).encode())
        result = ApiMitraProvider(api_key="test-key")._lookup_sync("1234567890")
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.apimitra.in/train/pnr?number=1234567890")
        self.assertEqual(request.get_header("X-api-key"), "test-key")
        self.assertEqual(result["train_number"], "13185")

    @patch("api.provider.urlopen")
    def test_maps_rate_limit_to_actionable_error(self, mocked_urlopen):
        mocked_urlopen.side_effect = HTTPError("https://api.apimitra.in/train/pnr", 429, "limited", {}, io.BytesIO())
        with self.assertRaises(ProviderError) as raised:
            ApiMitraProvider(api_key="test-key")._lookup_sync("1234567890")
        self.assertEqual(raised.exception.status_code, 429)

    @patch("api.provider.urlopen", side_effect=TimeoutError())
    def test_maps_timeout_to_gateway_timeout(self, _mocked_urlopen):
        with self.assertRaises(ProviderError) as raised:
            ApiMitraProvider(api_key="test-key")._lookup_sync("1234567890")
        self.assertEqual(raised.exception.status_code, 504)

    @patch("api.provider.urlopen")
    def test_rejects_unexpected_json(self, mocked_urlopen):
        mocked_urlopen.return_value = StubResponse(b"[]")
        with self.assertRaises(ProviderError) as raised:
            ApiMitraProvider(api_key="test-key")._lookup_sync("1234567890")
        self.assertEqual(raised.exception.status_code, 502)

    @patch("api.provider.urlopen")
    def test_missing_key_fails_without_sending_request(self, mocked_urlopen):
        with patch.dict("os.environ", {"API_MITRA_API_KEY": ""}):
            with self.assertRaises(ProviderError) as raised:
                ApiMitraProvider(api_key="")._lookup_sync("1234567890")
        self.assertEqual(raised.exception.status_code, 503)
        mocked_urlopen.assert_not_called()

    @patch("api.provider.urlopen")
    def test_maps_provider_key_required_response(self, mocked_urlopen):
        mocked_urlopen.return_value = StubResponse(json.dumps({"error": "API key required", "code": "api_key_required"}).encode())
        with self.assertRaises(ProviderError) as raised:
            ApiMitraProvider(api_key="test-key")._lookup_sync("1234567890")
        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("API_MITRA_API_KEY", raised.exception.public_message)


if __name__ == "__main__":
    unittest.main()
