# frozen_string_literal: true

require 'sinatra/base'
require 'json'
require 'rack/attack'
require_relative 'relay'

module RubyBot
  # Sinatra API server
  class API < Sinatra::Base
    use Rack::Attack
    
    # Rate limiting
    Rack::Attack.throttle('req/ip', limit: 60, period: 60) do |req|
      req.ip unless req.path.start_with?('/static')
    end
    
    Rack::Attack.throttle('login/ip', limit: 5, period: 60) do |req|
      req.ip if req.path == '/api/auth/login' && req.post?
    end

    def initialize(coordinator:, settings:)
      super()
      @coordinator = coordinator
      @settings = settings
    end

    get '/' do
      redirect '/dashboard'
    end

    get '/dashboard' do
      content_type :html
      '<!DOCTYPE html>
<html>
<head>
  <title>UpLove Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; padding: 20px; }
    .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
    .healthy { background: #d4edda; }
    .degraded { background: #fff3cd; }
    .unhealthy { background: #f8d7da; }
  </style>
</head>
<body>
  <h1>UpLove Dashboard</h1>
  <div id="status"></div>
  <script>
    fetch("/api/health")
      .then(r => r.json())
      .then(data => {
        const div = document.getElementById("status");
        div.className = "status " + data.health_status;
        div.innerHTML = `
          <h2>System Status: ${data.health_status}</h2>
          <p>Uptime: ${data.uptime_formatted}</p>
          <p>Discord: ${data.discord_connected ? "Connected" : "Disconnected"}</p>
          <p>IRC: ${data.irc_connected ? "Connected" : "Disconnected"}</p>
          <p>Messages: ${data.message_count}</p>
          <p>Errors: ${data.error_count}</p>
        `;
      });
  </script>
</body>
</html>'
    end

    get '/api/health' do
      content_type :json
      stats = @coordinator.get_health_stats
      
      # Format uptime
      uptime_seconds = stats[:uptime_seconds]
      days = (uptime_seconds / 86_400).to_i
      hours = ((uptime_seconds % 86_400) / 3600).to_i
      minutes = ((uptime_seconds % 3600) / 60).to_i
      
      parts = []
      parts << "#{days}d" if days > 0
      parts << "#{hours}h" if hours > 0
      parts << "#{minutes}m" if minutes > 0
      uptime_formatted = parts.any? ? parts.join(' ') : '0s'
      
      health_status = 'healthy'
      health_status = 'degraded' unless stats[:discord_connected] && stats[:irc_connected]
      health_status = 'unhealthy' if stats[:error_count] > 100
      
      JSON.generate(
        stats.merge(
          uptime_formatted: uptime_formatted,
          health_status: health_status
        )
      )
    end

    get '/api/features' do
      content_type :json
      JSON.generate(@coordinator.storage.get_feature_flags)
    end

    post '/api/features/:feature' do |feature|
      content_type :json
      enabled = params[:enabled] == 'true' || params[:enabled] == true
      @coordinator.storage.set_feature_flag(feature, enabled)
      JSON.generate({ feature: feature, enabled: enabled })
    end

    get '/api/monitor/urls' do
      content_type :json
      JSON.generate(@coordinator.storage.list_monitor_urls)
    end

    post '/api/monitor/urls' do
      content_type :json
      url = params[:url] || JSON.parse(request.body.read)['url']
      success = @coordinator.storage.add_monitor_url(url)
      status success ? 201 : 400
      JSON.generate({ success: success, url: url })
    end

    delete '/api/monitor/urls/:url' do |url|
      content_type :json
      success = @coordinator.storage.remove_monitor_url(url)
      status success ? 200 : 404
      JSON.generate({ success: success })
    end

    get '/api/rss/feeds' do
      content_type :json
      JSON.generate(@coordinator.storage.list_rss_feeds)
    end

    post '/api/rss/feeds' do
      content_type :json
      url = params[:url] || JSON.parse(request.body.read)['url']
      success = @coordinator.storage.add_rss_feed(url)
      status success ? 201 : 400
      JSON.generate({ success: success, url: url })
    end

    delete '/api/rss/feeds/:url' do |url|
      content_type :json
      success = @coordinator.storage.remove_rss_feed(url)
      status success ? 200 : 404
      JSON.generate({ success: success })
    end

    post '/football-nation' do
      content_type :json
      
      # Check webhook secret if configured
      if @settings.respond_to?(:football_webhook_secret) && @settings.football_webhook_secret
        provided_secret = request.env['HTTP_X_WEBHOOK_SECRET']
        unless provided_secret == @settings.football_webhook_secret
          status 401
          return JSON.generate({ error: 'Invalid webhook secret' })
        end
      end
      
      begin
        data = JSON.parse(request.body.read)
        summary = format_football_event(data)
        @coordinator.announce_football_event(summary) if @coordinator.respond_to?(:announce_football_event)
        JSON.generate({ success: true, message: summary })
      rescue JSON::ParserError
        status 400
        JSON.generate({ error: 'Invalid JSON' })
      end
    end

    private

    def format_football_event(data)
      title = data['title'] || data[:title] || 'Football Update'
      competition = data['competition'] || data[:competition]
      team = data['team'] || data[:team]
      opponent = data['opponent'] || data[:opponent]
      minute = data['minute'] || data[:minute]
      score_home = data['score_home'] || data[:score_home]
      score_away = data['score_away'] || data[:score_away]
      commentary = data['commentary'] || data[:commentary]
      
      parts = ["⚽ #{title}"]
      parts << "#{competition}" if competition
      parts << "#{team} vs #{opponent}" if team && opponent
      parts << "#{minute}'" if minute
      parts << "(#{score_home}-#{score_away})" if score_home && score_away
      parts << "- #{commentary}" if commentary
      
      parts.join(' ')
    end
  end
end

