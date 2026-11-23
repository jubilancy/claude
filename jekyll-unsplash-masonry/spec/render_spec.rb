# frozen_string_literal: true

RSpec.describe "unsplash_grid rendering" do
  around do |example|
    @api = FakeUnsplash.new
    Dir.mktmpdir { |dir| @dir = dir; example.run }
    @api.stop
  end

  before { with_key("secret-test-key") }

  let(:site) { build_site(@dir) }

  it "renders the 8 photos from a block as a grid" do
    html = render(grid_block(SpecHelpers::IDS), site)
    expect(html.scan("<figure").size).to eq(8)
    expect(html).to include('class="unsplash-masonry"')
    expect(html).to include("--um-cols:3;--um-cols-md:2;--um-cols-sm:1")
    expect(html).to include("column-count") # inline CSS
    expect(html).not_to match(/\n\s*\n/)    # no blank lines, so Markdown leaves it alone
  end

  it "hotlinks urls.regular exactly as returned, with dimensions, lazy loading and the color placeholder" do
    html = render(grid_block(%w(BPWZ01FtySg)), site)
    regular = FakeUnsplash.photo("BPWZ01FtySg")["urls"]["regular"]
    expect(html).to include(%(src="#{CGI.escapeHTML(regular)}"))
    expect(html).to include('width="4000" height="6000"')
    expect(html).to include('loading="lazy" decoding="async"')
    expect(html).to include('style="background-color:#262626"')
  end

  it "builds srcset from urls.raw and keeps ixid on every URL" do
    html = render(grid_block(%w(BPWZ01FtySg)), site)
    srcset = html[/srcset="([^"]+)"/, 1]
    entries = CGI.unescapeHTML(srcset).split(", ")
    expect(entries.size).to eq(4)
    expect(entries).to all(include("ixid=IXBPWZ01FtySg"))
    expect(entries.first).to end_with("&w=400 400w")
  end

  it "uses urls.small for size=small and can turn srcset off" do
    html = render(%({% unsplash_grid ids="BPWZ01FtySg" size="small" srcset="false" %}), site)
    expect(html).to include("&amp;w=400\"")
    expect(html).not_to include("srcset=")
  end

  it "credits the photographer and Unsplash with utm params, from the API response" do
    html = render(grid_block(%w(BPWZ01FtySg)), site)
    expect(html).to include('Photo by <a href="https://unsplash.com/@jane?utm_source=my-app&amp;utm_medium=referral">Jane &lt;Doe&gt;</a>')
    expect(html).to include('on <a href="https://unsplash.com/?utm_source=my-app&amp;utm_medium=referral">Unsplash</a>')
  end

  it "falls back from alt_description to description to 'Photo by <name> on Unsplash'" do
    @api.overrides = {
      "BPWZ01FtySg" => { "alt_description" => nil, "description" => nil },
      "EQB0hDo3nds" => { "alt_description" => nil, "description" => "A  described\nphoto" }
    }
    html = render(%({% unsplash_grid ids="BPWZ01FtySg,EQB0hDo3nds,E64t6WGW0Go" %}), site)
    expect(html).to include('alt="Photo by Jane &lt;Doe&gt; on Unsplash"')
    expect(html).to include('alt="A described photo"')
    expect(html).to include('alt="a test photo E64t6WGW0Go"')
  end

  it "never writes the API key into the HTML and sends the documented headers" do
    html = render(grid_block(%w(BPWZ01FtySg)), site)
    expect(html).not_to include("secret-test-key")
    req = @api.photo_requests.first
    expect(req[:auth]).to eq("Client-ID secret-test-key")
    expect(req[:version]).to eq("v1")
  end

  it "applies columns, gap, class and the config defaults, with tag options winning" do
    site = build_site(@dir, "columns" => 4, "gap" => "8px", "class" => "from-config")
    html = render(%({% unsplash_grid ids="BPWZ01FtySg" columns="2" class="wide" %}), site)
    expect(html).to include('class="unsplash-masonry wide"')
    expect(html).to include("--um-cols:2;--um-cols-md:2;--um-cols-sm:1;--um-gap:8px")
  end

  it "reads ids= and data= sources and de-duplicates" do
    site.data["art"] = ["https://unsplash.com/photos/EQB0hDo3nds", { "id" => "E64t6WGW0Go" }, "BPWZ01FtySg"]
    html = render(%({% unsplash_grid ids="BPWZ01FtySg,https://unsplash.com/photos/x-HNhsAZge4BU" data="art" %}), site)
    expect(html.scan("<figure").size).to eq(4)
  end

  it "warns on unparseable lines instead of crashing" do
    expect(Jekyll.logger).to receive(:warn).with("UnsplashMasonry:", /page\.md: can't read a photo ID from "junk"/)
    html = render("{% unsplash_grid %}\njunk\nhttps://unsplash.com/photos/BPWZ01FtySg\n{% endunsplash_grid %}", site)
    expect(html.scan("<figure").size).to eq(1)
  end

  it "emits the CSS once per document and adds the lightbox only when asked" do
    html = render(%({% unsplash_grid ids="BPWZ01FtySg" lightbox="true" %}\n{% unsplash_grid ids="EQB0hDo3nds" lightbox="true" %}), site)
    expect(html.scan("<style>").size).to eq(1)
    expect(html.scan("<script>").size).to eq(1)
    expect(html).to include("<dialog").or include("createElement('dialog')")
    expect(html).to include("data-um-large=")
    expect(render(%({% unsplash_grid ids="BPWZ01FtySg" %}), build_site(@dir))).not_to include("<script>")
  end

  it "fails with a clear message when no photos are given" do
    expect { render(%({% unsplash_grid ids="" %}), site) }.to raise_error(Jekyll::UnsplashMasonry::Error, /no photos given/)
  end

  it "needs an end tag only for the body form" do
    expect { Liquid::Template.parse("{% unsplash_grid %}\nBPWZ01FtySg") }.to raise_error(Liquid::SyntaxError, /endunsplash_grid/)
    expect { Liquid::Template.parse(%({% unsplash_grid ids="BPWZ01FtySg" %}{% endunsplash_grid %})) }.not_to raise_error
  end
end
