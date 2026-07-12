# Universities source audit — Belarus, 2026

## Scope

This milestone verifies the current official list of Belarusian higher education institutions, each institution’s registry-backed official site, an official admissions-related page where one could be opened, and a shallow map of applicant-data availability. It does not parse documents, build adapters, import records into SQLite, or assess academic quality. Russian branches are reviewed separately and are not counted as standalone Belarusian institutions.

## Research date and methodology

- Checked: 2026-07-12 21:14:28 +03:00 (`Europe/Minsk`).
- Primary evidence: the Ministry of Education’s current higher-education system page and its regional/private institution registry pages.
- Verification: direct HTTP GET with redirects enabled, official-domain identity checks, and bounded inspection of official navigation links. No Playwright, CAPTCHA bypass, authentication, unofficial catalog as sole evidence, or inferred URL was used.
- `available` means a matching official source was found and opened; `not_found` means the bounded surface check found no matching official source; `unknown` means the official site could not be reliably opened. `partial` is reserved for incomplete source coverage.
- Editorial categories describe obvious subject profile and are not legal classifications.

## Primary official registries

| Source | Coverage | Checked | HTTP |
|---|---|---:|---:|
| [Higher education system](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/informatsiya-o-sisteme-vysshego-obrazovaniya/) | Confirms 47 UVO: 43 state and 4 private | 2026-07-12 21:14 +03:00 | 200 |
| [Institution registry index](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/index.php) | Six regional lists, Minsk, private institutions, licensed Russian branches | 2026-07-12 21:14 +03:00 | 200 |
| [Брест и Брестская область](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/brest-i-brestskaya-oblast/index.php) | Current institution entries with names, cities, sites, and supervising bodies. | 2026-07-12 21:14 +03:00 | 200 |
| [Витебск и Витебская область](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/vitebsk-i-vitebskaya-oblast/index.php) | Current institution entries with names, cities, sites, and supervising bodies. | 2026-07-12 21:14 +03:00 | 200 |
| [Гомель и Гомельская область](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/gomel-i-gomelskaya-oblast/index.php) | Current institution entries with names, cities, sites, and supervising bodies. | 2026-07-12 21:14 +03:00 | 200 |
| [Гродно и Гродненская область](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/grodno-i-grodnenskaya-oblast/index.php) | Current institution entries with names, cities, sites, and supervising bodies. | 2026-07-12 21:14 +03:00 | 200 |
| [Могилев и Могилевская область](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/mogilev-i-mogilevskaya-oblast/index.php) | Current institution entries with names, cities, sites, and supervising bodies. | 2026-07-12 21:14 +03:00 | 200 |
| [Минск](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/g-minsk/index.php) | Current institution entries with names, cities, sites, and supervising bodies. | 2026-07-12 21:14 +03:00 | 200 |
| [Частные учреждения](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/chastnye-uchrezhdeniya/index.php) | Current institution entries with names, cities, sites, and supervising bodies. | 2026-07-12 21:14 +03:00 | 200 |
| [Licensed Russian branches](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/filialy-uchrezhdeniy/index.php) | Two branches listed separately from Belarusian institutions. | 2026-07-12 21:14 +03:00 | 200 |

The Ministry index separates state institutions by geography, private institutions, and licensed branches of Russian institutions. The Ministry system page’s total of 47 equals the 43 entries on the regional/Minsk pages plus the 4 entries on the private page; the two Russian branches are outside that total and outside `universities`. No publication date is displayed on these registry pages.

## Summary

- Confirmed: 47
- State: 43
- Private: 4
- Cities: 11
- With an official admissions URL: 33
- Preliminary monitoring candidates: 9
- Online monitoring: 1 (BSEU only)
- Review items: 5

## Confirmed universities

