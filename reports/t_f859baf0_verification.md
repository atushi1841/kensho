# Japan Event & Festival Data Scraper — Feasibility & Market Report
**Task**: t_f859baf0 | **Date**: 2026-10-02 | **Assignee**: kensho-worker

---

## Executive Summary
**Technically feasible but with significant source gaps.** The existing 10times Events Scraper provides 22 Japan events per run (B2B tradeshows/conferences) but **misses the core target data**: matsuri (traditional festivals), local concerts, art exhibitions, community events, seasonal festivals, and ticket availability. No existing Apify actor covers Japanese consumer event platforms (eplus, pia, Lawson Ticket, Walkerplus, local tourism boards). This is a **greenfield scraper opportunity** requiring multi-source Japanese platform integration.

---

## Existing Apify Landscape (Store Search Results)

| Actor | Users | Runs | Focus | Pricing |
|-------|-------|------|-------|---------|
| `zen-studio/10times-events-scraper` | 360 | 19,998 | Global trade shows/conferences, 59 fields/event | Pay-per-event ($0.0035/item) |
| `runtime/10times` | 54 | 1,013 | 10times trade shows | Per-event |
| `ardent_fork/peatix-events` | 3 | 34 | Peatix events | — |
| `khadinakbar/eventbrite-events-scraper` | 18 | 927 | Eventbrite tickets/venues | — |
| `crawlerbros/tentimes-events-scraper` | 25 | 442 | 10times clone | — |

**Gap**: No actor covers **Japanese consumer event platforms** (eplus, pia, l-tike, Walkerplus, local tourism boards). 10times returns only 22 B2B events/run for Japan — zero matsuri, zero concerts, zero local exhibitions.

---

## 10times Japan Run Analysis (Live Test)

**Input**: `{"country": "JP", "maxItems": 100}`
**Output**: 22 events — all B2B tradeshows/conferences/workshops

| Event | Type | Date | City | Categories |
|-------|------|------|------|------------|
| Beyond Beauty Tokyo | Tradeshow | 2026-09-30 | Koto | Wellness, Fashion |
| Tokyo Pack | Tradeshow | 2026-10-14 | Koto | Packaging |
| Anti-Aging Japan | Workshop | 2026-09-30 | Koto | Wellness, Fashion |
| Cosme Week Osaka | Tradeshow | 2026-09-30 | Osaka | Fashion |
| Japan Intl Machine Tool Fair | Tradeshow | 2026-10-26 | Koto | Industrial Eng |
| Anime Japan | Tradeshow | 2026-03-28 | Koto | Entertainment |
| Kyushu/Okinawa Tourism Expo | Tradeshow | 2026-10-28 | Fukuoka | Hospitality, Travel |

**Missing entirely**: matsuri, concerts, art exhibitions, seasonal festivals, community events, ticket data.

---

## Target Japanese Platforms (Greenfield)

| Platform | Type | Coverage | Notes |
|----------|------|----------|-------|
| **eplus.jp** | Ticketing | Concerts, theater, sports, events | Major player, requires session handling |
| **pia.jp** | Ticketing | Concerts, events, movies | Largest Japan ticketing, complex JS |
| **l-tike.com** | Ticketing | Lawson Ticket, concerts, events | Convenience store chain backed |
| **cnplayguide.com** | Ticketing | Concerts, theater | Playguide group |
| **Walkerplus** | Event listings | Local events, festivals, concerts | Kadokawa-owned, rich metadata |
| **Tokyo Calendar** | Event listings | Tokyo events, dining, culture | Premium listings |
| **Prefecture tourism sites** | Official calendars | Matsuri, seasonal events | 47 prefectures + major cities |
| **Japan Tourism Agency** | Official data | National events, festivals | data.go.jp open data |
| **Local city websites** | Official calendars | Community matsuri, fireworks | Hundreds of sources |

---

## Technical Architecture Recommendation

### Data Sources (Tier 1 — Priority)
1. **eplus.jp** — Concerts, theater, events (primary ticket source)
2. **Walkerplus** — Event listings with rich metadata (dates, venues, categories)
2. **pia.jp / l-tike.com** — Secondary ticket validation
3. **Prefecture/city official calendars** — Matsuri, seasonal festivals (public data)
4. **Japan Tourism Agency (data.go.jp)** — National event open data

### Collection Strategy
| Layer | Approach | Frequency | Est. Cost |
|-------|----------|-----------|-----------|
| **Ticket platforms** | Playwright + API reverse-engineering | Daily | ~$200-500/mo (proxies, compute) |
| **Listing sites** | HTTP + scrapling (JS rendering) | 6-hourly | ~$100/mo |
| **Official calendars** | HTTP + RSS/ICS parsing | Daily | Free (public data) |
| **Deduplication/merge** | Post-processing pipeline | After each collection | Compute only |

