# aqilas

Python client for the Aqilas SMS API.

## Installation

```bash
pip install aqilas
```

For local development:

```bash
pip install -e .[dev]
```

## Quick start

```python
from aqilas import AqilasClient, AqilasError

client = AqilasClient(token="your-token")

try:
	credit = client.get_credit()
	print(credit.credit, credit.currency)

	sent = client.send_sms(
		sender="AQILAS",
		receivers=["+22670000000"],
		content="Bonjour depuis Aqilas",
	)
	print(sent.bulk_id)

	status = client.get_sms_status(sent.bulk_id)
	print(status.results)
finally:
	client.close()
```

## Shared client helpers

The package also exposes module-level helpers for simple scripts.

```python
from aqilas import AqilasError, get_credit, init_client, send_sms

init_client(token="your-token")

try:
	print(get_credit().credit)
	send_sms(
		sender="AQILAS",
		receivers=["+22670000000"],
		content="Bonjour",
	)
except AqilasError as exc:
	print(f"Request failed: {exc}")
```

## Error model

The client raises explicit exceptions instead of returning error objects.

- `AqilasValidationError`: invalid caller input
- `AqilasNotInitializedError`: shared client not initialized
- `AqilasNetworkError`: request transport failure
- `AqilasResponseError`: API error or invalid response payload

All of them inherit from `AqilasError`.

## Validation rules

- `token` must be a non-empty string.
- `base_url` must start with `http://` or `https://`.
- `sender` must be 2 to 11 characters and contain only letters, digits, spaces, `_` or `-`.
- `receivers` must be a non-empty list of international phone numbers such as `+22670000000`.
- `content` must be non-empty and at most 1600 characters.
- `bulkid` must be 3 to 128 characters and contain only letters, digits, `.`, `_` or `-`.

## Development

Run the test suite with:

```bash
pytest
```
