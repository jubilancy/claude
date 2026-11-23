# frozen_string_literal: true

require "set"

module Jekyll
  module UnsplashMasonry
    # Per-build state, shared by every tag in the site: rate-limit flag, memoised photos, counters.
    module State
      module_function

      def reset!
        @rate_limited = false
        @photos = {}
        @requests = 0
        @from_cache = Set.new
        @fetched = Set.new
        @skipped_no_data = []
        @skipped_stale = []
        @warned_no_key = false
        @warned_app = false
      end

      def app_name_warned?
        @warned_app
      end

      def app_name_warned!
        @warned_app = true
      end

      def rate_limited?
        @rate_limited
      end

      def rate_limited!
        @rate_limited = true
      end

      def photos
        @photos ||= {}
      end

      def request_made!
        @requests = requests + 1
      end

      def requests
        @requests ||= 0
      end

      def fetched
        @fetched ||= Set.new
      end

      def from_cache
        @from_cache ||= Set.new
      end

      def skipped_no_data
        @skipped_no_data ||= []
      end

      def skipped_stale
        @skipped_stale ||= []
      end

      def no_key_warned?
        @warned_no_key
      end

      def no_key_warned!
        @warned_no_key = true
      end

      # Printed once per build, after the site is written.
      def report!
        used = fetched.size + from_cache.size
        if used.positive? || requests.positive?
          Jekyll.logger.info("UnsplashMasonry:",
                             "#{used} photo(s): #{from_cache.size} from cache, #{fetched.size} fetched, " \
                             "#{requests} API request(s)")
        end
        return if skipped_no_data.empty? && skipped_stale.empty?

        parts = []
        parts << "not rendered (no cache): #{skipped_no_data.uniq.join(', ')}" unless skipped_no_data.empty?
        parts << "rendered from stale cache, not refreshed: #{skipped_stale.uniq.join(', ')}" unless skipped_stale.empty?
        Jekyll.logger.warn("UnsplashMasonry:",
                           "Unsplash rate limit reached (X-Ratelimit-Remaining: 0), requests skipped for " \
                           "#{parts.join('; ')}. Rebuild after the hourly limit resets.")
      end
    end
  end
end