### Actor Design: "Japan Event & Festival Intelligence"
**Input Schema**:
```json
{
  "prefectures": ["Tokyo", "Osaka", "Kyoto", "Hokkaido", "Fukuoka", "all"],
  "event_types": ["matsuri", "concert", "exhibition", "theater", "sports", "fireworks", "all"],
  "date_from": "2026-10-01",
  "date_to": "2026-12-31",
  "include_tickets": true,
  "output_format": "jsonl"
}
```

**Output Schema** (per event):
- `event_id`, `title`, `event_type` (matsuri/concert/exhibition/theater/sports/fireworks/other)
- `prefecture`, `city`, `venue_name`, `venue_address`, `coordinates`
- `start_date`, `end_date`, `recurring_pattern` (annual/one-time)
- `description`, `organizer`, `official_url`
- `ticket_info`: `price_range_jpy`, `ticket_url`, `on_sale_date`, `status` (on_sale/sold_out/upcoming)
- `categories`: list of category tags
- `expected_attendance`, `historical_attendance`
- `source_urls`, `collected_at`

---

## Pricing Strategy

| Model | Price | Rationale |
|-------|-------|-----------|
| **Pay-per-event** (dataset row) | **$0.008/row** | High-value consumer event data; ticket URLs = commercial value |
| **Actor Start** | $0.00005 | Standard |
| **Subscription (MCP)** | $25/mo | AI agent access to event API for travel/concert apps |
| **Bulk dataset (Gumroad)** | $49-199 | Full seasonal dataset exports |

**Competitive positioning**: 4-8× 10times pricing justified by consumer event coverage + ticket data.

---

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Ticket site anti-bot (Cloudflare, CAPTCHA) | High | Playwright with residential proxies; session persistence; human-like delays |
| JS-heavy sites (SPA) | High | scrapling / Playwright with network interception |
| TOS / legal (ticket scalping perception) | Medium | Explicitly no purchase automation; only public listing data; respect robots.txt |
| Site structure changes | High | Selector abstraction layer; monitoring alerts; fallback selectors |
| Data volume (100s events/day) | Medium | Incremental collection; deduplication by event_id + date + venue |
| Seasonal spikes (Golden Week, Obon) | High | Adaptive scheduling; priority queues |

---

## Recommended Next Steps (Child Tasks)

1. **Spec & Pricing Card** — Finalize schema, pricing, target prefectures
2. **eplus.jp Collector** — Reverse-engineer API/GraphQL; Playwright scraper prototype
3. **Walkerplus Collector** — HTTP + scrapling for event listings
4. **Official Calendar Collector** — 47 prefecture + major city RSS/ICS/HTML parsers
5. **pia/l-tike Validation Module** — Spot-check ticket availability
6. **Deduplication & Merge Engine** — Multi-source event_id normalization
7. **Apify Actor Package** — Docker, .actor/actor.json, schemas, pricing
8. **Store Listing** — SEO, example runs, categories, pricing tiers
9. **MCP Server Wrapper** — AI agent consumption mode

---

## Verification Checklist

- [x] Store search confirms no Japan consumer event actor exists
- [x] 10times tested: returns only 22 B2B events for Japan (no matsuri/concerts/exhibitions)
- [x] Target platforms identified: eplus, pia, l-tike, Walkerplus, official calendars
- [x] Technical approach defined (Playwright + scrapling + HTTP)
- [x] Pricing model defined ($0.008/row pay-per-event)
- [ ] Legal review: TOS of eplus/pia/Walkerplus (public listing data)
- [ ] Prototype: collect 1 week of Tokyo events from eplus + Walkerplus
- [ ] Unit tests for deduplication engine
- [ ] Anti-bot bypass validation (Cloudflare challenge handling)

---

## Appendix: Key URLs

- 10times Japan test: `{"country": "JP", "maxItems": 100}` → 22 events
- eplus.jp: https://eplus.jp
- pia.jp: https://pia.jp
- l-tike.com: https://l-tike.com
- Walkerplus: https://walkerplus.com
- Japan Tourism Agency open data: https://data.go.jp
- Prefecture event calendars: e.g. https://www.metro.tokyo.lg.jp (Tokyo), https://www.city.osaka.lg.jp (Osaka)

---

## verification_evidence

```
# 10times Japan live test
$ python3 /home/atushi/.hermes/profiles/kensho-worker/cache/scratch/run_jp_country.py
RUN: gkzIFALewO0lEmYD2
status: SUCCEEDED
COUNT: 22
types: {'Tradeshow': 13, 'Conference': 7, 'Workshop': 2}
top cats: [(107, 7), (34, 6), (125, 4), (160, 2), (50, 2), (27, 2), (61, 2), (108, 1), (1443, 1), (158, 1)]

# All 22 events are B2B tradeshows/conferences/workshops
# Zero matsuri, zero concerts, zero local exhibitions, zero ticket data

# Apify Store search confirmation
$ python3 /home/atushi/.hermes/profiles/kensho-worker/cache/scratch/store_search2.py
# No actors for: "japan festival", "japan concert", "japan exhibition", 
# "matsuri", "japan ticket", "japan event calendar", "festival japan"
# Only 10times (global B2B) and Peatix/Eventbrite (no Japan runs)
```