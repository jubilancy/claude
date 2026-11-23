# frozen_string_literal: true

require_relative "lib/jekyll/unsplash_masonry/version"

Gem::Specification.new do |spec|
  spec.name          = "jekyll-unsplash-masonry"
  spec.version       = Jekyll::UnsplashMasonry::VERSION
  spec.authors       = ["jubilancy"]
  spec.summary       = "Masonry photo grid for Jekyll, built from the Unsplash API at build time."
  spec.description   = "A Liquid tag that renders a pure-CSS masonry grid of hotlinked Unsplash photos " \
                       "with the required credits. Photo JSON is cached on disk; the API key is only used at build time."
  spec.homepage      = "https://github.com/jubilancy/claude/tree/main/jekyll-unsplash-masonry"
  spec.license       = "MIT"
  spec.required_ruby_version = ">= 3.0"

  spec.files         = Dir["lib/**/*.rb", "README.md", "LICENSE"]
  spec.require_paths = ["lib"]

  spec.add_dependency "jekyll", ">= 4.0", "< 5.0"

  spec.add_development_dependency "rspec", "~> 3.12"
  spec.add_development_dependency "webrick", "~> 1.8"
end
