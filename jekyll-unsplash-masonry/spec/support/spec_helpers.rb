# frozen_string_literal: true

module SpecHelpers
  IDS = %w(BPWZ01FtySg EQB0hDo3nds E64t6WGW0Go B7dPXzAflys EdulVUlf0Xc _qL-OGpBOds R2HN5uZYtHM HNhsAZge4BU).freeze

  def build_site(dir, unsplash = {})
    File.write(File.join(dir, "_config.yml"), "") unless File.exist?(File.join(dir, "_config.yml"))
    config = Jekyll.configuration(
      "source" => dir, "destination" => File.join(dir, "_site"), "quiet" => true,
      "unsplash_masonry" => { "app_name" => "my-app", "api_url" => @api.url }.merge(unsplash)
    )
    Jekyll::Site.new(config)
  end

  def render(template, site, page_path: "page.md")
    Liquid::Template.parse(template).render!({}, registers: { site: site, page: { "path" => page_path } })
  end

  def with_key(value = "test-key")
    allow(ENV).to receive(:[]).and_call_original
    allow(ENV).to receive(:[]).with("UNSPLASH_ACCESS_KEY").and_return(value)
  end

  def grid_block(ids)
    "{% unsplash_grid %}\n#{ids.map { |i| "https://unsplash.com/photos/#{i}" }.join("\n")}\n{% endunsplash_grid %}"
  end
end
