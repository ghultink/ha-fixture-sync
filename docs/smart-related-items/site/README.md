# Smartifying the Related-Items End Screen

How an embedding website can use **smart playlists with dynamic filters** to drive what the Blue Billywig player shows in its post-roll "Related items" panel — without ever changing the player config per page.

This document covers:

1. How the Blue Billywig player decides what to show as related items
2. What a "smart playlist with dynamic filters" really is in OVP6 / SAPI
3. The data-source plumbing (QueryString, LocalStorage, JavaScript, Datafeed, PlainText, WidgetProperty)
4. Concrete scenarios — how a host website signals context into the player
5. A working example wired up against the `demo` publication

---

## 1. How the player picks related items

Source: `standardplayer/src/helpers/RelatedClipsHelper.js`.

The helper runs through this priority ladder for each main-roll clip:

| Order | Mode | Trigger |
|---|---|---|
| 1 | `externalItems` | Embedding page called `api.setRelatedItems([...])` / `api.setRelatedClips([...])` |
| 2 | `relatedItemsListId` | The **clip** has any of these fields filled: `relatedItemsListId`, `relateditems`, `gerelateerdeitems`, `relatedcliplist`, `exitscreen`, `exitscreenitems` |
| 3 | `exitscreenItemsListId` | The **playout** has a default `exitscreenItemsListId` configured |
| 4 | `tagSearch` | None of the above — fall back to a weighted search on the clip's `cat` (categories) and title parts |
| 5 | `latestItems` | Last resort — most-recent published items |

Whenever a `cliplistid` is loaded (modes 2 + 3), the player calls

```
GET {publication}/json/search?cliplistid={id}&filterbyusetype=all&limit=15&...
```

The SAPI returns the cliplist metadata. If `allowDatasource === true`, the player does **not** trust the value in `filters.value` — instead it resolves each filter's `datasource` at runtime, then re-runs the search via:

```
GET {publication}/json/search?filterset=[…]&sort=…&limit=…
```

That second call is where the "smartification" happens: the value substituted into the filter is whatever the embedding website has put on the page (URL, localStorage, JS, datafeed, etc.).

---

## 2. Anatomy of a smart playlist

In OVP6 (`app/components/library/playlist/playlist-details-general.component.html`) a playlist is "smart" when:

- `listtype === 'dynamic'`
- `filterType === 'filters'` (the alternative is `'solr'` — raw SOLR query)
- `allowDatasource === 'true'` — enables the **plug icon** next to each filter value in the UI

The stored JSON (`filters`) is an array of **filter groups** (`AND` between groups, `OR` between filters in a group):

```json
{
  "listtype": "dynamic",
  "filterType": "filters",
  "allowDatasource": "true",
  "limit": 15,
  "sort": "published_date desc",
  "filters": [
    {
      "filters": [
        {
          "id": "qstopic",
          "type": "search",           // entity scope: search | mediaclip | project
          "field": "cat",              // OVP field name — mapped server-side to SOLR
          "operator": "containsAnyOf",
          "value": "Formula 1",        // becomes the *fallback* when datasource resolves to empty
          "datasource": {
            "sourceType": "QueryString",
            "sourceValue": "topic",
            "defaultValue": "Formula 1"
          }
        }
      ]
    }
  ]
}
```

### Operators

From `bb-vertical-filter.component.html` + `formatengine/classes/searchrequesthelper.class.php`:

| Operator | Use |
|---|---|
| `contains`, `doesNotContain` | substring on text/string |
| `is`, `isNot` | exact equality |
| `isEmpty`, `isNotEmpty` | presence checks |
| `containsAnyOf`, `containsAllOf`, `doesNotContainAnyOf` | multi-value list fields (`cat`, `_strmulti`, `_txtmulti`) |
| `isBefore`, `isAfter`, `isInTheLast`, `isNotInTheLast` | dates |
| `isSmallerThan`, `isGreaterThan` | numeric |
| `isAnyOf` / `isNoneOf` | facets |

### Common fields worth filtering on

`cat` (multi-value categories), `fulltext`, `title`, `description`, `language`, `published_date`, `length` (duration), `country_string`, plus any custom field you've added to the publication.

---

## 3. Data sources — how the embedding page feeds the filter

From `DataSourceHelper.js` and `bb-data-source-picker.component.ts`. Each filter can have **one** `datasource` object:

