import os
from typing import Dict, Optional
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

def try_match_address(entry: Dict) -> Optional[str]:
    """
    Try to match an address via the address register.
    If exactly one result is returned and the formatted address matches,
    return the adres identificator id.
    """

    data = get_basisregister_adres_match(
        entry.get("addressGemeenteNaam"),
        entry.get("addressGemeentePostCode"),
        entry.get("addressStreet"),
        entry.get("addressGemeenteNummer"),
        entry.get("addressBus")
    )

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

        if volledig_adres.strip() != expected.strip():
            continue
        else:
            matches.append(result)

    matches = [m for m in matches if m.get("adresStatus") == "inGebruik"]

    if len(matches) == 0:
        log("No matches found for " + entry.get('address'))
        return

    if len(matches) > 1:
        log("WARNING: Too many matches found for " + entry.get('address'))
        return

    identificator = matches[0].get("identificator", {})

    id = identificator.get("id")
    log(f"For <{entry.get('address')}> found URI <{id}> in address register.")

    return id

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

    current_count = 1

    for address in addresses:
        log(f"Processing address {current_count}/{count}: {address.get('address')}")
        current_count += 1

        adress_register = try_match_address(address)

        # We sort the addresses:
        if(address.get('uri') and not adress_register):
            remove_uri_addresses.append(address)
        elif(not address.get('uri') and not adress_register):
            no_match_addresses.append(address)
        elif(address.get('uri') and adress_register and address.get('uri') != adress_register):
            address['addressRegister'] = adress_register
            adjust_uri_addresses.append(address)
        elif(not address.get('uri') and adress_register):
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
