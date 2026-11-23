# frozen_string_literal: true

module Jekyll
  module UnsplashMasonry
    # Turns photo IDs into photo hashes: disk cache first, API only when needed.
    class Resolver
      def initialize(options, source_dir, key: ENV["UNSPLASH_ACCESS_KEY"])
        @options = options
        @key = key.to_s.strip
        @key = nil if @key.empty?
        @cache = Cache.new(File.expand_path(options["cache_dir"], source_dir), options.ttl_seconds)
        @client = Client.new(api_url: options.api_url, key: @key) if @key
      end

      attr_reader :cache

      # @return [Array<Hash>] photos in the order of +ids+; photos that could not be loaded are left out
      def resolve(ids, refresh: false)
        ids.filter_map { |id| photo(id, refresh) }
      end

      private

      def photo(id, refresh)
        return State.photos[id] if State.photos.key?(id)

        cached = @cache.read(id)
        return remember(id, cached, :cache) if cached && !refresh && @cache.fresh?(id)

        return skipped(id, cached) if State.rate_limited?
        return without_key(id, cached) unless @client

        fetch(id, cached)
      end

      def fetch(id, cached)
        State.request_made!
        res = @client.get_photo(id)
        data = res.success? ? res.json : nil

        if data.is_a?(Hash)
          @cache.write(id, data)
          remember(id, data, :fetched)
        elsif res.rate_limited?
          State.rate_limited!
          skipped(id, cached)
        elsif res.code == 401
          raise Error, "Unsplash rejected UNSPLASH_ACCESS_KEY (HTTP 401). Check that the key is an Access Key."
        else
          Jekyll.logger.warn("UnsplashMasonry:", "Photo #{id}: HTTP #{res.code}" \
                                                 "#{cached ? ', using cached copy' : ', skipping it'}")
          cached ? remember(id, cached, :cache) : nil
        end
      rescue *Client::NETWORK_ERRORS => e
        Jekyll.logger.warn("UnsplashMasonry:", "Photo #{id}: #{e.class}: #{e.message}" \
                                               "#{cached ? ', using cached copy' : ', skipping it'}")
        cached ? remember(id, cached, :cache) : nil
      end

      def without_key(id, cached)
        unless cached
          raise Error, "UNSPLASH_ACCESS_KEY is not set and photo #{id} is not in the cache " \
                       "(#{@cache.dir}). Set the key in the environment for the first build " \
                       "(see the README), or remove the photo."
        end

        unless State.no_key_warned?
          State.no_key_warned!
          Jekyll.logger.warn("UnsplashMasonry:", "UNSPLASH_ACCESS_KEY is not set; using cached photos only " \
                                                 "(stale or refresh requests are ignored).")
        end
        remember(id, cached, :cache)
      end

      def skipped(id, cached)
        if cached
          State.skipped_stale << id
          remember(id, cached, :cache)
        else
          State.skipped_no_data << id
          nil
        end
      end

      def remember(id, photo, source)
        State.photos[id] = photo
        (source == :fetched ? State.fetched : State.from_cache) << id
        track_download(id, photo)
        photo
      end

      # Opt-in only (download_tracking: true). Never called for a display-only gallery.
      def track_download(id, photo)
        return unless @options.download_tracking? && @client
        return if State.rate_limited? || @cache.marked?(id, "downloaded")

        url = photo.dig("links", "download_location")
        return unless url

        State.request_made!
        res = @client.get_url(url)
        if res.success?
          @cache.mark(id, "downloaded")
        elsif res.rate_limited?
          State.rate_limited!
        else
          Jekyll.logger.warn("UnsplashMasonry:", "download_location for #{id}: HTTP #{res.code}")
        end
      rescue *Client::NETWORK_ERRORS => e
        Jekyll.logger.warn("UnsplashMasonry:", "download_location for #{id}: #{e.class}: #{e.message}")
      end
    end
  end
end
