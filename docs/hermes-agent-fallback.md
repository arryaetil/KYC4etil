# Hermes Agent als fallback

Hermes Agent is hier geen primaire vervanger van de bestaande jaarverslag-flow.
De normale route blijft eerst draaien:

1. website-agent en jaarverslag-agent proberen de bron te vinden
2. de backend valideert en slaat de uitkomst op
3. als de flow faalt of te onzeker blijft, gaat de case naar Hermes

## Wanneer Hermes inzetten

- geen bruikbare PDF of bron gevonden
- wel bron, maar geen `wp_gevonden`
- meerdere tegenstrijdige signalen
- lage zekerheid of onduidelijke vestiging
- moeilijke uitzonderingen die handmatige zoektocht kosten

## Wat Hermes wel doet

- brononderzoek
- webnavigatie
- PDF-verkenning
- samenvatten en structureren van bevindingen

## Wat Hermes niet doet

- direct de waarheid overschrijven in de database
- de bestaande scoring of review-flow vervangen
- ongevraagde wijzigingen buiten het afgesproken contract maken

## Integratieprincipe

Gebruik Hermes als research-escapeklep met een strak JSON-contract. De
backend blijft eigenaar van opslag, validatie en audit trail.
