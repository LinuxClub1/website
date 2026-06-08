import os, random, json, ipaddress, csv, requests
from datetime import datetime, timezone
from time import time

from dotenv import load_dotenv
from flask import Flask, Response, request
from flask_cors import CORS

load_dotenv("/root/secrets/env")
MESSAGES_WEBHOOK = os.getenv("MESSAGES_WEBHOOK")
SUBMISSION_WEBHOOK = os.getenv("SUBMISSION_WEBHOOK")
IPREGISTRY_TOKEN = os.getenv("IPREGISTRY_TOKEN")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
QUOTES_PATH = "/home/ubuntu/Peapbot/quotes.csv"
SUBMISSIONS_CSV_PATH = os.getenv("SUBMISSIONS_CSV_PATH") or "/home/ubuntu/registration-bot/submissions.csv"
rate_limit = {}

app = Flask(__name__)
CORS(app)


def text(value, limit=None, code=False):
    out = "N/A" if value is None or value == "" else str(value)
    if limit is not None and len(out) > limit:
        out = out[: limit - 3] + "..."
    if code:
        return "`" + out.replace("`", "'") + "`"
    return out


def ip_link(value):
    ip_value = text(value)
    if ip_value == "N/A":
        return ip_value
    try:
        ipaddress.ip_address(ip_value)
    except ValueError:
        return ip_value
    return "[" + ip_value + "](https://ipinfo.io/" + ip_value + ")"


@app.route("/api/quote", methods=["GET"])
def quote():
    try:
        with open(QUOTES_PATH, encoding="utf-8") as quote_file:
            lines = quote_file.readlines()
    except FileNotFoundError:
        return "Quotes file not found", 404
    except OSError:
        return "Unable to read quotes file", 500

    all_quotes = []
    for line in lines:
        line = line.strip()
        if line == "":
            continue
        if line.endswith(":::;"):
            line = line[:-4]
        if ";;;:" not in line:
            continue

        text_part, metadata = line.split(";;;:", 1)
        metadata_parts = metadata.rsplit(";", 2)
        if len(metadata_parts) != 3:
            continue

        text_items = [item.strip() for item in text_part.split(",") if item.strip() != ""]
        author_items = [item.strip() for item in metadata_parts[0].split(",") if item.strip() != ""]
        if len(text_items) == 0:
            continue

        out_lines = []
        for i, text_item in enumerate(text_items):
            if i < len(author_items):
                author = author_items[i]
            elif len(author_items) > 0:
                author = author_items[-1]
            else:
                author = "Unknown"
            out_lines.append('"' + text_item + '" - ' + author)
        all_quotes.append("\n".join(out_lines))
    if len(all_quotes) == 0:
        return "No quotes! Something definitely went wrong", 404
    return random.choice(all_quotes), 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/api/submission", methods=["POST"])
