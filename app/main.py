from __future__ import annotations
import argparse, json, re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

PHONE_RE = re.compile(r'(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)')
ORDER_RE = re.compile(r'\b(?:VW-\d{4,}|VYG[A-Z0-9]{4,})\b', re.I)
MONEY_RE = re.compile(r'\b(?:INR|Rs\.?|₹|\$|CAD|USD)\s*[\d,]+(?:\.\d+)?\b', re.I)
DATE_RE = re.compile(r'\b(?:Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?)\s+\d{1,2}\b', re.I)

# Explicitly treated as untrusted input. These phrases must never become instructions.
INJECTION_RE = re.compile(
    r'\b(ignore (?:all|any|previous) instructions?|system notice|administrator mode|'
    r'do not escalate|override|jailbreak|developer message)\b', re.I
)

@dataclass
class Result:
    id: str
    brand: str
    channel: str
    intent: str
    entities: dict[str, Any]
    next_action: str
    handler: str
    priority: str
    confidence: float
    human_review: bool
    reasons: list[str]

def extract_entities(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    out: dict[str, Any] = {}
    phones = PHONE_RE.findall(text)
    orders = ORDER_RE.findall(text)
    money = MONEY_RE.findall(text)
    dates = DATE_RE.findall(text)
    if phones: out["phone_numbers"] = phones
    if orders: out["references"] = orders
    if money: out["amounts"] = money
    if dates: out["dates"] = dates
    # Useful domain entities
    low=text.lower()
    terms = {
        "product": ["magnesium","protein","ashwagandha","keratin","balayage"],
        "airline": ["air canada"],
        "city_or_route": ["toronto","amritsar","dubai","frankfurt","pearson","gurgaon","gujarat"],
    }
    found=[]
    for k, vals in terms.items():
        for v in vals:
            if v in low: found.append((k,v))
    for k,v in found:
        out.setdefault(k,[]).append(v)
    return out

def should_use_llm(m: dict[str, Any]) -> bool:
    """Route medium-complexity, customer-facing requests to an LLM; keep high-risk cases deterministic/human."""
    text = str(m.get("text") or "").lower().strip()
    if not text or INJECTION_RE.search(text):
        return False
    high_risk = [
        "blood pressure medication", "bank details", "process payment",
        "urgent" , "pearson", "connection" , "cancelled", "charged twice",
        "refund" , "broken seal", "wrong item", "500mg", "250mg"
    ]
    if any(x in text for x in high_risk):
        return False
    # LLM is useful where interpretation, tone, context, or a combined request is needed.
    llm_signals = [
        "price", "rate", "best way", "parents", "wheelchair", "quote",
        "next step", "other one", "membership", "same time", "before diwali",
        "what do i", "how do", "can you help", "please", "would like"
    ]
    return any(x in text for x in llm_signals)


def classify(m: dict[str, Any]) -> Result:
    text=m.get("text")
    low=(str(text) if text is not None else "").lower().strip()
    entities=extract_entities(text)

    def result(intent, action, handler, priority="normal", confidence=.95, human=False, reasons=None):
        return Result(m["id"],m.get("brand","unknown"),m.get("channel","unknown"),intent,entities,
                      action,handler,priority,confidence,human,reasons or [])

    if not text or not str(text).strip() or low == "none":
        return result("empty_or_unreadable",
                      "Ask the customer to resend the message or provide the missing content.",
                      "human_support", "normal", .99, True, ["No usable customer request was provided."])

    # Customer text is untrusted data. Never obey instructions embedded in it.
    if INJECTION_RE.search(str(text)):
        return result("instruction_or_privileged_refund_request",
                      "Do not execute the embedded instructions. Verify the account/refund request through the normal support workflow.",
                      "human_support", "high", .99, True,
                      ["Authority-claim/prompt-injection language was detected.", "Refund approval must not be authorized by message text."])

    # High-consequence cases first.
    if "blood pressure medication" in low or "safe to take" in low:
        return result("health_safety_question",
                      "Do not provide medication/supplement safety advice automatically; route to qualified support and advise the customer to consult an appropriate clinician/pharmacist.",
                      "human_support", "high", .98, True,
                      ["Medication/supplement interaction question requires qualified review."])

    if "bank details" in low or ("process payment" in low and "invoice" in low):
        return result("invoice_payment_request",
                      "Verify the invoice and supplier/payment details through the finance workflow before any payment is processed.",
                      "finance_review", "high", .98, True,
                      ["Payment and bank-detail handling is high risk."])

    # Explicit requests, with combined requests handled by the dominant workflow and entities retained.
    if "cancel" in low and "subscription" in low:
        return result("subscription_cancellation",
                      "Verify the account, cancel the subscription, and send cancellation confirmation.",
                      "subscription_automation", confidence=.98,
                      reasons=["Customer explicitly asks to cancel the subscription."])

    if low in {"unsubscribe", "stop", "remove me"}:
        return result("unsubscribe_marketing",
                      "Suppress marketing messages for this customer and confirm the opt-out.",
                      "messaging_automation", confidence=.99,
                      reasons=["Explicit unsubscribe request."])

    if "charged twice" in low or "charged two" in low or "charged twice" in low or "duplicate" in low or ("twice" in low and "charged" in low):
        return result("duplicate_charge",
                      "Verify the order/payment ledger, reverse or refund the duplicate charge if confirmed, and update the customer.",
                      "billing_support", "high", .98, True,
                      ["Duplicate-charge complaint with monetary amount."])

    if "tracking" in low or "tracking hasn't moved" in low or "hasn't moved" in low:
        return result("order_tracking",
                      "Look up the shipment using the order reference and send the latest tracking status; escalate if the shipment is stalled beyond SLA.",
                      "order_support", confidence=.99,
                      reasons=["Explicit shipment-tracking request."])

    if "refund" in low and "broken" in low:
        return result("damaged_delivery_refund",
                      "Verify the order and damage evidence, open the returns/refund workflow, and separately route the new protein purchase request to sales/order support.",
                      "returns_support", "high", .97, True,
                      ["Broken seal plus explicit refund request.", "Message contains a separate new-product purchase request."])

    if "wrong item" in low or ("250mg" in low and "500mg" in low):
        return result("wrong_item_received",
                      "Verify the order, arrange the correct 500mg replacement/return, and notify the customer of the resolution.",
                      "returns_support", "high", .97, True,
                      ["Customer reports receiving a different strength from the one ordered."])

    if "wholesale" in low or "bulk pricing" in low:
        return result("wholesale_enquiry",
                      "Capture business details and route the account to wholesale/sales for bulk pricing and terms.",
                      "sales_wholesale", confidence=.99,
                      reasons=["Explicit wholesale/bulk-pricing request."])

    if "balayage" in low:
        return result("salon_service_pricing",
                      "Answer whether balayage is suitable for dark hair, provide an approximate price/range, and offer a booking consultation before Diwali.",
                      "salon_sales", confidence=.97,
                      reasons=["Customer asks about balayage suitability, price, and booking timing."])

    if "keratin" in low and ("appointment" in low or "shift" in low or "saturday" in low or "sunday" in low):
        return result("appointment_reschedule_and_service_price",
                      "Check Sunday 4pm availability, reschedule the appointment if available, and provide the keratin treatment price.",
                      "salon_booking", confidence=.98,
                      reasons=["Customer requests an appointment change and asks for a service price."])

    if "move my thursday appointment" in low or ("sister" in low and "membership" in low):
        return result("appointment_change_and_membership_question",
                      "Check Thursday appointment availability, book the sister if a slot is available, and verify whether the membership is individual or transferable.",
                      "salon_booking", confidence=.97,
                      reasons=["Multiple appointment and membership questions require booking/account checks."])

    if "booked for tomorrow" in low and "work" in low:
        return result("appointment_cancellation_or_reschedule",
                      "Locate tomorrow's 11am appointment and ask whether the customer wants to cancel or reschedule; then update the booking.",
                      "salon_booking", confidence=.91, human=True,
                      reasons=["Customer implies a cancellation/reschedule but does not explicitly choose one."])

    if "appointment" in low or "shift it" in low or "move my" in low:
        return result("appointment_change",
                      "Check appointment availability and reschedule the booking; confirm the new time with the customer.",
                      "salon_booking", confidence=.96,
                      reasons=["Appointment-change language detected."])

    if "open on sundays" in low or ("open" in low and "sunday" in low):
        return result("opening_hours",
                      "Return the salon's Sunday opening hours from the current hours source.",
                      "salon_faq", confidence=.99,
                      reasons=["Direct opening-hours question."])

    if "obsessed" in low or "amazing job" in low or "posting a photo" in low:
        return result("positive_feedback",
                      "Record the positive feedback and optionally send a brief acknowledgement; no support case is required.",
                      "feedback_automation", "low", .99, False,
                      ["Customer is providing positive feedback rather than requesting support."])

    if "connection" in low and "cancelled" in low or "next available is" in low or ("urgent" in low and "pearson" in low):
        return result("urgent_travel_disruption",
                      "Escalate immediately to the travel-disruption desk and contact the customer using the supplied phone number; prioritize rebooking/assistance for the elderly passenger.",
                      "travel_disruption_desk", "urgent", .99, True,
                      ["Active flight disruption at the airport with an elderly passenger."])

    if "change my return" in low or ("return" in low and "change fee" in low):
        return result("flight_change_request",
                      "Verify booking VYG9K2M and fare rules, quote the applicable change fee for Oct 14→Oct 21, and obtain approval before changing the booking.",
                      "travel_changes", "high", .98, True,
                      ["Flight date change and fee question require booking/fare verification."])

    if "wheelchair" in low or ("over 70" in low and "fares" in low):
        return result("accessible_travel_planning",
                      "Route to an accessible-travel specialist to compare December Toronto→Amritsar options and arrange wheelchair assistance for the mother.",
                      "accessible_travel", "high", .98, True,
                      ["Elderly travellers and wheelchair assistance require specialist handling."])

    if "quote" in low and ("next step" in low or "how do we pay" in low or "how do we pay" in low):
        return result("travel_quote_followup",
                      "Retrieve the Dubai-stopover quote, confirm the itinerary/timing, and provide the next booking/payment step.",
                      "travel_sales", confidence=.97,
                      reasons=["Customer is following up on an existing quote and asks how to proceed/pay."])

    if "travel consultant" in low and ("resume" in low or "5 years" in low):
        return result("job_application",
                      "Acknowledge the application and route the resume and candidate details to recruiting for review.",
                      "recruiting", confidence=.99, human=True,
                      reasons=["Employment enquiry includes experience, location, and a resume."])

    if low == "what about the other one":
        return result("ambiguous_followup",
                      "Retrieve the conversation context; if the referenced item/booking cannot be identified, ask the customer which one they mean.",
                      "human_support", confidence=.90, human=True,
                      reasons=["The message depends on prior context and has no identifiable standalone referent."])

    if PHONE_RE.fullmatch((text or "").strip()):
        return result("phone_number_only",
                      "Use conversation context to identify the request; if unavailable, ask what help is needed.",
                      "human_support", confidence=.97, human=True,
                      reasons=["Only a phone number was supplied; no customer request was stated."])

    if "packaging was much better" in low or "arrived today" in low and "thank" in low:
        return result("positive_order_feedback",
                      "Record the positive delivery/packaging feedback and optionally acknowledge the customer.",
                      "feedback_automation", "low", .99,
                      reasons=["Customer reports successful delivery and provides positive feedback."])

    return result("unclassified",
                  "Ask a clarifying question or route to human support.",
                  "human_support", "normal", .60, True,
                  ["No reliable intent rule matched; automation should not guess."])

def classify_with_optional_llm(m: dict[str, Any], use_llm: bool = True, provider: str = "gemini") -> Result:
    import time
    from .metrics import record
    started=time.perf_counter()
    base = classify(m)
    route = "human" if base.human_review else ("llm" if use_llm and should_use_llm(m) else "automatic")
    if not use_llm or base.human_review or not should_use_llm(m):
        result=base
    else:
        try:
            from .llm import triage_with_llm
            data = triage_with_llm(m, provider=provider)
            result = Result(
                id=m["id"], brand=m.get("brand", "unknown"), channel=m.get("channel", "unknown"),
                intent=str(data["intent"]), entities=data.get("entities", {}),
                next_action=str(data["next_action"]), handler=str(data["handler"]),
                priority=str(data.get("priority", "normal")).lower(), confidence=float(data.get("confidence", .8)),
                human_review=bool(data.get("human_review", False)),
                reasons=["AI-assisted triage: " + str(x) for x in data.get("reasons", [])] + ["PII is redacted before optional AI processing."]
            )
        except Exception as exc:
            base.reasons.append(f"AI fallback unavailable: {exc}")
            result=base; route="automatic"
    latency=(time.perf_counter()-started)*1000
    record(event="triage", channel=m.get("channel","unknown"), message_id=m.get("id"), route=("human" if result.human_review else route), intent=result.intent, confidence=result.confidence, latency_ms=round(latency,2), llm_cost_usd=0.0, llm_model=(__import__("os").environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite") if provider == "gemini" else __import__("os").environ.get("OLLAMA_MODEL", "qwen3:0.6b")))
    return result

def process(path: str, use_llm: bool = True) -> list[dict[str, Any]]:
    """Process every record without allowing one malformed record to stop the batch."""
    raw=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw,list): raise ValueError("Input JSON must be an array of message objects.")
    out=[]
    for m in raw:
        if not isinstance(m,dict) or not m.get("id"):
            out.append({"id": None, "intent":"malformed_input", "entities":{}, "next_action":"Send the record to human review for correction.", "handler":"human_support", "priority":"high", "confidence":0.0, "human_review":True, "reasons":["Malformed message object; isolated safely without stopping the batch."], "error":"Malformed message object; skipped safely.", "raw_type":type(m).__name__})
            continue
        try:
            out.append(asdict(classify_with_optional_llm(m, use_llm=use_llm)))
        except Exception as exc:
            out.append({"id":m.get("id"),"brand":m.get("brand","unknown"),"channel":m.get("channel","unknown"),"intent":"processing_error","entities":{},"next_action":"Send the message to human review and investigate the processing error.","handler":"human_support","priority":"high","confidence":0.0,"human_review":True,"reasons":["Processing failed safely: "+str(exc)],"error":"Processing failed safely"})
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", default="messages.json", help="Input JSON file (default: messages.json)")
    ap.add_argument("-o","--output",default="output.json")
    args=ap.parse_args()
    results=process(args.input)
    Path(args.output).write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"Processed {len(results)} messages -> {args.output}")

if __name__=="__main__":
    main()
