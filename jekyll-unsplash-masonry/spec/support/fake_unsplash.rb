# frozen_string_literal: true

require "json"
require "webrick"

# A tiny local stand-in for api.unsplash.com so the specs never touch the real API.
class FakeUnsplash
  attr_reader :requests
  attr_accessor :limit_after, :missing, :overrides

  def initialize
    @requests = []
    @limit_after = nil # number of requests answered before 403 + X-Ratelimit-Remaining: 0
    @missing = []
    @overrides = {} # id => hash merged into that photo's JSON
    @server = WEBrick::HTTPServer.new(Port: 0, BindAddress: "127.0.0.1",
                                      Logger: WEBrick::Log.new(File::NULL), AccessLog: [])
    @server.mount_proc("/photos") { |req, res| handle(req, res) }
    @thread = Thread.new { @server.start }
  end

  def url
    "http://127.0.0.1:#{@server.config[:Port]}"
  end

  def stop
    @server.shutdown
    @thread.join
  end

  def photo_requests
    @requests.select { |r| r[:path] =~ %r{\A/photos/[^/]+\z} }
  end

  def self.photo(id, overrides = {})
    {
      "id" => id,
      "width" => 4000,
      "height" => 6000,
      "color" => "#262626",
      "description" => nil,
      "alt_description" => "a test photo #{id}",
      "urls" => {
        "raw" => "https://images.unsplash.com/photo-#{id}?ixid=IX#{id}&ixlib=rb-4.1.0",
        "full" => "https://images.unsplash.com/photo-#{id}?ixid=IX#{id}&ixlib=rb-4.1.0&q=85&fm=jpg&crop=entropy",
        "regular" => "https://images.unsplash.com/photo-#{id}?ixid=IX#{id}&ixlib=rb-4.1.0&q=80&w=1080",
        "small" => "https://images.unsplash.com/photo-#{id}?ixid=IX#{id}&ixlib=rb-4.1.0&q=80&w=400"
      },
      "links" => { "download_location" => "DOWNLOAD_#{id}" },
      "user" => { "name" => "Jane <Doe>", "username" => "jane",
                  "links" => { "html" => "https://unsplash.com/@jane" } }
    }.merge(overrides)
  end

  private

  def handle(req, res)
    @requests << { path: req.path, query: req.query_string, auth: req["Authorization"],
                   version: req["Accept-Version"] }
    if @limit_after && @requests.size > @limit_after
      res.status = 403
      res["X-Ratelimit-Remaining"] = "0"
      res.body = "Rate Limit Exceeded"
      return
    end
    id = req.path.split("/").last
    if @missing.include?(id)
      res.status = 404
      res.body = JSON.generate("errors" => ["Couldn't find Photo"])
      return
    end
    res["Content-Type"] = "application/json"
    res["X-Ratelimit-Remaining"] = "40"
    res.body = JSON.generate(self.class.photo(id, @overrides.fetch(id, {})))
  end
end
