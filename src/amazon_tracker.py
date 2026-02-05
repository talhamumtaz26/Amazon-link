#!/usr/bin/env python3
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import gspread
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


DEFAULT_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}


def load_env() -> None:
    load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass
class ProductSnapshot:
    url: str
    title: str
    price: Optional[str]
    stock: Optional[str]


def fetch_product(url: str, user_agent: Optional[str]) -> ProductSnapshot:
    headers = dict(DEFAULT_HEADERS)
    if user_agent:
        headers["User-Agent"] = user_agent

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    title = ""
    title_tag = soup.select_one("#productTitle")
    if title_tag:
        title = title_tag.get_text(strip=True)

    price = extract_price(soup)
    stock = extract_stock(soup)

    return ProductSnapshot(url=url, title=title, price=price, stock=stock)


def extract_price(soup: BeautifulSoup) -> Optional[str]:
    selectors = [
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        "#priceblock_saleprice",
        ".a-price .a-offscreen",
    ]
    for selector in selectors:
        tag = soup.select_one(selector)
        if tag:
            text = tag.get_text(strip=True)
            if text:
                return text
    return None


def extract_stock(soup: BeautifulSoup) -> Optional[str]:
    availability = soup.select_one("#availability")
    if availability:
        text = availability.get_text(strip=True)
        if text:
            return text
    return None


def get_sheet(sheet_id: str, worksheet_name: str, credentials_path: str):
    client = gspread.service_account(filename=credentials_path)
    sheet = client.open_by_key(sheet_id)
    return sheet.worksheet(worksheet_name)


def row_to_dict(header: List[str], row: List[str]) -> Dict[str, str]:
    data = dict(zip(header, row))
    return {key.strip(): value for key, value in data.items() if key}


def ensure_headers(sheet, header: List[str]) -> List[str]:
    if not header or not header[0].strip():
        sheet.update("A1:F1", [["URL", "Title", "Last Price", "Last Stock", "Last Checked", "Notes"]])
        return ["URL", "Title", "Last Price", "Last Stock", "Last Checked", "Notes"]
    return header


def detect_change(previous_price: Optional[str], previous_stock: Optional[str], snapshot: ProductSnapshot) -> Optional[str]:
    changes = []
    if snapshot.price and snapshot.price != previous_price:
        changes.append(f"Price changed from {previous_price or 'N/A'} to {snapshot.price}")
    if snapshot.stock and snapshot.stock != previous_stock:
        changes.append(f"Stock changed from {previous_stock or 'N/A'} to {snapshot.stock}")
    return "; ".join(changes) if changes else None


def notify_change(webhook_url: str, snapshot: ProductSnapshot, note: str) -> None:
    payload = {
        "url": snapshot.url,
        "title": snapshot.title,
        "price": snapshot.price,
        "stock": snapshot.stock,
        "notes": note,
    }
    response = requests.post(webhook_url, json=payload, timeout=15)
    response.raise_for_status()


def update_sheet(sheet, row_index: int, snapshot: ProductSnapshot, note: Optional[str]) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    values = [
        snapshot.title,
        snapshot.price or "",
        snapshot.stock or "",
        timestamp,
        note or "",
    ]
    sheet.update(f"B{row_index}:F{row_index}", [values])


def load_rows(sheet) -> Tuple[List[str], List[List[str]]]:
    data = sheet.get_all_values()
    if not data:
        return [], []
    header = data[0]
    rows = data[1:]
    return header, rows


def main() -> None:
    load_env()
    sheet_id = require_env("GOOGLE_SHEET_ID")
    credentials_path = require_env("GOOGLE_SERVICE_ACCOUNT_JSON")
    worksheet_name = os.getenv("GOOGLE_WORKSHEET", "Sheet1")
    webhook_url = os.getenv("NOTIFY_WEBHOOK_URL")
    user_agent = os.getenv("USER_AGENT")

    sheet = get_sheet(sheet_id, worksheet_name, credentials_path)
    header, rows = load_rows(sheet)
    header = ensure_headers(sheet, header)

    if "URL" not in header:
        raise RuntimeError("Sheet header must include a URL column.")

    url_index = header.index("URL")

    for idx, row in enumerate(rows, start=2):
        row_data = row_to_dict(header, row)
        url = row_data.get("URL")
        if not url:
            continue

        snapshot = fetch_product(url, user_agent)
        note = detect_change(row_data.get("Last Price"), row_data.get("Last Stock"), snapshot)
        update_sheet(sheet, idx, snapshot, note)

        if note and webhook_url:
            notify_change(webhook_url, snapshot, note)


if __name__ == "__main__":
    main()
