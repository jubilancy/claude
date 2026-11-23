# frozen_string_literal: true

RSpec.describe "unsplash_grid caching and rate limits" do
  around do |example|
    @api = FakeUnsplash.new
    Dir.mktmpdir { |dir| @dir = dir; example.run }
    @api.stop
  end

  let(:ids) { SpecHelpers::IDS.first(3) }
  let(:template) { grid_block(ids) }
  let(:cache_dir) { File.join(@dir, ".jekyll-cache", "unsplash") }

  before { with_key }

  it "fetches each photo once, writes <id>.json, and makes zero requests on the next build" do
    render(template, build_site(@dir))
    expect(@api.photo_requests.size).to eq(3)
    expect(Dir[File.join(cache_dir, "*.json")].map { |f| File.basename(f, ".json") }).to match_array(ids)

    Jekyll::UnsplashMasonry::State.reset!
    html = render(template, build_site(@dir))
    expect(@api.photo_requests.size).to eq(3)
    expect(html.scan("<figure").size).to eq(3)
  end

  it "fetches a repeated ID only once within a build" do
    render("#{template}\n#{template}", build_site(@dir))
    expect(@api.photo_requests.size).to eq(3)
  end

  it "re-requests only photos whose cache is older than the TTL" do
    render(template, build_site(@dir))
    old = Time.now - (31 * 86_400)
    File.utime(old, old, File.join(cache_dir, "#{ids.first}.json"))

    Jekyll::UnsplashMasonry::State.reset!
    render(template, build_site(@dir))
    expect(@api.photo_requests.size).to eq(4)
    expect(@api.photo_requests.last[:path]).to end_with(ids.first)
  end

  it "honours cache_ttl_days" do
    render(template, build_site(@dir, "cache_ttl_days" => 1))
    old = Time.now - (2 * 86_400)
    ids.each { |i| File.utime(old, old, File.join(cache_dir, "#{i}.json")) }
    Jekyll::UnsplashMasonry::State.reset!
    render(template, build_site(@dir, "cache_ttl_days" => 1))
    expect(@api.photo_requests.size).to eq(6)
  end

  it "refreshes cached photos with refresh=true" do
    render(template, build_site(@dir))
    Jekyll::UnsplashMasonry::State.reset!
    render(%({% unsplash_grid ids="#{ids.first}" refresh="true" %}), build_site(@dir))
    expect(@api.photo_requests.size).to eq(4)
  end

  it "fails with a clear message when the key is missing and there is no cache" do
    with_key(nil)
    expect { render(template, build_site(@dir)) }
      .to raise_error(Jekyll::UnsplashMasonry::Error, /UNSPLASH_ACCESS_KEY is not set and photo #{ids.first} is not in the cache/)
    expect(@api.requests).to be_empty
  end

  it "renders from the cache without a key" do
    render(template, build_site(@dir))
    with_key(nil)
    Jekyll::UnsplashMasonry::State.reset!
    expect(render(template, build_site(@dir)).scan("<figure").size).to eq(3)
  end

  it "stops at the first rate-limit response, renders cached photos and warns once with the skipped IDs" do
    render(grid_block(ids.first(1)), build_site(@dir)) # cache the first photo only
    Jekyll::UnsplashMasonry::State.reset!
    @api.limit_after = @api.requests.size # next request gets 403 / X-Ratelimit-Remaining: 0

    warnings = []
    allow(Jekyll.logger).to receive(:warn) { |_p, msg| warnings << msg }
    allow(Jekyll.logger).to receive(:info)
    html = render(grid_block(SpecHelpers::IDS.first(5)), build_site(@dir, "refresh" => true))
    Jekyll::UnsplashMasonry::State.report!

    expect(html.scan("<figure").size).to eq(1) # only the cached photo
    expect(@api.photo_requests.size).to eq(2)  # one real fetch of photo 1 earlier + exactly one refused request
    expect(warnings.size).to eq(1)
    expect(warnings.first).to include("rate limit")
    expect(warnings.first).to include(SpecHelpers::IDS[1], SpecHelpers::IDS[4])
  end

  it "skips a 404 photo with a warning and keeps the rest" do
    @api.missing = [ids[1]]
    expect(Jekyll.logger).to receive(:warn).with("UnsplashMasonry:", /#{ids[1]}: HTTP 404/)
    html = render(template, build_site(@dir))
    expect(html.scan("<figure").size).to eq(2)
  end

  it "only calls download_location when download_tracking is on" do
    render(template, build_site(@dir))
    expect(@api.requests.map { |r| r[:path] }.grep(/DOWNLOAD/)).to be_empty
  end

  it "calls download_location once per photo when download_tracking is enabled" do
    ids.each { |i| @api.overrides[i] = { "links" => { "download_location" => "#{@api.url}/photos/#{i}/download" } } }
    render(template, build_site(@dir, "download_tracking" => true))
    downloads = @api.requests.map { |r| r[:path] }.grep(%r{/download\z})
    expect(downloads.size).to eq(3)

    Jekyll::UnsplashMasonry::State.reset!
    render(template, build_site(@dir, "download_tracking" => true))
    expect(@api.requests.map { |r| r[:path] }.grep(%r{/download\z}).size).to eq(3)
  end
end
