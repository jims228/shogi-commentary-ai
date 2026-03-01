require "sinatra"
require "json"
require "bioshogi"

set :port, 7070
set :bind, ENV.fetch('BIOSHOGI_BIND', '127.0.0.1')

post "/analyze" do
  content_type :json
  body = JSON.parse(request.body.read)
  kifu = body["kifu"] || ""
  
  begin
    parser = Bioshogi::Parser.parse(kifu, {
      typical_error_case: :embed,
      analysis_feature: true
    })
    
    result = parser.container.players.map.with_index do |player, i|
      tags = player.tag_bundle.to_h
      {
        player: i,
        attack:    tags[:attack]    || [],
        defense:   tags[:defense]   || [],
        technique: tags[:technique] || [],
        note:      tags[:note]      || []
      }
    end
    
    { ok: true, players: result }.to_json
  rescue => e
    { ok: false, error: e.message }.to_json
  end
end

get "/health" do
  { ok: true }.to_json
end
