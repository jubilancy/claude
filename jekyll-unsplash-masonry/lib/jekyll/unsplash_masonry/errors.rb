# frozen_string_literal: true

module Jekyll
  module UnsplashMasonry
    # Raised for problems that must fail the build (missing key, bad key, no usable source).
    class Error < StandardError; end
  end
end
