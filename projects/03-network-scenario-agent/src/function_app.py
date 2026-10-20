"""Azure Functions (Python v2 programming model) wrapper for the network engine.
Not deployed. Exposes POST /api/scenarios, described in ../openapi.yaml.

Local run: func start (Azure Functions Core Tools), with host.json and
requirements.txt in this folder."""
import json
import logging

import azure.functions as func

from network_engine.api import ValidationError, handle_scenario

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="scenarios", methods=["POST"])
def run_scenario(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        body = {}
    try:
        result = handle_scenario(body)
    except ValidationError as exc:
        return func.HttpResponse(json.dumps({"error": str(exc)}), status_code=400, mimetype="application/json")
    logging.info("scenario run: %s", result["recommendation"]["text"])
    return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")
