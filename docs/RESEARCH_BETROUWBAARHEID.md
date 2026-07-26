# Researchbetrouwbaarheid

## Centrale timeout

Iedere researchrun gebruikt `RESEARCH_COMPANY_TIMEOUT_SECONDS` (standaard
300 seconden), ongeacht of de run los of als onderdeel van een batch wordt
gestart. Bij een timeout krijgt de run de status `error` en een expliciete
foutmelding. Een batch gaat daarna verder met de volgende organisatie.

Kandidaten worden pas na afronding van de onderzoekspaden opgeslagen. Een
afgebroken run bevat daarom geen gedeeltelijke kandidaten en kan veilig opnieuw
worden gestart.

## Reviewerstatistieken

De read-only endpoint `GET /research/reviewer-statistics` maakt de kwaliteit
van de aangeleverde bronnen meetbaar. Met de optionele queryparameter
`batch_id` wordt de berekening beperkt tot één batch.

De respons bevat:

- het aantal expliciet beoordeelde, geaccepteerde en afgewezen bronnen;
- het acceptatiepercentage;
- de rangverdeling van geaccepteerde bronnen en het aandeel op rang 1;
- de opgegeven afwijsredenen;
- het aantal afgeronde runs en het gemiddelde aantal kandidaten per run.

Alleen kandidaten van de onderzoeksagent tellen mee. Handmatig toegevoegde
bronnen worden uitgesloten, zodat deze cijfers de bronvinding meten en niet de
aanvullingen van medewerkers. Een expliciet geaccepteerde bron die later door
een nieuwe keuze de status `alternatief` kreeg, blijft als acceptatie meetellen.

De statistieken zijn beschrijvend. Er wordt nog geen automatische
rankingkalibratie of modeltraining aan gekoppeld; daarvoor is eerst voldoende
reviewvolume en een aparte evaluatieset nodig.