@app.route("/api/submission/<path:unique_id>", methods=["POST"])
def handle(unique_id=None):
    ip = request.headers.get("CF-Connecting-IP") or request.remote_addr or "unknown"
    now = time()

    expired_ips = [k for k, v in rate_limit.items() if now - v >= 5]
    for expired_ip in expired_ips:
        rate_limit.pop(expired_ip, None)

    if ip in rate_limit and now - rate_limit[ip] < 5:
        return "Too many requests", 429
    rate_limit[ip] = now

    data = request.get_json() or {}
    name = data.get("name")
    email = data.get("email")
    reason = data.get("reason")
    grade = data.get("grade")
    availability = data.get("availability")
    found = data.get("found")
    else_text = data.get("else")
    if unique_id is None or unique_id == "":
        unique_id = data.get("unique_id")
    if unique_id is None or unique_id == "":
        unique_id = "N/A"

    if name is None or name == "" or email is None or email == "":
        return "Unable to send message", 400
    if not email.lower().endswith("@bvsd.org"):
        return "Invalid email", 418

    cf_values = {}
    for header_name in [
        "CF-IPCity",
        "CF-Region",
        "CF-IPCountry",
        "CF-Region-Code",
        "CF-Postal-Code",
        "CF-Timezone",
        "CF-IPlatitude",
        "CF-IPLongitude",
        "CF-IPContinent",
        "CF-Metro-Code",
        "CDN-Loop",
        "X-Forwarded-Proto",
        "CF-Visitor",
    ]:
        header_raw = request.headers.get(header_name)
        if header_raw is None:
            header_raw = ""
        try:
            cf_values[header_name] = header_raw.encode("latin1").decode("utf-8")
        except UnicodeError:
            cf_values[header_name] = header_raw

    city = cf_values.get("CF-IPCity", "")
    region = cf_values.get("CF-Region", "")
    country = cf_values.get("CF-IPCountry", "")
    location_parts = []
    for part in [city, region, country]:
        part_text = text(part).strip()
        if part_text != "" and part_text != "N/A":
            location_parts.append(part_text)
    location_value = ", ".join(location_parts) if len(location_parts) > 0 else "N/A"
    request_user_agent = text(request.headers.get("User-Agent"))

    cf_connecting_ip = request.headers.get("CF-Connecting-IP")
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    x_real_ip = request.headers.get("X-Real-IP")
    edge_remote_ip = request.remote_addr

    sender_ip = None
    for candidate in [cf_connecting_ip, x_forwarded_for, x_real_ip, edge_remote_ip]:
        if candidate is None:
            continue
        for part in str(candidate).split(","):
            cleaned = part.strip()
            if cleaned != "":
                sender_ip = cleaned
                break
        if sender_ip is not None:
            break
    sender_ip = text(sender_ip)

    cf_ray = request.headers.get("CF-Ray")
    cf_server = cf_ray.rsplit("-", 1)[1] if isinstance(cf_ray, str) and "-" in cf_ray else cf_ray
    sender_data = {
        "sender_ip": sender_ip,
        "edge_remote_ip": text(edge_remote_ip),
        "x_real_ip": text(x_real_ip),
        "x_forwarded_for": text(x_forwarded_for),
        "cf_connecting_ip": text(cf_connecting_ip),
        "cf_ray": text(cf_ray),
        "cf_server": text(cf_server),
        "location": location_value,
        "user_agent": text(request.headers.get("User-Agent")),
    }

    ipregistry_data = {}
    if IPREGISTRY_TOKEN is not None and IPREGISTRY_TOKEN != "" and sender_ip != "N/A":
        try:
            ipregistry_resp = requests.get(
                "https://api.ipregistry.co/" + sender_ip,
                params={"key": IPREGISTRY_TOKEN},
                timeout=6,
            )
        except requests.RequestException:
            ipregistry_resp = None
        if ipregistry_resp is not None and ipregistry_resp.status_code == 200:
            try:
                parsed_ipregistry = ipregistry_resp.json()
                if isinstance(parsed_ipregistry, dict):
                    ipregistry_data = parsed_ipregistry
            except ValueError:
                pass

    company_data = ipregistry_data.get("company", {}) if isinstance(ipregistry_data.get("company"), dict) else {}
    connection_data = ipregistry_data.get("connection", {}) if isinstance(ipregistry_data.get("connection"), dict) else {}

    company_name = text(company_data.get("name"))
    company_domain = text(company_data.get("domain"))
    if company_domain != "N/A" and not company_domain.startswith("http://") and not company_domain.startswith("https://"):
        company_domain = "https://" + company_domain
    if company_name != "N/A" and company_domain != "N/A":
        company_block = "[" + company_name + "](" + company_domain + ")"
    elif company_name != "N/A":
        company_block = company_name
    elif company_domain != "N/A":
        company_block = company_domain
    else:
        company_block = "N/A"

    connection_name = text(connection_data.get("organization"))
    connection_domain = text(connection_data.get("domain"))
    if connection_domain != "N/A" and not connection_domain.startswith("http://") and not connection_domain.startswith("https://"):
        connection_domain = "https://" + connection_domain
    if connection_name != "N/A" and connection_domain != "N/A":
        connection_block = "[" + connection_name + "](" + connection_domain + ")"
    elif connection_name != "N/A":
        connection_block = connection_name
    elif connection_domain != "N/A":
        connection_block = connection_domain
    else:
        connection_block = "N/A"

    if company_block != "N/A" and connection_block != "N/A" and company_block != connection_block:
        isp = company_block + " through " + connection_block
    elif company_block != "N/A":
        isp = company_block
    elif connection_block != "N/A":
        isp = connection_block
    else:
        isp = "N/A"

    sender_location = sender_data.get("location", "N/A")
    sender_user_agent = sender_data.get("user_agent", "N/A")
    cloudflare_server = sender_data.get("cf_server", "N/A")
    city_lower = str(city).strip().lower()
    region_lower = str(region).strip().lower()
    region_code_lower = str(cf_values.get("CF-Region-Code", "")).strip().lower()
    metro_code = str(cf_values.get("CF-Metro-Code", "")).strip()
    denver_area_cities = {
        "denver",
        "aurora",
        "lakewood",
        "englewood",
        "littleton",
        "centennial",
        "thornton",
        "arvada",
        "westminster",
        "broomfield",
        "highlands ranch",
        "commerce city",
        "greenwood village",
        "parker",
        "castle rock",
        "northglenn",
        "brighton",
        "golden",
    }
    is_colorado = region_lower == "colorado" or region_code_lower == "co"
    is_boulder = is_colorado and city_lower == "boulder"
    is_denver_area = is_colorado and (city_lower in denver_area_cities or metro_code == "751")
    is_front_range_priority = is_boulder or is_denver_area
    submission_value = text(
        "\n".join(
            [
                "Sender Name: " + text(name, 120),
                "Email: " + text(email, 180),
                "Reason: " + text(reason, 350),
                "Grade: " + text(grade, 80),
                "Availability: " + text(availability, 180),
                "Found: " + text(found, 180),
                "Else: " + text(else_text, 220),
            ]
        ),
        1000,
    )
    sender_info_value = text(
        "\n".join(
            [
                "Location: " + text(sender_location, 180),
                "User Agent: " + text(sender_user_agent, 350),
                "Unique ID: " + text(unique_id, 220),
                "Sender IP: " + text(ip_link(sender_ip), 180),
                "ISP: " + text(isp, 450),
                "Cloudflare Server: " + text(cloudflare_server, 120),
            ]
        ),
        1000,
    )

    simple_fields = [
        {"name": "Submission", "value": submission_value, "inline": False},
        {"name": "Sender Info", "value": sender_info_value, "inline": False},
    ]

    detailed_fields = [
        {"name": "Sender", "value": text(name, 350, code=True), "inline": False},
        {"name": "Email", "value": text(email, 350, code=True), "inline": False},
        {"name": "Reason", "value": text(reason, 950, code=True), "inline": False},
        {"name": "Grade", "value": text(grade, 160, code=True), "inline": False},
        {"name": "Availability", "value": text(availability, 250, code=True), "inline": False},
        {"name": "Found", "value": text(found, 250, code=True), "inline": False},
        {"name": "Else", "value": text(else_text, 250, code=True), "inline": False},
        {"name": "Location", "value": text(location_value, 250, code=True), "inline": False},
        {"name": "User-Agent", "value": text(request_user_agent, 450, code=True), "inline": False},
        {"name": "Unique ID", "value": text(unique_id, 250, code=True), "inline": False},
    ]

    headers_for_display = dict(request.headers)
    for ip_header in ["CF-Connecting-IP", "X-Forwarded-For", "X-Real-IP", "Cf-Connecting-Ip", "Cf-Connecting-IP"]:
        headers_for_display.pop(ip_header, None)

    uri = request.full_path
    if isinstance(uri, str) and uri.endswith("?"):
        uri = uri[:-1]

    try:
        timestamp_utc = datetime.fromtimestamp(float(time()), tz=timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        timestamp_utc = str(time())

    detailed_fields.append(
        {
            "name": "Proxy Request",
            "value": text(
                request.method
                + " "
                + text(request.environ.get("SERVER_PROTOCOL"))
                + "\nHost: "
                + text(request.host)
                + "\nURI: "
                + text(uri)
                + "\nTimestamp (UTC): "
                + timestamp_utc,
                1000,
            ),
            "inline": False,
        }
    )
    detailed_fields.append(
        {
            "name": "Proxy Network",
            "value": text(
                "edge_remote_ip: "
                + ip_link(sender_data.get("edge_remote_ip"))
                + "\nsender_ip: "
                + ip_link(sender_data.get("sender_ip"))
                + "\ncf_connecting_ip: "
                + (
                    ", ".join(
                        [
                            ip_link(str(item).strip())
                            for item in str(sender_data.get("cf_connecting_ip")).split(",")
                            if str(item).strip() != ""
                        ]
                    )
                    or "N/A"
                )
                + "\nx_forwarded_for: "
                + (
                    ", ".join(
                        [
                            ip_link(str(item).strip())
                            for item in str(sender_data.get("x_forwarded_for")).split(",")
                            if str(item).strip() != ""
                        ]
                    )
                    or "N/A"
                )
                + "\nx_real_ip: "
                + (
                    ", ".join(
                        [
                            ip_link(str(item).strip())
                            for item in str(sender_data.get("x_real_ip")).split(",")
                            if str(item).strip() != ""
                        ]
                    )
                    or "N/A"
                ),
                1000,
            ),
            "inline": False,
        }
    )
    detailed_fields.append(
        {
            "name": "Cloudflare Geo",
            "value": text(
                "cf_ray: "
                + text(sender_data.get("cf_ray"))
                + "\ncf_server: "
                + text(sender_data.get("cf_server"))
                + "\ncountry: "
                + cf_values.get("CF-IPCountry", "")
                + "\nregion: "
                + cf_values.get("CF-Region", "")
                + " ("
                + cf_values.get("CF-Region-Code", "")
                + ")"
                + "\ncity: "
                + cf_values.get("CF-IPCity", "")
                + "\npostal: "
                + cf_values.get("CF-Postal-Code", "")
                + "\ntimezone: "
                + cf_values.get("CF-Timezone", "")
                + "\nlat/lon: "
                + cf_values.get("CF-IPlatitude", "")
                + ", "
                + cf_values.get("CF-IPLongitude", "")
                + "\ncontinent: "
                + cf_values.get("CF-IPContinent", "")
                + "\ncf_metro: "
                + cf_values.get("CF-Metro-Code", "")
                + "\ncdn_loop: "
                + cf_values.get("CDN-Loop", "")
                + "\nforwarded_proto: "
                + cf_values.get("X-Forwarded-Proto", "")
                + "\ncf_visitor: "
                + cf_values.get("CF-Visitor", ""),
                1000,
            ),
            "inline": False,
        }
    )
    if len(headers_for_display) == 0:
        header_lines = "N/A"
    else:
        header_items = []
        for header_key in sorted(headers_for_display.keys()):
            header_value = headers_for_display.get(header_key)
            if isinstance(header_value, list):
                value_text = ", ".join([str(v) for v in header_value]) if len(header_value) > 0 else "N/A"
            elif isinstance(header_value, dict):
                value_text = json.dumps(header_value, ensure_ascii=True)
            else:
                value_text = text(header_value)
            header_items.append(str(header_key) + ": " + value_text)
        header_lines = "\n".join(header_items)
    detailed_fields.append(
        {
            "name": "Request Headers",
            "value": "```" + text(str(header_lines).replace("```", "'''"), 980) + "```",
            "inline": False,
        }
    )

    flag_country_code = "us"
    if isinstance(country, str) and len(country) == 2 and country.isalpha():
        flag_country_code = country.lower()
    embed_color = 0xACBF87
    if is_boulder:
        simple_title = "PROMINENT IP BOULDER"
        detailed_title = " Detailed PROMINENT IP BOULDER"
    elif is_denver_area:
        simple_title = "PROMINENT IP DENVER AREA"
        detailed_title = "Detailed PROMINENT IP DENVER AREA"
    else:
        simple_title = "Message Received"
        detailed_title = "Detailed Message"

    simple_embed = {
        "title": simple_title,
        "color": embed_color,
        "thumbnail": {"url": "https://flagcdn.com/160x120/" + flag_country_code + ".png"},
        "fields": simple_fields,
    }
    detailed_embed = {
        "title": detailed_title,
        "color": embed_color,
        "thumbnail": {"url": "https://flagcdn.com/160x120/" + flag_country_code + ".png"},
        "fields": detailed_fields,
    }

    csv_headers = [
        "logged_at_utc",
        "method",
        "host",
        "uri",
        "name",
        "email",
        "reason",
        "grade",
        "availability",
        "found",
        "else",
        "unique_id",
        "location",
        "city",
        "region",
        "country",
        "cf_region_code",
        "cf_postal_code",
        "cf_timezone",
        "cf_iplatitude",
        "cf_iplongitude",
        "cf_ipcontinent",
        "cf_metro_code",
        "cdn_loop",
        "x_forwarded_proto",
        "cf_visitor",
        "user_agent",
        "sender_ip",
        "edge_remote_ip",
        "x_real_ip",
        "x_forwarded_for",
        "cf_connecting_ip",
        "cf_ray",
        "cf_server",
        "isp_display",
        "ipregistry_company_name",
        "ipregistry_company_domain",
        "ipregistry_connection_org",
        "ipregistry_connection_domain",
        "is_denver_or_boulder",
        "request_headers_json",
        "request_json",
        "ipregistry_json",
    ]
    csv_row = {
        "logged_at_utc": timestamp_utc,
        "method": request.method,
        "host": text(request.host),
        "uri": text(uri),
        "name": text(name),
        "email": text(email),
        "reason": text(reason),
        "grade": text(grade),
        "availability": text(availability),
        "found": text(found),
        "else": text(else_text),
        "unique_id": text(unique_id),
        "location": text(location_value),
        "city": text(city),
        "region": text(region),
        "country": text(country),
        "cf_region_code": text(cf_values.get("CF-Region-Code")),
        "cf_postal_code": text(cf_values.get("CF-Postal-Code")),
        "cf_timezone": text(cf_values.get("CF-Timezone")),
        "cf_iplatitude": text(cf_values.get("CF-IPlatitude")),
        "cf_iplongitude": text(cf_values.get("CF-IPLongitude")),
        "cf_ipcontinent": text(cf_values.get("CF-IPContinent")),
        "cf_metro_code": text(cf_values.get("CF-Metro-Code")),
        "cdn_loop": text(cf_values.get("CDN-Loop")),
        "x_forwarded_proto": text(cf_values.get("X-Forwarded-Proto")),
        "cf_visitor": text(cf_values.get("CF-Visitor")),
        "user_agent": text(request_user_agent),
        "sender_ip": text(sender_data.get("sender_ip")),
        "edge_remote_ip": text(sender_data.get("edge_remote_ip")),
        "x_real_ip": text(sender_data.get("x_real_ip")),
        "x_forwarded_for": text(sender_data.get("x_forwarded_for")),
        "cf_connecting_ip": text(sender_data.get("cf_connecting_ip")),
        "cf_ray": text(sender_data.get("cf_ray")),
        "cf_server": text(sender_data.get("cf_server")),
        "isp_display": text(isp),
        "ipregistry_company_name": text(company_data.get("name")),
        "ipregistry_company_domain": text(company_data.get("domain")),
        "ipregistry_connection_org": text(connection_data.get("organization")),
        "ipregistry_connection_domain": text(connection_data.get("domain")),
        "is_denver_or_boulder": "yes" if is_front_range_priority else "no",
        "request_headers_json": json.dumps(dict(request.headers), ensure_ascii=True, sort_keys=True),
        "request_json": json.dumps(data, ensure_ascii=True, sort_keys=True),
        "ipregistry_json": json.dumps(ipregistry_data, ensure_ascii=True, sort_keys=True),
    }
    try:
        csv_dir = os.path.dirname(SUBMISSIONS_CSV_PATH)
        if csv_dir != "":
            os.makedirs(csv_dir, exist_ok=True)
        csv_exists = os.path.exists(SUBMISSIONS_CSV_PATH)
        csv_needs_header = (not csv_exists) or os.path.getsize(SUBMISSIONS_CSV_PATH) == 0
        with open(SUBMISSIONS_CSV_PATH, "a", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=csv_headers)
            if csv_needs_header:
                writer.writeheader()
            writer.writerow(csv_row)
    except OSError:
        pass

    requests.post(MESSAGES_WEBHOOK, json={"embeds": [simple_embed]}, timeout=10)
    requests.post(SUBMISSION_WEBHOOK, json={"embeds": [detailed_embed]}, timeout=10)
    return "Successfully processed", 200


@app.route("/api/avatars/<int:user_id>/avatar.png", methods=["GET"])
def discord_avatar(user_id: int):
    if DISCORD_BOT_TOKEN is None or DISCORD_BOT_TOKEN == "":
        return "Bot token not configured", 500

    user_url = "https://discord.com/api/v10/users/" + str(user_id)
    user_resp = requests.get(user_url, headers={"Authorization": "Bot " + DISCORD_BOT_TOKEN}, timeout=10)
    if user_resp.status_code != 200:
        return "Unable to fetch user", user_resp.status_code

    user_data = user_resp.json()
    avatar_hash = user_data.get("avatar")
    if avatar_hash is None or avatar_hash == "":
        return "User has no custom avatar", 404

    avatar_url = "https://cdn.discordapp.com/avatars/" + str(user_id) + "/" + avatar_hash + ".png?size=256"
    avatar_resp = requests.get(avatar_url, timeout=10)
    if avatar_resp.status_code != 200:
        return "Unable to fetch avatar", avatar_resp.status_code

    return Response(avatar_resp.content, mimetype="image/png")


app.run(host="0.0.0.0", port=6768)
