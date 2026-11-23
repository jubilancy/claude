# frozen_string_literal: true

require "tmpdir"
require "jekyll-unsplash-masonry"
Dir[File.join(__dir__, "support", "*.rb")].sort.each { |f| require f }

Jekyll.logger.log_level = :error

RSpec.configure do |config|
  config.include SpecHelpers
  config.before { Jekyll::UnsplashMasonry::State.reset! }
  config.expect_with(:rspec) { |c| c.syntax = :expect }
end
