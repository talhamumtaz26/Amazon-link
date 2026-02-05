# Amazon Link Tracker

Track Amazon product price and stock status from a Google Sheet. This repo includes a simple Python script that reads product URLs, fetches the product page, parses the current price/availability, writes updates back to the sheet, and optionally sends a webhook notification when something changes.

> **Note:** Amazon pages are protected by anti-bot measures. This script uses basic HTML parsing and may fail for some products or regions. For production use, consider Amazon's Product Advertising API or a dedicated scraping service.

## Sheet layout

Create a Google Sheet with the following header row in the first worksheet:

| URL | Title | Last Price | Last Stock | Last Checked | Notes |
| --- | ----- | ---------- | ---------- | ------------ | ----- |

Only the **URL** column is required. The script will populate the other columns.

## Setup

1. **Create a Google Cloud project** and enable the Google Sheets API.
2. **Create a service account** and download the JSON key.
3. **Share your sheet** with the service account email (editor access).
4. Copy `.env.example` to `.env` and fill in values.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python src/amazon_tracker.py
```

By default, the script scans every row with a URL and updates the sheet. It only sends notifications if it detects a change in price or stock status.

## Environment variables

| Variable | Description |
| --- | --- |
| GOOGLE_SHEET_ID | The Google Sheet ID (from the URL). |
| GOOGLE_SERVICE_ACCOUNT_JSON | Absolute path to the service account JSON file. |
| GOOGLE_WORKSHEET | Worksheet name (default: `Sheet1`). |
| NOTIFY_WEBHOOK_URL | Optional: webhook URL to send change notifications. |
| USER_AGENT | Optional: override the HTTP user agent. |

## Example notification payload

```json
{
  "url": "https://www.amazon.com/dp/B09...",
  "title": "Product Name",
  "price": "$19.99",
  "stock": "In Stock",
  "notes": "Price changed from $22.99"
}
```

## Limitations

- Amazon pages vary by locale and can change without notice.
- Some pages may require additional headers or cookies.
- High-frequency polling may violate Amazon's terms.
