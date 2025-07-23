import json
import re
from datetime import datetime
from dateutil.parser import parse as parse_date

# === IATA Code Mapping ===
iata_map = {
    "toronto": "YYZ", "sydney": "SYD", "dubai": "DXB", "bangladesh": "DAC", "dhaka": "DAC",
    "new york": "JFK", "los angeles": "LAX", "london": "LHR", "paris": "CDG", "tokyo": "HND",
    "melbourne": "MEL", "perth": "PER", "brisbane": "BNE", "singapore": "SIN", "delhi": "DEL",
    "mumbai": "BOM", "karachi": "KHI", "islamabad": "ISB", "bali": "DPS", "jakarta": "CGK",
    "kuala lumpur": "KUL", "manila": "MNL", "amman": "AMM", "cairo": "CAI", "riyadh": "RUH",
    "jeddah": "JED", "istanbul": "IST", "doha": "DOH", "chicago": "ORD", "san francisco": "SFO",
    "seattle": "SEA", "houston": "IAH", "vancouver": "YVR", "montreal": "YUL"
}

def normalize_date(date_str):
    try:
        dt = parse_date(date_str)
        return dt.strftime("%d %b %Y")  # API expects "27 Jul 2025"
    except Exception:
        return date_str

def convert_to_iata(extracted: dict) -> dict:
    if not extracted:
        return {}

    origin = extracted.get("origin", "").strip().lower()
    destination = extracted.get("destination", "").strip().lower()
    date = extracted.get("date", "").strip()

    return {
        "origin": iata_map.get(origin, origin.upper()[:3]),
        "destination": iata_map.get(destination, destination.upper()[:3]),
        "date": normalize_date(date)
    }

def validate_extraction(data: dict) -> str:
    missing = []
    if not data.get("origin"):
        missing.append("origin")
    if not data.get("destination"):
        missing.append("destination")
    if not data.get("date"):
        missing.append("date")
    return f"Missing required data: {', '.join(missing)}" if missing else "Valid"

def format_flight_results(flights: list) -> str:
    if not flights:
        return "Sorry, no flights found for your request."

    result_lines = ["Here are some flight options for you:\n"]

    for i, flight in enumerate(flights, 1):
        try:
            segments = flight.get("Segments", [])
            price = flight.get("DisplayFare", {}).get("TotalFare", 0)
            currency = flight.get("DisplayFare", {}).get("Currency", "AUD")
            formatted_price = f"{currency} ${int(price):,}"

            departure_segment = segments[0]
            arrival_segment = segments[-1]

            dep_time = departure_segment.get("DepartureDateTime", "").replace("T", " ")
            arr_time = arrival_segment.get("ArrivalDateTime", "").replace("T", " ")
            airline = departure_segment.get("Airline", {}).get("Name", "Unknown Airline")
            flight_number = departure_segment.get("Airline", {}).get("FlightNumber", "")

            via = ""
            if len(segments) > 1:
                stops = segments[1:-1]
                via_points = [s.get("Origin", "") for s in stops]
                if via_points:
                    via = " via " + ", ".join(via_points)

            line = (
                f"{i}. {airline} {flight_number}\n"
                f"   {dep_time} → {arr_time}{via}\n"
                f"   Price: {formatted_price}\n"
            )
            result_lines.append(line)

        except Exception as e:
            result_lines.append(f"{i}. [Error parsing flight data]")

    return "\n".join(result_lines)
