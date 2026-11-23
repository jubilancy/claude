# frozen_string_literal: true

require "cgi"
require "uri"

module Jekyll
  module UnsplashMasonry
    # Photo hashes -> HTML. No blank lines and no indentation, so Markdown pages pass it through untouched.
    class Renderer
      UNSPLASH_HOME = "https://unsplash.com/"
      COLOR_RE = /\A#[0-9a-fA-F]{3,8}\z/.freeze

      CSS = <<~CSS.gsub(/\s*\n\s*/, "")
        .unsplash-masonry{column-count:var(--um-cols,3);column-gap:var(--um-gap,1rem);margin:1.5rem 0}
        .unsplash-masonry__item{break-inside:avoid;margin:0 0 var(--um-gap,1rem)}
        .unsplash-masonry__img{display:block;width:100%;height:auto;background-color:#e5e5e5}
        .unsplash-masonry__credit{font-size:.8rem;line-height:1.3;padding-top:.35rem;opacity:.8}
        @media(max-width:1023px){.unsplash-masonry{column-count:var(--um-cols-md,2)}}
        @media(max-width:639px){.unsplash-masonry{column-count:var(--um-cols-sm,1)}}
        .um-dialog{border:0;padding:0;background:transparent;max-width:95vw;max-height:95vh}
        .um-dialog::backdrop{background:rgba(0,0,0,.85)}
        .um-dialog img{display:block;max-width:95vw;max-height:90vh;cursor:zoom-out}
      CSS

      # Progressive enhancement: without JS (or <dialog>) the link just opens the large image.
      LIGHTBOX_JS = <<~JS.gsub(/\s*\n\s*/, "")
        (function(){
        if(!window.HTMLDialogElement)return;
        var d=document.createElement('dialog');d.className='um-dialog';
        var i=document.createElement('img');d.appendChild(i);document.body.appendChild(d);
        d.addEventListener('click',function(){d.close();});
        document.addEventListener('click',function(e){
        if(e.defaultPrevented||e.button||e.metaKey||e.ctrlKey||e.shiftKey)return;
        var a=e.target.closest&&e.target.closest('a[data-um-large]');
        if(!a)return;
        e.preventDefault();
        var m=a.querySelector('img');
        i.src=a.getAttribute('data-um-large');i.alt=m?m.alt:'';
        d.showModal();
        });
        })();
      JS

      def initialize(options)
        @options = options
      end

      def self.css
        CSS
      end

      def self.lightbox_js
        LIGHTBOX_JS
      end

      def render(photos, assets: true)
        out = []
        out << "<style>#{CSS}</style>" if assets && @options.inline_css?
        out << "<script>#{LIGHTBOX_JS}</script>" if assets && @options.lightbox?
        out << %(<div class="#{grid_classes}" style="#{grid_style}">)
        photos.each { |photo| out << figure(photo) }
        out << "</div>"
        out.join("\n")
      end

      def figure(photo)
        urls = photo["urls"] || {}
        src = urls[@options.size == "small" ? "small" : "regular"] || urls["regular"] || urls["small"]
        return "" unless src

        color = photo["color"].to_s
        style = COLOR_RE.match?(color) ? %( style="background-color:#{color}") : ""
        img = %(<img class="unsplash-masonry__img" src="#{esc(src)}"#{srcset(urls)}#{dims(photo)} ) +
              %(alt="#{esc(alt_text(photo))}" loading="lazy" decoding="async"#{style}>)
        img = lightbox_link(urls, src, img) if @options.lightbox?
        %(<figure class="unsplash-masonry__item">#{img}#{credit(photo)}</figure>)
      end

      def alt_text(photo)
        [photo["alt_description"], photo["description"]].each do |text|
          text = text.to_s.strip.gsub(/\s+/, " ")
          return text unless text.empty?
        end
        "Photo by #{photographer_name(photo)} on Unsplash"
      end

      def credit(photo)
        name = esc(photographer_name(photo))
        profile = photo.dig("user", "links", "html")
        who = profile ? %(<a href="#{esc(self.class.with_utm(profile, app_name))}">#{name}</a>) : name
        home = esc(self.class.with_utm(UNSPLASH_HOME, app_name))
        %(<figcaption class="unsplash-masonry__credit">Photo by #{who} on <a href="#{home}">Unsplash</a></figcaption>)
      end

      # Appends utm_source/utm_medium, keeping any query the URL already has.
      def self.with_utm(url, app_name)
        uri = URI.parse(url)
        query = URI.decode_www_form(uri.query.to_s).reject { |k, _| %w(utm_source utm_medium).include?(k) }
        query << ["utm_source", app_name] << ["utm_medium", "referral"]
        uri.query = URI.encode_www_form(query)
        uri.to_s
      rescue URI::InvalidURIError
        url
      end

      private

      def app_name
        @options.app_name
      end

      def grid_classes
        ["unsplash-masonry", @options.extra_class].reject(&:empty?).map { |c| esc(c) }.join(" ")
      end

      def grid_style
        cols = @options.columns
        "--um-cols:#{cols};--um-cols-md:#{[cols, 2].min};--um-cols-sm:1;--um-gap:#{esc(@options.gap)}"
      end

      def photographer_name(photo)
        name = photo.dig("user", "name").to_s.strip
        name.empty? ? photo.dig("user", "username").to_s : name
      end

      def dims(photo)
        w = photo["width"].to_i
        h = photo["height"].to_i
        w.positive? && h.positive? ? %( width="#{w}" height="#{h}") : ""
      end

      def srcset(urls)
        raw = urls["raw"]
        widths = @options.srcset_widths
        return "" unless @options.srcset? && raw && !widths.empty?

        sep = raw.include?("?") ? "&" : "?"
        list = widths.map { |w| "#{raw}#{sep}w=#{w} #{w}w" }.join(", ")
        cols = @options.columns
        sizes = "(min-width:1024px) #{(100.0 / cols).round(2)}vw, (min-width:640px) #{(100.0 / [cols, 2].min).round(2)}vw, 100vw"
        %( srcset="#{esc(list)}" sizes="#{esc(sizes)}")
      end

      def lightbox_link(urls, src, img)
        large = urls["full"] || urls["regular"] || src
        %(<a href="#{esc(large)}" data-um-large="#{esc(large)}">#{img}</a>)
      end

      def esc(text)
        CGI.escapeHTML(text.to_s)
      end
    end
  end
end
