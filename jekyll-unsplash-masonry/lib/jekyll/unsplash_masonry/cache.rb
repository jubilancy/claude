# frozen_string_literal: true

require "fileutils"
require "json"

module Jekyll
  module UnsplashMasonry
    # One JSON file per photo: <dir>/<id>.json. Freshness is the file's mtime against the TTL.
    class Cache
      attr_reader :dir

      def initialize(dir, ttl_seconds)
        @dir = dir
        @ttl = ttl_seconds
      end

      def path(id)
        File.join(@dir, "#{id}.json")
      end

      def marker(id, name)
        File.join(@dir, "#{id}.#{name}")
      end

      def read(id)
        file = path(id)
        return nil unless File.file?(file)

        JSON.parse(File.read(file))
      rescue JSON::ParserError
        Jekyll.logger.warn("UnsplashMasonry:", "Ignoring corrupt cache file #{file}")
        nil
      end

      def fresh?(id)
        file = path(id)
        return false unless File.file?(file)
        return true if @ttl.nil?

        (Time.now - File.mtime(file)) < @ttl
      end

      def write(id, photo)
        FileUtils.mkdir_p(@dir)
        tmp = "#{path(id)}.tmp#{Process.pid}"
        File.write(tmp, JSON.generate(photo))
        File.rename(tmp, path(id))
      end

      def mark(id, name)
        FileUtils.mkdir_p(@dir)
        FileUtils.touch(marker(id, name))
      end

      def marked?(id, name)
        File.file?(marker(id, name))
      end
    end
  end
end
