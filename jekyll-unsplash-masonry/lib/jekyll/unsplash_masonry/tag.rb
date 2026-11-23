# frozen_string_literal: true

module Jekyll
  module UnsplashMasonry
    # {% unsplash_grid %} URLs, one per line {% endunsplash_grid %}
    # {% unsplash_grid ids="A,B" %}   {% unsplash_grid data="art" %}   (no end tag needed)
    class Tag < Liquid::Tag
      END_TAG = /\A\{%-?\s*endunsplash_grid\s*-?%\}\z/.freeze
      Bare = Struct.new(:text) do
        def to_s
          text
        end
      end

      ARG_RE = /([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"']+))/.freeze

      def initialize(tag_name, markup, parse_context)
        super
        @args = {}
        markup.scan(ARG_RE) { |key, dq, sq, bare| @args[key] = dq || sq || Bare.new(bare) }
        # Without ids= or data= the URLs come from the tag body, which needs an end tag.
        @block = !(@args.key?("ids") || @args.key?("data"))
        @body = +""
      end

      # The body is read literally (one URL per line); Liquid inside it is not evaluated.
      def parse(tokenizer)
        return unless @block

        while (token = tokenizer.shift)
          return if END_TAG.match?(token.strip)

          @body << token
        end
        raise Liquid::SyntaxError, "unsplash_grid: missing {% endunsplash_grid %} " \
                                   "(or use ids=\"...\" / data=\"...\", which need no end tag)"
      end

      def render(context)
        site = context.registers[:site]
        args = @args.transform_values { |v| v.is_a?(Bare) ? context[v.to_s] : v }
        options = Options.from(site.config["unsplash_masonry"], args)
        where = context.registers[:page] && context.registers[:page]["path"]

        ids = collect_ids(site, context, args, where)
        raise Error, "unsplash_grid#{where ? " (#{where})" : ''}: no photos given. " \
                     "Use ids=, data= or put URLs between the tags." if ids.empty?

        warn_app_name(options)
        resolver = Resolver.new(options, site.source)
        photos = resolver.resolve(ids, refresh: options.refresh?)
        Renderer.new(options).render(photos, assets: first_use?(context))
      end

      private

      def collect_ids(site, context, args, where)
        ids = []
        bad = []
        if args["ids"]
          found, unparsed = Parser.extract_ids(Array(args["ids"]).join("\n").tr(",", "\n"))
          ids.concat(found)
          bad.concat(unparsed)
        end
        if args["data"]
          found, unparsed = Parser.extract_ids(data_lines(site, args["data"].to_s, where).join("\n"))
          ids.concat(found)
          bad.concat(unparsed)
        end
        found, unparsed = Parser.extract_ids(@body)
        ids.concat(found)
        bad.concat(unparsed)

        bad.each do |token|
          Jekyll.logger.warn("UnsplashMasonry:", "#{where || 'unsplash_grid'}: can't read a photo ID from #{token.inspect}, skipped")
        end
        ids.uniq
      end

      # _data/<name>.yml: a list of URLs/IDs, or a list of {id:|url:} hashes. "a.b" digs into nested data.
      def data_lines(site, name, where)
        value = name.split(".").reduce(site.data) { |memo, key| memo.respond_to?(:[]) && !memo.is_a?(String) ? memo[key] : nil }
        if value.nil?
          Jekyll.logger.warn("UnsplashMasonry:", "#{where || 'unsplash_grid'}: no data file or key #{name.inspect} in _data, skipped")
          return []
        end
        value = value.values if value.is_a?(Hash) && !value.key?("id") && !value.key?("url")
        Array(value).flat_map do |item|
          item.is_a?(Hash) ? [item["id"] || item["url"]] : [item]
        end.compact.map(&:to_s)
      end

      def warn_app_name(options)
        return if options.app_name_set? || State.app_name_warned?

        State.app_name_warned!
        Jekyll.logger.warn("UnsplashMasonry:", "unsplash_masonry.app_name is not set in _config.yml; credit links use " \
                                               "utm_source=#{Options::DEFAULT_APP_NAME}. Set it to your Unsplash app name.")
      end

      # CSS and the lightbox script are emitted once per rendered document.
      def first_use?(context)
        return false if context.registers[:unsplash_masonry_assets]

        context.registers[:unsplash_masonry_assets] = true
      end
    end

    # Optional closing tag for the ids= / data= forms; ignored.
    class EndTag < Liquid::Tag
      def render(_context)
        ""
      end
    end
  end
end
