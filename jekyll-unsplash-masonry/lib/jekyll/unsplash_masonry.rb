# frozen_string_literal: true

require "jekyll"
require "liquid"
require_relative "unsplash_masonry/version"
require_relative "unsplash_masonry/errors"
require_relative "unsplash_masonry/options"
require_relative "unsplash_masonry/parser"
require_relative "unsplash_masonry/cache"
require_relative "unsplash_masonry/client"
require_relative "unsplash_masonry/state"
require_relative "unsplash_masonry/resolver"
require_relative "unsplash_masonry/renderer"
require_relative "unsplash_masonry/tag"

Liquid::Template.register_tag("unsplash_grid", Jekyll::UnsplashMasonry::Tag)
Liquid::Template.register_tag("endunsplash_grid", Jekyll::UnsplashMasonry::EndTag)

Jekyll::Hooks.register :site, :after_reset do |_site|
  Jekyll::UnsplashMasonry::State.reset!
end

Jekyll::Hooks.register :site, :post_write do |_site|
  Jekyll::UnsplashMasonry::State.report!
end
