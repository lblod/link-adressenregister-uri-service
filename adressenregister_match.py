import requests
import unicodedata
from urllib.parse import urlencode
import json
import time
from helpers import log

DEFAULT_COUNTRY = "België"
BASISREGISTER_ADRESMATCH = "https://basisregisters.vlaanderen.be/api/v2/adressen"

def get_basisregister_adres_match(
    municipality=None,
    zipcode=None,
    thoroughfarename=None,
    housenumber=None,
    bus=None
):
    params = {}

    if municipality:
        params["GemeenteNaam"] = replace_accents(municipality)

    if zipcode:
        params["Postcode"] = replace_accents(str(zipcode))

    if thoroughfarename:
        params["Straatnaam"] = replace_accents(thoroughfarename)

    if housenumber:
        params["Huisnummer"] = replace_accents(str(housenumber))

    if bus:
        params["Busnummer"] = replace_accents(str(bus))

    if not params:
        return []

    query_string = urlencode(params)
    url = f"{BASISREGISTER_ADRESMATCH}?{query_string}"

    response = get_with_retry(url)

    return process_basisregister_response(response.json())

def replace_accents(value: str) -> str:
    """
    Remove accents/diacritics from a string.
    """
    if value is None:
        return ""

    normalized = unicodedata.normalize("NFKD", value)
    return "".join(c for c in normalized if not unicodedata.combining(c))

def try_json_parse(value):
    """
    Parse JSON safely.
    Returns None if parsing fails.
    """
    try:
        if isinstance(value, str):
            return json.loads(value)

        return value

    except (json.JSONDecodeError, TypeError):
        return None

def add_default_country_to_basisregister_address(address):
    """
    Adds the default country to the address object.
    Also appends the country to the spelling field when taal == 'nl'.
    """
    full_address = (
        address.get("volledigAdres", {})
               .get("geografischeNaam", {})
    )

    if full_address.get("taal") == "nl":
        spelling = full_address.get("spelling", "")
        full_address["spelling"] = f"{spelling}, {DEFAULT_COUNTRY}"

    address["land"] = DEFAULT_COUNTRY

    return address

def process_basisregister_response(response):
    """
    Processes the basisregister API response.
    Handles:
    - JSON string input
    - already parsed dict input
    - list of addresses
    """
    results = try_json_parse(response)

    if not results:
        return []

    if (
        isinstance(results, dict)
        and "adressen" in results
        and isinstance(results["adressen"], list)
    ):
        return [
            add_default_country_to_basisregister_address(address)
            for address in results["adressen"]
        ]

    return add_default_country_to_basisregister_address(results)

def get_with_retry(
    url,
    params=None,
    headers=None,
    retries=3,
    backoff_factor=0.5,
    timeout=10,
):
    for attempt in range(retries):
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            return response

        except requests.RequestException as e:
            log(f"It seems request failed for attempt " +  str(attempt))
            if attempt == retries - 1:
                log(f"Request failed for {params}: {e}")
                return None

            sleep_time = backoff_factor * (2 ** attempt)
            log("sleeping " + str(sleep_time) + " seconds..")
            time.sleep(sleep_time)