from helpers import query, update
from collections import defaultdict
from escape_helpers import sparql_escape_uri
from typing import List, Dict

def get_addresses() -> Dict:
    """
    Fetch all addresses with their linked uri's (if they exist).
    """
    addresses_query = """
        SELECT DISTINCT
            ?graph
            ?address
            ?addressStreet
            ?addressGemeenteNaam
            ?addressGemeenteLand
            ?addressGemeentePostCode
            ?addressGemeenteNummer
            ?addressBus
            ?uri
        WHERE {
            GRAPH ?graph {
                ?address a <http://www.w3.org/ns/locn#Address>;
                    <http://www.w3.org/ns/locn#thoroughfare> ?addressStreet;
                    <https://data.vlaanderen.be/ns/adres#gemeentenaam> ?addressGemeenteNaam;
                    <http://www.w3.org/ns/locn#postCode> ?addressGemeentePostCode.
                    
                OPTIONAL { ?address <https://data.vlaanderen.be/ns/adres#Adresvoorstelling.huisnummer> ?addressGemeenteNummer. }
                OPTIONAL { ?address <https://data.vlaanderen.be/ns/adres#verwijstNaar> ?uri. }
                OPTIONAL { ?address <https://data.vlaanderen.be/ns/adres#Adresvoorstelling.busnummer> ?addressBus. }
                OPTIONAL { ?address <https://data.vlaanderen.be/ns/adres#land> ?addressGemeenteLand . }
            }
        }
    """
    result = query(addresses_query)
    rows = extract_bindings(result)
    return rows

def insert_uri_query(entries: List[dict]):
    """
    Write INSERT DATA statements grouped per graph into a sparql query.
    This is used to add matching address URI's to addresses, 
    where the address entry has no URI but the address register has a match with a URI.
    """

    if not entries:
        return

    grouped: dict[str, List[dict]] = defaultdict(list)
    for entry in entries:
        grouped[entry["graph"]].append(entry)

    blocks: List[str] = []

    for graph, items in grouped.items():
        lines: List[str] = []
        for item in items:
            address = f"{sparql_escape_uri(item['address'])}"
            uri = f"{sparql_escape_uri(item['addressRegister'])}"
            lines.append(f"    {address} <https://data.vlaanderen.be/ns/adres#verwijstNaar> {uri} .")
            lines.append(f"""  {uri} <http://www.w3.org/2004/02/skos/core#note> "Attached to {address} with service" .""")

        block = (
            "INSERT DATA {\n"
            f"  GRAPH {sparql_escape_uri(graph)} {{\n"
            + "\n".join(lines)
            + "\n  }\n"
            "}\n"
        )
        blocks.append(block)

    content = "\n;\n\n".join(blocks) + "\n;"
    update(content)

def remove_uri_query(entries: List[dict]):
    """
    Write UPDATE statements grouped per graph into a sparql query.
    This is used to remove incorrect URI's from addresses, 
    where the URI in the address register is empty but the address entry still has a URI.
    We keep the incorrect URI in a separate predicate.
    """

    if not entries:
        return

    grouped: dict[str, List[dict]] = defaultdict(list)
    for entry in entries:
        grouped[entry["graph"]].append(entry)

    blocks: List[str] = []

    for graph, items in grouped.items():
        delete_lines: List[str] = []
        insert_lines: List[str] = []
        for item in items:
            address = f"{sparql_escape_uri(item['address'])}"
            uri = f"{sparql_escape_uri(item['uri'])}"
            delete_lines.append(f"    {address} <https://data.vlaanderen.be/ns/adres#verwijstNaar> {uri} .")
            insert_lines.append(f"    {address} <http://mu.semte.ch/vocabularies/ext/ProbablyObsoleteAddressUri> {uri} .")
            insert_lines.append(f"""    {uri} <http://www.w3.org/2004/02/skos/core#note> "Detached from {address} with service" .""")

        block = (
            "DELETE {\n"
            f"  GRAPH {sparql_escape_uri(graph)} {{\n"
            + "\n".join(delete_lines)
            + "\n  }\n"
            "}\n"
            "INSERT {\n"
            f"  GRAPH {sparql_escape_uri(graph)} {{\n"
            + "\n".join(insert_lines)
            + "\n  }\n"
            "}\n"
        )
        blocks.append(block)

    content = "\n;\n\n".join(blocks) + "\n;"
    update(content)

def correct_uri_query(entries: List[dict]):
    """
    Write UPDATE statements grouped per graph into a sparql query.
    This is used to remove incorrect URI's from addresses, 
    where the URI in the address register is different than the URI of the address entry.
    We keep the incorrect URI in a separate predicate.
    """

    if not entries:
        return

    grouped: dict[str, List[dict]] = defaultdict(list)
    for entry in entries:
        grouped[entry["graph"]].append(entry)

    blocks: List[str] = []

    for graph, items in grouped.items():
        delete_lines: List[str] = []
        insert_lines: List[str] = []
        for item in items:
            address = f"{sparql_escape_uri(item['address'])}"
            uri = f"{sparql_escape_uri(item['uri'])}"
            new_uri = f"{sparql_escape_uri(item['addressRegister'])}"
            delete_lines.append(f"    {address} <https://data.vlaanderen.be/ns/adres#verwijstNaar> {uri} .")
            insert_lines.append(f"    {address} <https://data.vlaanderen.be/ns/adres#verwijstNaar> {new_uri} .")
            insert_lines.append(f"    {address} <http://mu.semte.ch/vocabularies/ext/ProbablyObsoleteAddressUri> {uri} .")
            insert_lines.append(f"""    {uri} <http://www.w3.org/2004/02/skos/core#note> "Detached from {address} with service" .""")

        block = (
            "DELETE {\n"
            f"  GRAPH {sparql_escape_uri(graph)} {{\n"
            + "\n".join(delete_lines)
            + "\n  }\n"
            "}\n"
            "INSERT {\n"
            f"  GRAPH {sparql_escape_uri(graph)} {{\n"
            + "\n".join(insert_lines)
            + "\n  }\n"
            "}\n"
        )
        blocks.append(block)

    content = "\n;\n\n".join(blocks) + "\n;"
    update(content)

def extract_bindings(result: Dict) -> List[Dict[str, str]]:
    """
    Flatten SPARQL JSON bindings into simple dicts.
    """
    keys = result['head']['vars']
    bindings = result.get("results", {}).get("bindings", [])
    rows = []
    for binding in bindings:
        row = {}
        for key in keys:
            row[key] = binding.get(key, {}).get("value", "")
        rows.append(row)
    return rows