/* Inbound risk score: JS port of projects/04-inbound-risk-agent/src/risk_model.py and alert_card.py.
   Parity with Python is checked by projects/04-inbound-risk-agent/src/verify_js_parity.js. */
(function (root) {
  "use strict";
  var WEIGHTS = [["lane", 15], ["area", 15], ["carrier", 15], ["dwell", 20], ["customs", 10], ["slack", 20], ["calendar", 5]];
  var BANDS = [["critical", 55], ["at_risk", 40], ["watch", 25]];
  var BAND_LABELS = { critical: "Critical", at_risk: "At risk", watch: "Watch", on_track: "On track" };
  var MIN_REASON_POINTS = 3.0;
  var MAX_REASONS = 3;

  function clamp01(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }
  function ri(x) { return Math.floor(x + 0.5); }
  function r1(x) { return Math.floor(x * 10 + 0.5) / 10; }
  function f1(x) { return r1(x).toFixed(1); }
  function pct0(x) { return String(ri(x * 100)) + "%"; }

  function subscores(f) {
    var ratio = f.dwell_hours / f.dwell_norm_hours;
    var slack = f.days_to_promise - f.remaining_transit_days;
    var cal = f.holiday_name ? 1.0 : (f.non_working_days > 0 ? 0.6 : 0.0);
    return {
      lane: clamp01((f.lane_delay_rate - 0.06) / 0.24),
      area: clamp01((f.area_loss_rate - 0.004) / 0.016),
      carrier: clamp01((0.95 - f.carrier_on_time) / 0.20),
      dwell: clamp01((ratio - 1.0) / 2.0),
      customs: f.customs_status === "held" ? 1.0 : f.customs_status === "pending" ? 0.5 : 0.0,
      slack: clamp01((1.0 - slack) / 2.0),
      calendar: cal
    };
  }

  function reasonText(factor, f) {
    switch (factor) {
      case "lane":
        return "Lane " + f.lane + " ran late on " + pct0(f.lane_delay_rate) + " of shipments in the last 12 months";
      case "area":
        return "Destination area " + f.area + " lost " + f1(f.area_loss_rate * 100) + "% of shipments, against " +
          f1(f.network_loss_rate * 100) + "% across the network";
      case "carrier":
        return f.carrier + " delivered on time on " + pct0(f.carrier_on_time) + " of shipments in the last 12 months";
      case "dwell":
        return "No scan for " + ri(f.dwell_hours) + " h since the " + f.last_scan_label + " scan at " + f.last_scan_location +
          ", " + f1(f.dwell_hours / f.dwell_norm_hours) + "x the usual " + ri(f.dwell_norm_hours) + " h";
      case "customs":
        return f.customs_status === "held" ? "Held by customs, not yet released" : "Customs clearance still pending";
      case "slack":
        if (f.days_to_promise < 0) {
          return "Already " + f1(-f.days_to_promise) + " days past the promised date, about " +
            f1(f.remaining_transit_days) + " days of transit left";
        }
        return "Due in " + f1(f.days_to_promise) + " days with about " + f1(f.remaining_transit_days) + " days of transit left";
      default:
        var n = f.non_working_days, unit = n === 1 ? "day" : "days";
        if (f.holiday_name) return n + " non-working " + unit + " before the promised date, including " + f.holiday_name;
        return n + " weekend " + unit + " before the promised date";
    }
  }

  function bandFor(score) {
    for (var i = 0; i < BANDS.length; i++) if (score >= BANDS[i][1]) return BANDS[i][0];
    return "on_track";
  }

  function scoreShipment(f) {
    var sub = subscores(f), total = 0, pts = [];
    WEIGHTS.forEach(function (w, order) {
      var p = w[1] * sub[w[0]];
      total += p;
      pts.push([p, order, w[0]]);
    });
    var score = Math.min(100, ri(total));
    var ranked = pts.slice().sort(function (a, b) { return b[0] - a[0] || a[1] - b[1]; });
    var reasons = ranked.filter(function (t) { return t[0] >= MIN_REASON_POINTS; }).slice(0, MAX_REASONS)
      .map(function (t) { return { factor: t[2], points: r1(t[0]), text: reasonText(t[2], f) }; });
    var points = {};
    pts.forEach(function (t) { points[t[2]] = r1(t[0]); });
    return { score: score, band: bandFor(score), points: points, reasons: reasons };
  }

  function buildAlertCard(rec, result) {
    var sid = rec.shipment_id;
    var reasons = result.reasons.map(function (r) { return "- " + r.text; }).join("\n") || "- No single factor above 3 points";
    var lastScan = rec.last_scan_label + " at " + rec.last_scan_location + ", " + ri(rec.dwell_hours) + " h ago";
    return {
      "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
      type: "AdaptiveCard",
      version: "1.5",
      body: [
        {
          type: "Container", style: result.band === "critical" ? "attention" : "warning", bleed: true,
          items: [
            { type: "TextBlock", text: BAND_LABELS[result.band] + " inbound risk: " + sid, weight: "Bolder", size: "Medium", wrap: true },
            { type: "TextBlock", text: "Risk score " + result.score + "/100 | " + rec.customer, isSubtle: true, spacing: "None", wrap: true }
          ]
        },
        {
          type: "FactSet",
          facts: [
            { title: "Customer", value: rec.customer },
            { title: "Order", value: rec.po_ref },
            { title: "Carrier", value: rec.carrier },
            { title: "Lane", value: rec.lane },
            { title: "Destination area", value: rec.area },
            { title: "Last scan", value: lastScan },
            { title: "Promised", value: rec.promised_display }
          ]
        },
        { type: "TextBlock", text: "Why it is flagged", weight: "Bolder", spacing: "Medium" },
        { type: "TextBlock", text: reasons, wrap: true }
      ],
      actions: [
        { type: "Action.Submit", title: "Acknowledge", style: "positive", data: { action: "acknowledge", shipmentId: sid } },
        { type: "Action.Submit", title: "Draft customer update", data: { action: "draft_customer_update", shipmentId: sid } },
        { type: "Action.Submit", title: "Escalate to carrier", style: "destructive", data: { action: "escalate_to_carrier", shipmentId: sid, carrier: rec.carrier } }
      ]
    };
  }

  var api = { WEIGHTS: WEIGHTS, BANDS: BANDS, BAND_LABELS: BAND_LABELS, subscores: subscores, reasonText: reasonText,
    bandFor: bandFor, scoreShipment: scoreShipment, buildAlertCard: buildAlertCard, ri: ri, r1: r1, f1: f1, pct0: pct0 };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.RiskModel = api;
})(typeof window !== "undefined" ? window : this);