```ts
interface BbDataSource {
  sourceType: 'QueryString' | 'LocalStorage' | 'JavaScript'
            | 'PlainText'   | 'DatafeedValue' | 'WidgetProperty';
  sourceValue: string;     // the key / script / "id:column" pair
  defaultValue?: string;   // fallback when the source resolves to empty
}
```

Resolution happens client-side, in the player, just before the `filterset` POST. The plain `value` on the filter is the absolute fallback — used only when there's no datasource or when it resolves to nothing **and** `defaultValue` is also empty.

### QueryString — the cleanest contract

The player merges all `?key=value` pairs on its own embed URL into `joinedRequestParams`. The website appends parameters when it generates the player URL.

```js
// host page
const topic = pageMeta.primaryTopic;       // "Verstappen"
const src   = `https://demo.bbvms.com/p/smart_related_items_demo/c/${clipId}.html?topic=${encodeURIComponent(topic)}`;
```

```json
"datasource": { "sourceType": "QueryString", "sourceValue": "topic", "defaultValue": "Formula 1" }
```

Values that look base64-encoded get auto-decoded — handy for passing JSON blobs.

### LocalStorage — survives across pages and clips

The website (or another player widget) sets a key on the **browser's** localStorage; the data source reads it. Useful for *user-scoped* signals: country, language, segment, favourite team.

```js
localStorage.setItem('bb_user_topic', 'Ferrari');
```

```json
"datasource": { "sourceType": "LocalStorage", "sourceValue": "bb_user_topic", "defaultValue": "Formula 1" }
```

### JavaScript — escape hatch

A snippet evaluated in the player's `Executer` sandbox. Whatever it returns is the filter value. Use for derived signals: reading `<meta>` tags, geolocation buckets, A/B variants, etc.

```js
// sourceValue
(() => {
  const m = document.querySelector('meta[name="article:section"]');
  return m ? m.content : 'Formula 1';
})()
```

### DatafeedValue — server-curated lookup table

Points at a SAPI Datafeed (a small CMS-managed CSV-like table). Useful when categories must be normalised: e.g. the website passes a slug, and a datafeed row maps it to an OVP `cat` value.

```json
"datasource": {
  "sourceType": "DatafeedValue",
  "sourceValue": "1736942394283:topic",
  "defaultValue": "Formula 1"
}
```

The first part is the datafeed id, the second is the column key. The helper supports `condition` columns so different rows can fire based on localStorage state.

### PlainText (with macros)

A literal value, **with macro expansion** before lookup. Macros: `{{querystring.X}}`, `{{localstorage.Y}}`, `{{mediaclip.Z}}`, `{{playout.Q}}`, `{{player.P}}`, `{{asset.A}}`. Great for composite keys, e.g. `country_{{querystring.cc}}`.

### WidgetProperty

Reads a property off an interactivity-editor widget on the page. Niche — usually only used inside interactive videos.

---

## 4. Concrete scenarios

> All scenarios share one principle: **the page knows the editorial context, the player doesn't.** The page's job is to surface that context in a way the smart playlist can consume.

### Scenario A — "More on this topic" (QueryString)

> *News site embeds the player on an article. The article is tagged `Verstappen`. End screen should show only Verstappen videos, falling back to broader F1 when not provided.*

**Setup**

1. Cliplist filter: `cat containsAnyOf "Formula 1"` with `datasource: QueryString:topic` (default `Formula 1`).
2. Playout has `relatedItems: "Show"` and `exitscreenItemsListId: <cliplist-id>`.
3. Article template appends `?topic={{ article.tags[0] }}` to the player URL.

**Result:** different articles produce different end-screen playlists from the **same** playout and the **same** cliplist.

### Scenario B — User-segmented recommendations (LocalStorage)

> *Streaming portal lets the user pick a favourite team. That choice should bias related items everywhere, on any page, until they change it.*

**Setup**

- Portal writes `localStorage.setItem('bb_favourite_team', 'Ferrari')` on profile save.
- Cliplist filter: `cat containsAnyOf` with `datasource: LocalStorage:bb_favourite_team` (default empty so it falls through to a generic group).

**Bonus:** combine with a second filter group that always includes `language is en` (no datasource) — ensures recommendations stay in the user's locale.

### Scenario C — Geo-aware lineup (Datafeed)

> *Same clip is embedded in NL, BE, DE, FR pages. End screen should prefer local-language follow-up videos.*

**Setup**

- Maintain a datafeed `countryToCat`:
  | country (key) | cat (value) |
  |---|---|
  | NL | F1 Nederland |
  | BE | F1 Belgium |
  | DE | F1 Deutschland |
  | FR | F1 France |
- Country column is a `condition` column; rows are filtered against `localStorage.country` set by the website at boot.
- Filter `datasource: DatafeedValue:<feedId>:cat`.

### Scenario D — Programmatic JS (no infra change on the OVP side)

> *Marketing wants to A/B test two related-items strategies on the same campaign page without redeploying the player config.*

**Setup**

- Filter `datasource: JavaScript` with body:

  ```js
  (() => {
    const variant = (window.__abVariant || 'A');
    return variant === 'A' ? 'Editor's Pick' : 'Trending';
  })()
  ```

- A/B tooling sets `window.__abVariant` before the player JS runs.

### Scenario E — "Continue watching" (LocalStorage + recency)

> *Track which clip the viewer just watched and prefer follow-ups in the same mini-series.*

- Player fires `mediaclipdataloaded`; host listens and stores `localStorage.setItem('bb_last_series', clip.series_string)`.
- Cliplist filter group 1: `series_string is` with `datasource: LocalStorage:bb_last_series`, default empty.
- Cliplist filter group 2: `published_date isInTheLast 30 days` — keep the result fresh when group 1 is empty.
- Because groups are AND-ed, when group 1 returns nothing the SOLR query falls back to the broader group via the player's own `mode='append'` recursion.

### Scenario F — Fully bypass the cliplist (`setRelatedItems`)

> *Host wants total control — e.g. it has its own recommendation engine and just wants the player to render the result.*

```js
const api = await getPlayer('myPlayer');     // window.bluebillywig.players[i]
api.setRelatedItems([
  { id: '5927072', type: 'MediaClip', title: '...', deeplink: '...', thumbnail: '...' },
  { id: '5927078', type: 'MediaClip', title: '...', deeplink: '...', thumbnail: '...' },
  // ... up to 15
]);
```

The helper sanity-checks the first item (needs `id`, `type`, `title`, `deeplink`); if it passes, the array is rendered as-is. Otherwise the helper enriches the IDs via a SAPI filterset search so deeplinks, thumbnails and durations are correct.

`setRelatedItems(null)` clears the override and lets the player fall back to its configured cliplist again.

---

## 5. Reference signals on the embedding page

| Signal | How to set | How the cliplist reads it |
|---|---|---|
| URL parameter | `?topic=Verstappen` | `QueryString:topic` |
| Browser-wide preference | `localStorage.setItem('k', v)` | `LocalStorage:k` |
| Lookup table | SAPI Datafeed entity | `DatafeedValue:{id}:{column}` |
| Computed value | n/a — script lives in the cliplist | `JavaScript` |
| Page metadata | `<meta name="article:section" content="F1">` | `JavaScript` reading the meta |
| Direct items list | `player.setRelatedItems([...])` | `externalItems` mode |

---

## 6. Working example — `demo` publication

Already wired up:

| Asset | id | Notes |
|---|---|---|
| Smart playlist | `1778574689889505` | filter: `cat containsAnyOf` ← `QueryString:topic` (default `Formula 1`) |
| Playout | `13550` (label `smart_related_items_demo`) | `relatedItems=Show`, `exitscreenItemsListId=1778574689889505` |
| Source clips | 20 clips tagged `Max Verstappen`, `Ferrari`, `Verstappen`, `F1`, … | published 2024-06-11 |

Embed URL pattern:

```
https://demo.bbvms.com/p/smart_related_items_demo/c/{CLIP_ID}.html?topic={TOPIC}
```

Try changing the topic value to see the related-items panel re-populate after the main video ends:

- `?topic=Verstappen`   → 20 Verstappen-tagged clips
- `?topic=Ferrari`      → same 20 (all of them carry the Ferrari tag too)
- `?topic=Red+Bull`     → same set
- `?topic=NotARealTag`  → falls through to the default `Formula 1`
- *(no `topic` query at all)* → also `Formula 1`

Companion test page: `test-page.html` in this directory.