| Code | Short name | Full name | City | Ownership | Kind | Admissions | Monitoring assessment | Checked |
|---|---|---|---|---|---|---|---|---|
| `brsu` | БрГУ | Брестский государственный университет имени А.С. Пушкина | Брест | state | university | [yes](https://www.brsu.by/abi/abiturientu) | `reference_only` | 2026-07-12 |
| `bstu` | БрГТУ | Брестский государственный технический университет | Брест | state | university | not found / unavailable | `needs_research` | 2026-07-12 |
| `barsu` | БарГУ | Барановичский государственный университет | Барановичи | state | university | [yes](https://abit.barsu.by/index.php) | `reference_only` | 2026-07-12 |
| `polessu` | ПолесГУ | Полесский государственный университет | Пинск | state | university | [yes](https://www.polessu.by/%D0%B0%D0%B1%D0%B8%D1%82%D1%83%D1%80%D0%B8%D0%B5%D0%BD%D1%82%D1%83-2) | `reference_only` | 2026-07-12 |
| `vsavm` | ВГАВМ | Витебская ордена «Знак Почета» государственная академия ветеринарной медицины | Витебск | state | academy | [yes](https://www.vsavm.by/abiturientu/) | `candidate` | 2026-07-12 |
| `vsmu` | ВГМУ | Витебский государственный ордена Дружбы народов медицинский университет | Витебск | state | university | [yes](https://www.vsmu.by/abiturient/grafic-raboty.html) | `reference_only` | 2026-07-12 |
| `vstu` | ВГТУ | Витебский государственный технологический университет | Витебск | state | university | [yes](https://vstu.by/ru/postupayushchim/gajd-priemnoj-kampanii-vgtu-2026) | `reference_only` | 2026-07-12 |
| `vsu` | ВГУ | Витебский государственный университет имени П.М. Машерова | Витебск | state | university | [yes](https://vsu.by/sobytiya/378-priemnaya-kompaniya/13246-kalendar-abiturienta-priemnaya-kampaniya-2026.html) | `reference_only` | 2026-07-12 |
| `psu` | ПГУ | Полоцкий государственный университет имени Евфросинии Полоцкой | Новополоцк | state | university | not found / unavailable | `needs_research` | 2026-07-12 |
| `bsut` | БелГУТ | Белорусский государственный университет транспорта | Гомель | state | university | not found / unavailable | `needs_research` | 2026-07-12 |
| `gsmu` | ГомГМУ | Гомельский государственный медицинский университет | Гомель | state | university | [yes](https://gsmu.by/applicants/the_admissions_committee/) | `candidate` | 2026-07-12 |
| `gstu` | ГГТУ | Гомельский государственный технический университет имени П.О. Сухого | Гомель | state | university | [yes](https://abiturient.gstu.by/) | `candidate` | 2026-07-12 |
| `gsu` | ГГУ | Гомельский государственный университет имени Франциска Скорины | Гомель | state | university | not found / unavailable | `needs_research` | 2026-07-12 |
| `mspu` | МГПУ | Мозырский государственный педагогический университет имени И.П. Шамякина | Мозырь | state | university | [yes](https://mspu.by/index.php/ru/home/14382-priemnaya-komissiya) | `candidate` | 2026-07-12 |
| `ggau` | ГГАУ | Гродненский государственный аграрный университет | Гродно | state | university | [yes](https://abit.ggau.by/) | `reference_only` | 2026-07-12 |
| `grsmu` | ГрГМУ | Гродненский государственный медицинский университет | Гродно | state | university | [yes](http://grsmu.by/ru/university/structure/faculties/02/abiturient/) | `candidate` | 2026-07-12 |
| `grsu` | ГрГУ | Гродненский государственный университет имени Янки Купалы | Гродно | state | university | [yes](https://abit.grsu.by) | `reference_only` | 2026-07-12 |
| `baa` | БГСХА | Белорусская государственная орденов Октябрьской революции и Трудового Красного Знамени сельскохозяйственная академия | Горки | state | academy | not found / unavailable | `reference_only` | 2026-07-12 |
| `bru` | БРУ | Белорусско-Российский университет | Могилев | state | university | [yes](http://bru.by/content/abiturient) | `reference_only` | 2026-07-12 |
| `mi-mvd` | Могилевский институт МВД | Могилевский институт Министерства внутренних дел Республики Беларусь | Могилев | state | institute | not found / unavailable | `needs_research` | 2026-07-12 |
| `msu` | МГУ | Могилевский государственный университет имени А.А. Кулешова | Могилев | state | university | not found / unavailable | `needs_research` | 2026-07-12 |
| `bgut` | БГУТ | Белорусский государственный университет пищевых и химических технологий | Могилев | state | university | [yes](https://www.abit.bgut.by/) | `reference_only` | 2026-07-12 |
| `bsu` | БГУ | Белорусский государственный университет | Минск | state | university | not found / unavailable | `reference_only` | 2026-07-12 |
| `pac` | Академия управления | Академия управления при Президенте Республики Беларусь | Минск | state | academy | [yes](https://www.pac.by/intrant/) | `reference_only` | 2026-07-12 |
| `bntu` | БНТУ | Белорусский национальный технический университет | Минск | state | university | [yes](http://priem.bntu.by/ru/pk/) | `reference_only` | 2026-07-12 |
| `amia` | Академия МВД | Академия Министерства внутренних дел Республики Беларусь | Минск | state | military_academy | not found / unavailable | `needs_research` | 2026-07-12 |
| `bdam` | БГАИ | Белорусская государственная академия искусств | Минск | state | academy | [yes](https://bdam.by/enrollee/) | `reference_only` | 2026-07-12 |
| `bgam` | БГАМ | Белорусская государственная академия музыки | Минск | state | academy | [yes](https://bgam.by/abiturientu/) | `reference_only` | 2026-07-12 |
| `bsatu` | БГАТУ | Белорусский государственный аграрный технический университет | Минск | state | university | not found / unavailable | `needs_research` | 2026-07-12 |
| `bsmu` | БГМУ | Белорусский государственный медицинский университет | Минск | state | university | [yes](https://www.bsmu.by/abiturientu/) | `candidate` | 2026-07-12 |
| `bspu` | БГПУ | Белорусский государственный педагогический университет имени Максима Танка | Минск | state | university | [yes](https://bspu.by/events/osnovnoi-nabor-priemnoi-kampanii-v-bgpu-2026-goda) | `candidate` | 2026-07-12 |
| `belstu` | БГТУ | Белорусский государственный технологический университет | Минск | state | university | [yes](https://abiturient.belstu.by/) | `reference_only` | 2026-07-12 |
| `bsuir` | БГУИР | Белорусский государственный университет информатики и радиоэлектроники | Минск | state | university | [yes](https://www.bsuir.by/ru/priemnaya-komissiya) | `reference_only` | 2026-07-12 |
| `buk` | БГУКИ | Белорусский государственный университет культуры и искусств | Минск | state | university | not found / unavailable | `needs_research` | 2026-07-12 |
| `sportedu` | БГУФК | Белорусский государственный университет физической культуры | Минск | state | university | [yes](https://www.sportedu.by/postupayushhim/) | `reference_only` | 2026-07-12 |
| `bseu` | БГЭУ | Белорусский государственный экономический университет | Минск | state | university | [yes](https://bseu.by/abiturient/) | `online` | 2026-07-12 |
| `varb` | Военная академия | Военная академия Республики Беларусь | Минск | state | military_academy | [yes](https://varb.mil.by/conditions/anons/) | `candidate` | 2026-07-12 |
| `bsac` | БГАС | Белорусская государственная академия связи | Минск | state | academy | not found / unavailable | `needs_research` | 2026-07-12 |
| `ips` | ИПС РБ | Институт пограничной службы Республики Беларусь | Минск | state | institute | [yes](https://ips.gpk.gov.by/obrazovanie/abiturientu/) | `reference_only` | 2026-07-12 |
| `ucp` | УГЗ | Университет гражданской защиты Министерства по чрезвычайным ситуациям Республики Беларусь | Минск | state | university | not found / unavailable | `needs_research` | 2026-07-12 |
| `bgaa` | БГАА | Белорусская государственная академия авиации | Минск | state | academy | [yes](https://abiturient.bgaa.by/) | `reference_only` | 2026-07-12 |
| `bsufl` | БГУИЯ | Белорусский государственный университет иностранных языков | Минск | state | university | [yes](https://bsufl.by/entrant/) | `reference_only` | 2026-07-12 |
| `unan` | Университет НАН Беларуси | Университет Национальной академии наук Беларуси | Минск | state | university | [yes](https://unan.by/postupayushhim/) | `reference_only` | 2026-07-12 |
| `bteu` | БТЭУ | Белорусский торгово-экономический университет потребительской кооперации | Гомель | private | university | [yes](https://abiturient.bteu.by/) | `candidate` | 2026-07-12 |
| `isz` | ИСЗ | Институт современных знаний имени А.М. Широкова | Минск | private | institute | [yes](https://isz.minsk.by/abiturientu/) | `reference_only` | 2026-07-12 |
| `mitso` | МИТСО | Международный университет «МИТСО» | Минск | private | university | not found / unavailable | `needs_research` | 2026-07-12 |
| `imb` | МИУП | Международный институт управления и предпринимательства | Минск | private | institute | [yes](https://www.imb.by/admission-comission/) | `reference_only` | 2026-07-12 |

## Data availability

| Data type | Available | Partial | Not found | Unknown |
|---|---:|---:|---:|---:|
| Program catalog | 21 | 0 | 14 | 12 |
| Admission plan | 9 | 0 | 26 | 12 |
| Current applications | 10 | 0 | 25 | 12 |
| Score distribution | 1 | 0 | 34 | 12 |
| Historical cutoffs | 8 | 0 | 27 | 12 |
| Tuition | 21 | 0 | 14 | 12 |
| Scholarships | 11 | 0 | 24 | 12 |
| Dormitories | 18 | 0 | 17 | 12 |
| Official media | 33 | 0 | 2 | 12 |

Current applications and score distributions are the scarcest structured applicant-facing data. General program, tuition, dormitory, and news information is much more common. `unknown` is concentrated among sites that returned TLS, DNS, timeout, 403, or 503 errors during this check.

## Monitoring candidates

BSEU is the only institution marked `online`; its existing monitor uses the official public XML. The following are **candidates only** because a public official “course of document acceptance” page opened. A dedicated technical audit must still verify DOM stability, update cadence, completeness, and rate limits:

- `vsavm` — ВГАВМ: [official current-applications page](https://www.vsavm.by/priemnaya-komissiya/); preliminary format `html`.
- `gsmu` — ГомГМУ: [official current-applications page](https://gsmu.by/applicants/informatsiya-o-khode-priyema-dokumentov/); preliminary format `html`.
- `gstu` — ГГТУ: [official current-applications page](https://abiturient.gstu.by/course-of-documents-acceptance); preliminary format `html`.
- `mspu` — МГПУ: [official current-applications page](https://mspu.by/index.php/home/8051-rezultaty-vstupitelnykh-ispytanijq); preliminary format `html`.
- `grsmu` — ГрГМУ: [official current-applications page](http://grsmu.by/ru/entrants/inf_priem/); preliminary format `html`.
- `bsmu` — БГМУ: [official current-applications page](https://www.bsmu.by/pk/); preliminary format `html`.
- `bspu` — БГПУ: [official current-applications page](https://abiturient.bspu.by/formk1?id=31); preliminary format `html`.
- `varb` — Военная академия: [official current-applications page](https://varb.mil.by/conditions/priem/); preliminary format `html`.
- `bteu` — БТЭУ: [official current-applications page](https://abiturient.bteu.by/priyomnaya-kampaniya/informatsiya-o-hode-priyoma/); preliminary format `html`.

## Review items

- **Филиал Российского государственного социального университета в г. Минске** — `needs_review`. Officially listed as a licensed branch of a Russian institution, not a standalone Belarusian UVO. Recommendation: Keep outside the core universities array; model as a branch in a later milestone. Sources: [source 1](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/filialy-uchrezhdeniy/index.php), [source 2](https://rgsu.by).
- **Минский филиал Российского экономического университета имени Г.В. Плеханова** — `needs_review`. Officially listed as a licensed branch of a Russian institution, not a standalone Belarusian UVO. Recommendation: Keep outside the core universities array; model as a branch in a later milestone. Sources: [source 1](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/filialy-uchrezhdeniy/index.php), [source 2](https://reu.by).
- **Минский государственный лингвистический университет** — `renamed`. Older name; the current Ministry registry uses «Белорусский государственный университет иностранных языков». Recommendation: Use BSUFL/BГУИЯ as canonical and retain the former name only as an alias after a dedicated history check. Sources: [source 1](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/g-minsk/index.php), [source 2](https://bsufl.by/).
- **Могилевский государственный университет продовольствия** — `renamed`. Older name; the current Ministry registry uses «Белорусский государственный университет пищевых и химических технологий». Recommendation: Use BGUT as canonical and retain the former name only as an alias after a dedicated history check. Sources: [source 1](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/mogilev-i-mogilevskaya-oblast/index.php), [source 2](https://bgut.by/).
- **Полоцкий государственный университет** — `renamed`. Shorter historical name; the current Ministry registry includes the dedication «имени Евфросинии Полоцкой». Recommendation: Use the full current registry name; treat the shorter form as an alias. Sources: [source 1](https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/vitebsk-i-vitebskaya-oblast/index.php), [source 2](https://psu.by/).

## Known limitations

- Official sites not successfully opened in this environment (12): `bstu`, `psu`, `bsut`, `gsu`, `mi-mvd`, `msu`, `amia`, `bsatu`, `buk`, `bsac`, `ucp`, `mitso`. The institutions remain confirmed by the Ministry registry.
- No stable official admissions URL was confirmed for 14 records: `bstu`, `psu`, `bsut`, `gsu`, `baa`, `mi-mvd`, `msu`, `bsu`, `amia`, `bsatu`, `buk`, `bsac`, `ucp`, `mitso`.
- The audit is surface-level. PDFs were not parsed, JavaScript applications were not reverse-engineered, and no authenticated paths were tested.
- HTTP 200 confirms availability at check time, not future stability or parser suitability.
- Registry pages expose no visible publication date; `checked_at` records the audit time instead.
- Historical aliases in `review_items` require a dedicated legal/history check before becoming searchable aliases in production.

## Recommended next research milestone

Deeply audit the following six institutions, excluding already-connected BSEU:

1. **BSU (`bsu`)** — highest general-interest value; the main official site opened, but a stable admissions hub was not confirmed, making source discovery itself important.
2. **BNTU (`bntu`)** — major technical institution with an official reception portal; useful for testing a large, multi-faculty source.
3. **BSUIR (`bsuir`)** — high-value IT audience and a confirmed official admissions section; useful for comparing modern site structure with BSEU.
4. **BSMU (`bsmu`)** — official current-application HTML opened; adds the medical admissions workflow.
5. **GSTU (`gstu`)** — official dedicated applicant subdomain and current-application page; adds Gomel and a technical regional source.
6. **VSAVM (`vsavm`)** — official current-application page plus admission-plan/history links; adds Vitebsk and an agricultural academy profile.

The next milestone should inspect only these sources in depth, record raw formats and update behavior, and decide adapter feasibility without yet implementing production adapters.
