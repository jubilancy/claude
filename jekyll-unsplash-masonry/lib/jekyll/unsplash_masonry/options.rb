# frozen_string_literal: true

module Jekyll
  module UnsplashMasonry
    # Merges defaults, the `unsplash_masonry:` block of _config.yml and the options given to the tag.
    class Options
      DEFAULTS = {
        "app_name" => nil,
        "columns" => 3,
        "gap" => "1rem",
        "size" => "regular",
        "class" => nil,
        "srcset" => true,
        "srcset_widths" => [400, 800, 1200, 1600],
        "lightbox" => false,
        "inline_css" => true,
        "cache_dir" => ".jekyll-cache/unsplash",
        "cache_ttl_days" => 30,
        "refresh" => false,
        "download_tracking" => false,
        "api_url" => "https://api.unsplash.com"
      }.freeze

      SIZES = %w(small regular).freeze
      GAP_RE = /\A[0-9.]+(px|rem|em|%|vw|vh)?\z/.freeze

      attr_reader :values

      def self.from(site_config, tag_args)
        new(DEFAULTS.merge(site_config || {}).merge(tag_args || {}))
      end

      def initialize(values)
        @values = values
      end

      def [](key)
        @values[key]
      end

      DEFAULT_APP_NAME = "jekyll-unsplash-masonry"

      def app_name_set?
        !@values["app_name"].to_s.strip.empty?
      end

      def app_name
        app_name_set? ? @values["app_name"].to_s.strip : DEFAULT_APP_NAME
      end

      def columns
        n = @values["columns"].to_i
        n = DEFAULTS["columns"] if n < 1
        [n, 12].min
      end

      def gap
        g = @values["gap"].to_s.strip
        GAP_RE.match?(g) ? (g =~ /\A[0-9.]+\z/ ? "#{g}px" : g) : DEFAULTS["gap"]
      end

      def size
        s = @values["size"].to_s.strip.downcase
        SIZES.include?(s) ? s : "regular"
      end

      def extra_class
        @values["class"].to_s.strip
      end

      def srcset_widths
        Array(@values["srcset_widths"]).map(&:to_i).select(&:positive?).uniq.sort
      end

      def ttl_seconds
        days = @values["cache_ttl_days"]
        return nil if days.nil? || days == false || days.to_f <= 0

        days.to_f * 86_400
      end

      def api_url
        @values["api_url"].to_s.chomp("/")
      end

      %w(srcset lightbox inline_css refresh download_tracking).each do |key|
        define_method("#{key}?") { truthy?(@values[key]) }
      end

      private

      def truthy?(value)
        return value if [true, false].include?(value)

        %w(true yes 1 on).include?(value.to_s.strip.downcase)
      end
    end
  end
end
