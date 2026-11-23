# frozen_string_literal: true

require "uri"

module Jekyll
  module UnsplashMasonry
    # Turns pasted URLs / bare IDs into Unsplash photo IDs.
    #
    # An ID is the last 11 characters of the /photos/<segment> path segment, so
    # "/photos/some-title-BPWZ01FtySg" and "/photos/BPWZ01FtySg" both work. IDs may start
    # with "_" or contain "-". Query strings and fragments are ignored.
    module Parser
      ID_LENGTH = 11
      ID_RE = /\A[A-Za-z0-9_-]{#{ID_LENGTH}}\z/.freeze

      module_function

      # @return [String, nil] the ID, or nil when the token can't be parsed
      def extract_id(token)
        token = token.to_s.strip
        return nil if token.empty?

        segment = segment_for(token)
        return nil if segment.nil? || segment.length < ID_LENGTH

        id = segment[-ID_LENGTH, ID_LENGTH]
        ID_RE.match?(id) ? id : nil
      end

      # @return [Array<(Array<String>, Array<String>)>] [ids, unparseable tokens]
      def extract_ids(text)
        ids = []
        bad = []
        text.to_s.each_line do |line|
          line = line.strip
          next if line.empty? || line.start_with?("#")

          line.split(/[\s,]+/).reject(&:empty?).each do |token|
            id = extract_id(token)
            id ? ids << id : bad << token
          end
        end
        [ids.uniq, bad]
      end

      def segment_for(token)
        path = token.sub(/[?#].*\z/m, "")
        if path.include?("/")
          segments = path.sub(%r{\Ahttps?://}i, "").split("/").reject(&:empty?)
          idx = segments.index("photos")
          segment = idx ? segments[idx + 1] : segments.last
          segment = nil if segment == "download"
          segment
        else
          path
        end
      end
    end
  end
end
