"""Azure Function (Python v2 model) wrapping risk_model.score_shipment for the scheduled flow.

Deploy with risk_model.py and alert_card.py copied next to this file.
Not covered by the local tests (needs the azure-functions package); the scoring it calls is.
"""
import json

import azure.functions as func

from alert_card import build_alert_card
from risk_model import score_shipment

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="score", methods=["POST"])
def score(req: func.HttpRequest) -> func.HttpResponse:
    body = req.get_json()
    out = []
    for rec in body.get("shipments", []):
        result = score_shipment(rec)
        item = {"shipment_id": rec["shipment_id"], "previous_band": rec.get("band"), **result}
        if result["band"] == "critical":
            item["card"] = json.dumps(build_alert_card(rec, result))
        out.append(item)
    return func.HttpResponse(json.dumps(out), mimetype="application/json")
