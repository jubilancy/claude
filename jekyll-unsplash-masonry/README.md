# jekyll-unsplash-masonry

A Liquid tag that turns Unsplash photo URLs into a responsive, pure-CSS masonry grid with the credits Unsplash requires.

- Photo data comes from the [Unsplash API](https://unsplash.com/documentation) **at build time only**. The key never reaches the HTML and no browser JavaScript calls the API.
- Each photo's JSON is cached in `.jekyll-cache/unsplash/<id>.json`. A cached photo is never requested again until its TTL expires, so a second build makes zero API requests.
- Images are [hotlinked](https://unsplash.com/documentation#hotlinking) from `urls.*`, never downloaded or self-hosted.
- Ruby standard library only (`net/http`, `json`). Jekyll 4.x, Ruby 3.x.

## Install

This repo uses it through a path gem. In the site's `Gemfile`:

```ruby
gem "jekyll-unsplash-masonry", path: "./jekyll-unsplash-masonry"
```

In `_config.yml`:

```yaml
plugins:
  - jekyll-unsplash-masonry

unsplash_masonry:
  app_name: "your-unsplash-app-name"   # required for the credit links, see below
```

Then `bundle install`.

### API key

Create an app at [unsplash.com/oauth/applications](https://unsplash.com/oauth/applications) and export its **Access Key**:

```bash
export UNSPLASH_ACCESS_KEY=your_access_key
bundle exec jekyll build
```

In a cloud session, add `UNSPLASH_ACCESS_KEY` in the environment's settings. On GitHub, add it as a repository secret (see [GitHub Pages](#github-pages)). The key is sent as `Authorization: Client-ID <key>` with `Accept-Version: v1`. If the key is missing and a photo is not cached, the build fails with a message naming the photo; if every photo is cached, no key is needed.

Demo-mode apps are limited to 50 requests per hour (1000 after production approval), see [Rate limiting](https://unsplash.com/documentation#rate-limiting). Image requests to `images.unsplash.com` do not count.

## Usage

### Photo URLs between the tags

```liquid
{% unsplash_grid %}
https://unsplash.com/photos/BPWZ01FtySg
https://unsplash.com/photos/EQB0hDo3nds
https://unsplash.com/photos/some-title-E64t6WGW0Go
https://unsplash.com/photos/_qL-OGpBOds?utm_source=anything
# lines starting with # are ignored
{% endunsplash_grid %}
```

One URL or ID per line (commas and spaces also separate). The ID is the **last 11 characters** of the `/photos/…` path segment, so slug URLs work, and IDs that start with `_` or contain `-` are fine. Query strings, fragments, a trailing slash and `/download` are ignored. A line that can't be parsed gets a build warning and is skipped. The body is read literally; Liquid inside it is not evaluated.

### `ids`

```liquid
{% unsplash_grid ids="BPWZ01FtySg,EQB0hDo3nds" %}
```

No end tag is needed with `ids` or `data` (an `{% endunsplash_grid %}` after them is accepted and ignored). `ids` accepts URLs as well as IDs.

### Data file

`_data/art.yml`:

```yaml
- https://unsplash.com/photos/BPWZ01FtySg
- id: EQB0hDo3nds
- url: https://unsplash.com/photos/some-title-E64t6WGW0Go
```

```liquid
{% unsplash_grid data="art" %}
```

Entries can be URLs, IDs, or hashes with `id` or `url`. `data="gallery.travel"` reads a nested key. `ids`, `data` and the tag body can be combined; duplicates are removed.

### Options

Every option can be set site-wide under `unsplash_masonry:` in `_config.yml` and overridden per tag, for example `{% unsplash_grid data="art" columns=2 size="small" class="my-grid" %}`.

| Option | Default | What it does |
|---|---|---|
| `app_name` | none (falls back to `jekyll-unsplash-masonry` with a warning) | Your Unsplash app name, used as `utm_source` in the credit links. |
| `columns` | `3` | Columns on desktop (1 to 12). Tablet gets `min(columns, 2)`, mobile gets 1. |
| `gap` | `1rem` | Column and row gap. A bare number means px. |
| `size` | `regular` | `regular` uses `urls.regular` as `src`, `small` uses `urls.small`. |
| `class` | none | Extra CSS class(es) on the grid `<div>`. |
| `srcset` | `true` | Add `srcset`/`sizes` built from `urls.raw` with `w=` values. `ixid` stays on every URL. |
| `srcset_widths` | `[400, 800, 1200, 1600]` | The `w=` values for `srcset`. |
| `lightbox` | `false` | Click a photo to open it larger in a native `<dialog>`. Without JavaScript the link opens the image. |
| `inline_css` | `true` | Emit the small `<style>` block (once per page). Turn off to supply your own CSS for the classes below. |
| `cache_dir` | `.jekyll-cache/unsplash` | Where the per-photo JSON lives (relative to the site source). |
| `cache_ttl_days` | `30` | Re-request a photo after this many days. `0` or `false` means never expire. |
| `refresh` | `false` | Ignore the cache and re-request every photo in the tag. Use `{% unsplash_grid ... refresh=true %}` for a one-off. |
| `download_tracking` | `false` | Call each photo's `download_location`. Leave off for a display-only gallery, see below. |
| `api_url` | `https://api.unsplash.com` | Only for tests or a proxy. |

### Markup and CSS

```html
<div class="unsplash-masonry my-class" style="--um-cols:3;--um-cols-md:2;--um-cols-sm:1;--um-gap:1rem">
<figure class="unsplash-masonry__item">
<img class="unsplash-masonry__img" src="…urls.regular…" srcset="…" sizes="…" width="4000" height="6000"
     alt="…" loading="lazy" decoding="async" style="background-color:#262626">
<figcaption class="unsplash-masonry__credit">Photo by <a href="https://unsplash.com/@name?utm_source=app&amp;utm_medium=referral">Name</a> on <a href="https://unsplash.com/?utm_source=app&amp;utm_medium=referral">Unsplash</a></figcaption>
</figure>
…
</div>
```

- Layout is CSS columns (`column-count`, `break-inside: avoid`). Breakpoints: 1024px and up is desktop, 640 to 1023px tablet, below 640px mobile.
- `src` is `urls.regular` (or `small`) exactly as the API returned it, including `ixid`.
- `width`/`height` come from the photo so the layout doesn't shift. `color` is the placeholder background.
- `alt` is `alt_description`, else `description`, else `Photo by <name> on Unsplash`.
- The output has no blank lines, so Markdown pages pass it through untouched.

## Credits (Unsplash requirement)

Under every photo the gem renders "Photo by *name* on Unsplash". The photographer link is `user.links.html` from the API response (never guessed), "Unsplash" links to `https://unsplash.com/`, and both get `?utm_source=<app_name>&utm_medium=referral`. See the [Attribution guideline](https://help.unsplash.com/en/articles/2511315-guideline-attribution). Set `app_name` to the name of your Unsplash app. If a photo has no profile link in the response, the name is shown without a link.

## Download tracking

From the [Triggering a download guideline](https://help.unsplash.com/en/articles/2511258-guideline-triggering-a-download): when your application performs something similar to a download (for example a user choosing the image to include in a blog post or set as a header), you must send a request to the URL in `photo.links.download_location`. Per the [API docs](https://unsplash.com/documentation#track-a-photo-download), that endpoint is for tracking only: it is not for embedding or serving the photo. Views are tracked automatically when you hotlink.

This gem is a **display-only gallery**, so by default (`download_tracking: false`) it never calls `download_location`.

You would need to trigger a download if the site lets someone pick or save a photo as their own, for example a "download" button, a picker that copies an image into content, or a workflow that downloads the file. In that case, do it when the action happens (from your own server-side code, never with the key in browser JavaScript). `download_tracking: true` is a build-time opt-in: it requests `download_location` once per photo (a `<id>.downloaded` marker in the cache prevents repeats). It is only right if building the site counts as the download action for those photos. If unsure, leave it off and read the guideline.

## Caching and rate limits

- Lookup order: fresh cache file, then the API. A hit makes no request.
- Each build ends with one line, for example `8 photo(s): 8 from cache, 0 fetched, 0 API request(s)`.
- If the API answers `403` with `X-Ratelimit-Remaining: 0`, the build stops requesting, renders every photo it has cached (even stale ones), and prints **one** warning listing the IDs that were skipped. Photos with no cache are left out of the grid until a later build.
- A `404` or network error for one photo warns and skips it (a cached copy is used if there is one). A `401` fails the build.
- Commit `.jekyll-cache/unsplash/` or cache it in CI (the workflow below does) so builds don't spend your quota. Delete a file to force that photo to be fetched again.

## GitHub Pages

GitHub Pages' built-in Jekyll build can't run custom plugins, so build with GitHub Actions. This repo includes [`.github/workflows/pages.yml`](../.github/workflows/pages.yml), which runs `bundle exec jekyll build` on pushes to `main`, caches `.jekyll-cache`, and deploys with the official Pages actions.

1. Repository **Settings → Pages → Build and deployment → Source: GitHub Actions** ([GitHub docs](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)).
2. **Settings → Secrets and variables → Actions → New repository secret**, name `UNSPLASH_ACCESS_KEY`, value your Access Key.
3. Push to `main` (or run the workflow manually from the Actions tab).

## Development

```bash
cd jekyll-unsplash-masonry
bundle install
bundle exec rspec
```

The specs start a local fake of the Unsplash API, so they make no real requests and need no key. They cover ID parsing, rendering (credits, `srcset`, alt text, options, data files) and caching (zero requests on a second build, TTL, `refresh`, rate limiting, missing key), plus one full `jekyll build`.

## License

MIT
