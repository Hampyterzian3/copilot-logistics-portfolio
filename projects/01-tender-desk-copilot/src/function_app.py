"""Azure Function (Python v2 programming model) that exposes rfq_checker over HTTP.

Power Automate calls it through a custom connector (operation CheckRfq):
  POST /api/check-rfq
  body: {"lanes_csv": "<csv text>", "requirements_md": "<markdown text>", "meta": {...}}
  returns: rfq_checker.check() output plus "markdown" (the readable summary used by
  Microsoft 365 Copilot in Word and PowerPoint).

Deploy: func azure functionapp publish <app-name> (requirements.txt: azure-functions).
"""
from __future__ import annotations

import csv
import io
import json

import azure.functions as func

import rfq_checker

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="check-rfq", methods=["POST"])
def check_rfq(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        rows = list(csv.DictReader(io.StringIO(body["lanes_csv"])))
        requirements = body.get("requirements_md", "")
        meta = body.get("meta") or {"id": "rfq"}
    except (ValueError, KeyError) as exc:
        return func.HttpResponse(json.dumps({"error": f"bad request: {exc}"}), status_code=400,
                                 mimetype="application/json")
    result = rfq_checker.check(rows, requirements)
    result["markdown"] = rfq_checker.to_markdown(meta, result)
    return func.HttpResponse(json.dumps(result), mimetype="application/json")
