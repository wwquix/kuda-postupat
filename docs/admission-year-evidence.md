# Admission year evidence for the future BSEU backfill

Checked on 13 July 2026 (Europe/Minsk). Conclusion: the explicit `admission_year` for the next controlled BSEU backfill may safely be **2026**. This milestone does not assign that year to legacy rows and does not perform the backfill.

## Official evidence

1. Current official BSEU applications XML: <https://bseu.by/abiturient/xml/1.xml>
   - HTTP 200 at verification time.
   - HTTP `Last-Modified`: `Sun, 12 Jul 2026 15:00:00 GMT`.
   - 77 rows; every row has `genTime="12.07.2026 18:00"`.
   - Exactly one monitored row matches «Экономическая информатика» + `дневная` + paid source code `IDFINANCE=19`; it reports `PlanVneBudj=60` and `AllCount=11` with the same 2026 generation time.

2. Official BSEU 2026 admission-plan PDF: <https://bseu.by/russian/abiturient/tsp2026.pdf>
   - The document title states that these are admission figures for general higher education in 2026 at BSEU.
   - It lists code `6-05-0311-05`, «Экономическая информатика», and 60 full-time paid places, matching the monitored XML row.

3. Official admission landing page linked by current settings: <https://bseu.by/abiturient/>
   - HTTP 200 at verification time.
   - The rendered/source page itself did not expose a visible `2026` marker and still contained `2023` references. It is therefore retained as the official navigation context, but it is not used alone to infer the year.

## Repository cross-check

`backend/data/research/universities-canonical-2026.json` and its schema explicitly declare `admission_year: 2026`. This is corroborating project research, not the primary official evidence.

## Decision and assumptions

The year is not inferred from the current wall-clock year, filename alone, or an undocumented mapping. The official PDF explicitly names 2026, and its program/plan facts agree with the current official XML whose source rows are timestamped in July 2026. Therefore Migration C may accept `2026` as an explicit reviewed parameter. It must still perform its own pre-backfill source check and must not silently derive a different year.
