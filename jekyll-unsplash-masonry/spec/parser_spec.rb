# frozen_string_literal: true

RSpec.describe Jekyll::UnsplashMasonry::Parser do
  def id(token)
    described_class.extract_id(token)
  end

  it "reads a plain photo URL" do
    expect(id("https://unsplash.com/photos/BPWZ01FtySg")).to eq("BPWZ01FtySg")
  end

  it "keeps IDs that start with an underscore or contain a dash" do
    expect(id("https://unsplash.com/photos/_qL-OGpBOds")).to eq("_qL-OGpBOds")
  end

  it "takes the last 11 characters of a slug-style URL" do
    expect(id("https://unsplash.com/photos/some-title-BPWZ01FtySg")).to eq("BPWZ01FtySg")
    expect(id("https://unsplash.com/photos/a-photo-with-a-dash-_qL-OGpBOds")).to eq("_qL-OGpBOds")
  end

  it "ignores query strings, fragments, trailing slashes and /download" do
    expect(id("https://unsplash.com/photos/BPWZ01FtySg?utm_source=x&ixid=abc")).to eq("BPWZ01FtySg")
    expect(id("https://unsplash.com/photos/BPWZ01FtySg/")).to eq("BPWZ01FtySg")
    expect(id("https://unsplash.com/photos/BPWZ01FtySg/download?force=true")).to eq("BPWZ01FtySg")
    expect(id("https://unsplash.com/photos/BPWZ01FtySg#comments")).to eq("BPWZ01FtySg")
  end

  it "accepts a bare ID" do
    expect(id("BPWZ01FtySg")).to eq("BPWZ01FtySg")
  end

  it "returns nil for things it cannot parse" do
    expect(id("")).to be_nil
    expect(id("https://unsplash.com/")).to be_nil
    expect(id("https://unsplash.com/photos/short")).to be_nil
    expect(id("https://unsplash.com/photos/bad!chars!!")).to be_nil
    expect(id("not a url")).to be_nil
  end

  describe ".extract_ids" do
    it "parses a block, skipping blanks and comments, and reports bad lines instead of raising" do
      text = <<~TXT
        # my favourites
        https://unsplash.com/photos/BPWZ01FtySg

        https://unsplash.com/photos/EQB0hDo3nds, https://unsplash.com/photos/some-title-E64t6WGW0Go
        https://unsplash.com/photos/nope
        BPWZ01FtySg
      TXT
      ids, bad = described_class.extract_ids(text)
      expect(ids).to eq(%w(BPWZ01FtySg EQB0hDo3nds E64t6WGW0Go))
      expect(bad).to eq(["https://unsplash.com/photos/nope"])
    end
  end
end
