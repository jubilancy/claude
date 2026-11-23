# frozen_string_literal: true

require "json"
require "net/http"
require "uri"

module Jekyll
  module UnsplashMasonry
    # Minimal Unsplash API client on net/http. Build time only; the key is never rendered.
    class Client
      Response = Struct.new(:code, :body, :remaining) do
        def success?
          code == 200
        end

        # Unsplash answers 403 with X-Ratelimit-Remaining: 0 when the hourly limit is used up.
        def rate_limited?
          (code == 403 && remaining == 0) || code == 429
        end

        def json
          JSON.parse(body)
        rescue JSON::ParserError
          nil
        end
      end

      NETWORK_ERRORS = [
        SocketError, Timeout::Error, SystemCallError, IOError, OpenSSL::SSL::SSLError,
        Net::OpenTimeout, Net::ReadTimeout, Net::ProtocolError
      ].freeze

      attr_reader :api_url, :key

      def initialize(api_url:, key:)
        @api_url = api_url
        @key = key
      end

      def get_photo(id)
        get(URI("#{@api_url}/photos/#{id}"))
      end

      # `download_location` comes from the photo JSON and is already a full API URL.
      def get_url(url)
        get(URI(url))
      end

      private

      def get(uri)
        request = Net::HTTP::Get.new(uri)
        request["Authorization"] = "Client-ID #{@key}"
        request["Accept-Version"] = "v1"
        request["User-Agent"] = "jekyll-unsplash-masonry/#{VERSION}"
        http = Net::HTTP.start(uri.host, uri.port, use_ssl: uri.scheme == "https",
                                                    open_timeout: 10, read_timeout: 20)
        begin
          res = http.request(request)
        ensure
          http.finish if http.started?
        end
        remaining = res["X-Ratelimit-Remaining"]
        Response.new(res.code.to_i, res.body.to_s, remaining.nil? ? nil : remaining.to_i)
      end
    end
  end
end
