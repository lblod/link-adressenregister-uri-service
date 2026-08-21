from typing import Dict
from queries import insert_uri_query, correct_uri_query, remove_uri_query, get_addresses
from adressenregister_match import get_basisregister_adres_match
from helpers import log
import math

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/sparql-results+json",
}
HEADERS_ADRESS = {
  "Accept": "application/json",
}

def try_match_address(entry: Dict) -> Dict:
    """
    Try to match an address via the address register.
    """

    house_number = entry.get("addressGemeenteNummer")
    if house_number and not house_number.strip():
        house_number = None
    elif house_number and not house_number[0].isdigit():
        # if the first character of the house number is not a digit, we assume the address has no house number and we set it to None (e.g. "z/n")
        house_number = None

    if not entry.get("addressGemeenteLand"):
        entry["addressGemeenteLand"] = "België"

    lookup = get_basisregister_adres_match(
        entry.get("addressGemeenteNaam"),
        entry.get("addressGemeentePostCode"),
        entry.get("addressStreet"),
        house_number,
        entry.get("addressBus")
    )

    if lookup["status"] == "lookup_failed":
        log(f"Lookup failed for {entry.get('address')}")

        return {
            "status": "lookup_failed",
            "uri": None
        }

    data = lookup["results"]

    matches = []

    for result in data:
        volledig_adres = (
            result
            .get("volledigAdres", {})
            .get("geografischeNaam", {})
            .get("spelling", "")
        )

        if house_number:
            house_number_part = f" {house_number}"
        else:
            house_number_part = ""

        bus = entry.get("addressBus")
        if bus and bus.strip():
            bus_part = f" bus {bus}"
        else:
            bus_part = ""

        expected = f"{entry.get('addressStreet')}{house_number_part}{bus_part}, " \
                   f"{entry.get('addressGemeentePostCode')} {entry.get('addressGemeenteNaam')}, " \
                   f"{entry.get('addressGemeenteLand')}"

        if volledig_adres.strip() == expected.strip():
            matches.append(result)

    matches = [m for m in matches if m.get("adresStatus") == "inGebruik"]

    if len(matches) == 0:
        log(f"No matches found for {entry.get('address')}")
        if not house_number:
            log(f"Note: No house number provided for {entry.get('address')}, this might be the reason for no matches.")
            return {
                "status": "no_housenumber",
                "uri": None
            }

        return {
            "status": "no_match",
            "uri": None
        }

    if len(matches) > 1:
        log(f"WARNING: Too many matches found for {entry.get('address')}")

        return {
            "status": "multiple_matches",
            "uri": None
        }

    identificator = matches[0].get("identificator", {})

    id = identificator.get("id")
    log(f"For <{entry.get('address')}> found URI <{id}> in address register.")

    return {
        "status": "matched",
        "uri": id
    }

def process_addresses(addresses: list, count: int, start_index: int) -> Dict:
    stats = {
        "remove_uri": 0,
        "adjust_uri": 0,
        "add_uri": 0,
        "no_match": 0,
        "skipped": 0,
        "no_housenumber": 0,
    }
    remove_uri_addresses = []
    adjust_uri_addresses = []
    add_uri_addresses = []

    current_count = start_index

    for address in addresses:
        log(f"Processing address {current_count}/{count}: {address.get('address')}")
        current_count += 1

        match_result = try_match_address(address)

        status = match_result["status"]
        adress_register = match_result["uri"]

        # We sort the addresses:
        if(status in ["lookup_failed", "multiple_matches"]):
            stats["skipped"] += 1
            continue
        elif(status == "no_housenumber"):
            stats["no_housenumber"] += 1
            continue
        elif(status == "no_match"):
            if(address.get('uri')):
                remove_uri_addresses.append(address)
                stats["remove_uri"] += 1
            else:
                stats["no_match"] += 1
        elif(status == "matched"):
            if(address.get('uri') and address.get('uri') != adress_register):
                address['addressRegister'] = adress_register
                adjust_uri_addresses.append(address)
                stats["adjust_uri"] += 1
            elif(not address.get('uri')):
                address['addressRegister'] = adress_register
                add_uri_addresses.append(address)
                stats["add_uri"] += 1

    # write queries and send them to database
    try:
        insert_uri_query(add_uri_addresses)
        remove_uri_query(remove_uri_addresses)
        correct_uri_query(adjust_uri_addresses)
    except Exception as e:
        log(f"Error while executing query: {e}")

    return stats

def batch(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]

def run():
    addresses = get_addresses()
    count = len(addresses)

    if count == 0:
        log("No addresses found, exiting.")
        return

    batch_size = 10
    total_batches = math.ceil(count/batch_size)

    totals = {
        "remove_uri": 0,
        "adjust_uri": 0,
        "add_uri": 0,
        "no_match": 0,
        "skipped": 0,
        "no_housenumber": 0,
    }

    for batch_num, address_batch in enumerate(batch(addresses, batch_size), start=1):
        log(f"Processing batch {batch_num}/{total_batches} ")
        
        start_index = (batch_num - 1) * batch_size + 1
        stats = process_addresses(address_batch, count, start_index)

        for key in totals:
            totals[key] += stats[key]

    log(f"Found {totals['remove_uri']} addresses where URI should be empty but is not.")
    log(f"Found {totals['adjust_uri']} addresses with mismatched URI.")
    log(f"Found {totals['add_uri']} addresses with missing URI.")
    log(f"Found {totals['no_match'] + totals['no_housenumber']} addresses with no match in address register.")
    log(f"Of those with no match, {totals['no_housenumber']} had no house number, which might be the reason for no match.")

    log("Processing completed.")
