# Migratie naar één bronnenwerkbank

## Besluit

KYC4etil vindt en beoordeelt bronnen. Het beheert geen vestigingsregister, voert
geen WP-waarde automatisch door en stuurt geen chatuitnodigingen.

De canonieke gegevensstroom is:

`User → Batch → Company → ResearchRun → BronKandidaat → reviewbeslissing`

## Uitgevoerd

- De oude chat-, review- en jaarverslaguploadrouters zijn uit de actieve app gehaald.
- De publieke chatroute en ongebruikte frontend-API's zijn verwijderd.
- Batchoverzichten lezen alleen nog uit research-runs en bronkandidaten.
- De Excel-export bevat per organisatie alleen een geaccepteerde bron.
- Monitoring schrijft nieuwe vondsten niet meer dubbel naar `Candidate` en
  `AgentResult`.
- Accepteren en afwijzen hebben vaste redencodes. Bij `anders` is toelichting
  verplicht.
- Een reviewer kan één primaire en meerdere ondersteunende relevante bronnen
  bewaren.
- WP-extractiefeedback bewaart het oorspronkelijke en gecorrigeerde aantal,
  afwijkingsreden en volledigheid van de ingelezen bron.
- Research-runs bewaren een klein SBI-gestuurd routeplan met eindstatus per
  route; DUO, DigiMV en team-/afspraakonderzoek zijn de eerste sectorroutes.
- De DUO-route leest voor PO, VO en MBO rechtstreeks adres- en personeelsdata
  in personen in. Instellingscodes en deelwaarden blijven als auditmetadata
  bewaard; meerdere instellingen worden nooit stilzwijgend opgeteld.

## Veilig teruggaan

De toestand vóór deze migratie staat lokaal op:

- tag `archive/chat-workflow-v1`;
- branch `archive/chat-workflow`.

Publiceren van deze refs naar een externe Git-server gebeurt alleen na expliciete
toestemming.

## Productiedatabase

Deze migratie voegt review- en extractiefeedbackvelden toe aan
`bron_kandidaten`. Historische
tabellen worden bewust nog niet gedropt. Maak eerst een databaseback-up, rol de
nieuwe versie uit en observeer minimaal één volledige gebruikscyclus. Verwijder
oude tabellen pas in een afzonderlijke, expliciet goedgekeurde migratie nadat is
vastgesteld dat geen actieve code of rapportage ze nog leest.

## Controle na uitrol

1. Upload een kleine lijst en start bronnenonderzoek.
2. Accepteer één bron en wijs één bron af met een vaste reden.
3. Controleer de reviewerstatistieken en Excel-export.
4. Start monitoring en bevestig dat een vondst als `ResearchRun` en
   `BronKandidaat` verschijnt.
5. Bevestig dat chat-, bellijst-, kandidaat-review- en handmatige
   jaarverslagroutes niet meer in OpenAPI staan.
