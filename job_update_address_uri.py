from typing import Dict
from queries import insert_uri_query, correct_uri_query, remove_uri_query, get_addresses
from adressenregister_match import get_basisregister_adres_match
from helpers import log

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

    lookup = get_basisregister_adres_match(
        entry.get("addressGemeenteNaam"),
        entry.get("addressGemeentePostCode"),
        entry.get("addressStreet"),
        entry.get("addressGemeenteNummer"),
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

        bus = entry.get("addressBus")
        if bus and bus.strip():
            bus_part = f" bus {bus}"
        else:
            bus_part = ""


        expected = f"{entry.get('addressStreet')} {entry.get('addressGemeenteNummer')}{bus_part}, " \
                   f"{entry.get('addressGemeentePostCode')} {entry.get('addressGemeenteNaam')}, " \
                   f"{entry.get('addressGemeenteLand')}"

        if volledig_adres.strip() == expected.strip():
            matches.append(result)

    matches = [m for m in matches if m.get("adresStatus") == "inGebruik"]

    if len(matches) == 0:
        log(f"No matches found for {entry.get('address')}")

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

def run():
    addresses = get_addresses()
    count = len(addresses)

    if(count == 0):
        log("No addresses found, exiting.")
        return

    remove_uri_addresses = []
    adjust_uri_addresses = []
    add_uri_addresses = []
    no_match_addresses = []
    skipped_addresses = []

    current_count = 1

    for address in addresses:
        log(f"Processing address {current_count}/{count}: {address.get('address')}")
        current_count += 1

        match_result = try_match_address(address)

        status = match_result["status"]
        adress_register = match_result["uri"]

        # We sort the addresses:
        if(status in ["lookup_failed", "multiple_matches"]):
            skipped_addresses.append(address)
            continue
        elif(status == "no_match"):
            if(address.get('uri')):
                remove_uri_addresses.append(address)
            else:
                no_match_addresses.append(address)
        elif(status == "matched"):
            if(address.get('uri') and address.get('uri') != adress_register):
                address['addressRegister'] = adress_register
                adjust_uri_addresses.append(address)
            elif(not address.get('uri')):
                address['addressRegister'] = adress_register
                add_uri_addresses.append(address)

    log(f"Found {len(remove_uri_addresses)} addresses where URI should be empty but is not.")
    log(f"Found {len(adjust_uri_addresses)} addresses with mismatched URI.")
    log(f"Found {len(add_uri_addresses)} addresses with missing URI.")
    log(f"Found {len(no_match_addresses)} addresses with no match in address register.")

    # write queries and send them to database
    insert_uri_query(add_uri_addresses)
    remove_uri_query(remove_uri_addresses)
    correct_uri_query(adjust_uri_addresses)

    log("Processing completed.")
