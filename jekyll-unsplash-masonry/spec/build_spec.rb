# frozen_string_literal: true

RSpec.describe "jekyll build" do
  around do |example|
    @api = FakeUnsplash.new
    Dir.mktmpdir { |dir| @dir = dir; example.run }
    @api.stop
  end

  before do
    with_key
    File.write(File.join(@dir, "index.md"), <<~MD)
      ---
      title: Test
      ---
      # Gallery

      #{grid_block(SpecHelpers::IDS)}

      After the grid.
    MD
  end

  def build
    site = build_site(@dir)
    site.process
    File.read(File.join(@dir, "_site", "index.html"))
  end

  it "renders 8 photos through Markdown, then a second build makes zero API requests" do
    html = build
    expect(html.scan("<figure class=\"unsplash-masonry__item\">").size).to eq(8)
    expect(html).not_to include("<pre>") # Markdown did not turn the HTML into a code block
    expect(html).to include("<p>After the grid.</p>")
    expect(@api.photo_requests.size).to eq(8)

    build
    expect(@api.photo_requests.size).to eq(8)
  end
end
