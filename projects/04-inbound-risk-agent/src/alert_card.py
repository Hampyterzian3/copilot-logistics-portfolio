"""Teams Adaptive Card (1.5) for a flagged shipment. Ported to JS in 04-risk-model.js."""
from __future__ import annotations

from risk_model import BAND_LABELS, ri

SCHEMA = "http://adaptivecards.io/schemas/adaptive-card.json"


def build_alert_card(rec: dict, result: dict) -> dict:
    sid = rec["shipment_id"]
    reasons = "\n".join(f"- {r['text']}" for r in result["reasons"]) or "- No single factor above 3 points"
    last_scan = f"{rec['last_scan_label']} at {rec['last_scan_location']}, {ri(rec['dwell_hours'])} h ago"
    return {
        "$schema": SCHEMA,
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            {
                "type": "Container",
                "style": "attention" if result["band"] == "critical" else "warning",
                "bleed": True,
                "items": [
                    {"type": "TextBlock", "text": f"{BAND_LABELS[result['band']]} inbound risk: {sid}",
                     "weight": "Bolder", "size": "Medium", "wrap": True},
                    {"type": "TextBlock", "text": f"Risk score {result['score']}/100 | {rec['customer']}",
                     "isSubtle": True, "spacing": "None", "wrap": True},
                ],
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Customer", "value": rec["customer"]},
                    {"title": "Order", "value": rec["po_ref"]},
                    {"title": "Carrier", "value": rec["carrier"]},
                    {"title": "Lane", "value": rec["lane"]},
                    {"title": "Destination area", "value": rec["area"]},
                    {"title": "Last scan", "value": last_scan},
                    {"title": "Promised", "value": rec["promised_display"]},
                ],
            },
            {"type": "TextBlock", "text": "Why it is flagged", "weight": "Bolder", "spacing": "Medium"},
            {"type": "TextBlock", "text": reasons, "wrap": True},
        ],
        "actions": [
            {"type": "Action.Submit", "title": "Acknowledge", "style": "positive",
             "data": {"action": "acknowledge", "shipmentId": sid}},
            {"type": "Action.Submit", "title": "Draft customer update",
             "data": {"action": "draft_customer_update", "shipmentId": sid}},
            {"type": "Action.Submit", "title": "Escalate to carrier", "style": "destructive",
             "data": {"action": "escalate_to_carrier", "shipmentId": sid, "carrier": rec["carrier"]}},
        ],
    }
