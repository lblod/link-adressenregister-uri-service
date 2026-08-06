# link-adressenregister-uri-service

Service for data quality improvements in LBLOD. It scans all addresses in a triplestore and compares their data to the [adressenregister](https://www.vlaanderen.be/datavindplaats/catalogus/adressenregister-crab) in order to find a matching address URI. The service then compares the (optional) linked URI in the triplestore to the (optional) matched URI and updates the triplestore accordingly. 

## Prerequisites

The service will use the following query to query all addresses in the triplestore:

```
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
```

This means it requires the stack to have the same data model. 

## Setup

Add the following to the `docker-compose.yml` file:

```
  link-adressenregister-uri:
    image: lblod/link-adressenregister-uri-service
    environment:
      MU_SPARQL_ENDPOINT: "http://triplestore:8890/sparql"
      MU_SPARQL_UPDATEPOINT: "http://triplestore:8890/sparql"
      CRON_SCHEDULE: "0 0 * * *"
```

Then run `drc up -d link-adressenregister-uri`

The following variables are required:

- `MU_SPARQL_ENDPOINT`
- `MU_SPARQL_UPDATEPOINT`

The variable `CRON_SCHEDULE` is optional. By default its value is `"0 0 * * *"`.

## How to run

The service will run a scheduled job every day at midnight. This pattern can be altered by setting the `CRON_SCHEDULE` variable.
It can also be manually triggered by running `curl -X POST http://localhost:8080/run` (assuming the service is exposed on port 8080).