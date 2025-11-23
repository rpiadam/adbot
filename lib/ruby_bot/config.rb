# frozen_string_literal: true

require 'dotenv'
require 'logger'

module RubyBot
  # Configuration loader and validator
  class Config
    attr_reader :discord_token, :discord_channel_id, :discord_guild_id,
                :discord_webhook_url, :irc_networks, :api_host, :api_port,
                :monitor_urls, :rss_feeds, :feature_flags,
                :welcome_channel_id, :welcome_message,
                :moderation_log_channel_id, :monitor_interval_seconds,
                :rss_poll_interval_seconds, :dashboard_username,
                :dashboard_password, :dashboard_secret_key

    IRCNetworkConfig = Struct.new(:server, :port, :tls, :channel, :nick, keyword_init: true)

    def initialize
      Dotenv.load
      load_config
      validate_config
    end

    private

    def load_config
      @discord_token = env_required('DISCORD_TOKEN')
      @discord_channel_id = env_required('DISCORD_CHANNEL_ID').to_i
      @discord_guild_id = env_optional('DISCORD_GUILD_ID')&.to_i
      @discord_webhook_url = env_optional('DISCORD_WEBHOOK_URL')
      @welcome_channel_id = env_optional('WELCOME_CHANNEL_ID')&.to_i
      @welcome_message = env_optional('WELCOME_MESSAGE')
      @moderation_log_channel_id = env_optional('MODERATION_LOG_CHANNEL_ID')&.to_i
      
      @irc_networks = load_irc_networks
      
      @monitor_urls = parse_csv(env_optional('MONITOR_URLS'))
      @monitor_interval_seconds = (env_optional('MONITOR_INTERVAL_SECONDS') || '300').to_i
      
      @rss_feeds = parse_csv(env_optional('RSS_FEEDS'))
      @rss_poll_interval_seconds = (env_optional('RSS_POLL_INTERVAL_SECONDS') || '600').to_i
      
      @api_host = env_optional('API_HOST') || '0.0.0.0'
      @api_port = (env_optional('API_PORT') || '8000').to_i
      
      @dashboard_username = env_optional('DASHBOARD_USERNAME')
      @dashboard_password = env_optional('DASHBOARD_PASSWORD')
      @dashboard_secret_key = env_optional('DASHBOARD_SECRET_KEY') || 'change-me-in-production'
      
      @feature_flags = {
        games: true,
        music: true,
        monitoring: true,
        rss: true,
        welcome: true,
        moderation: true,
        football: true
      }
    end

    def load_irc_networks
      networks = []
      
      # Check for multi-network format
      irc_servers = parse_csv(env_optional('IRC_SERVERS'))
      
      if irc_servers.any?
        # Multi-network format
        irc_ports = parse_csv(env_optional('IRC_PORTS')).map { |p| p.empty? ? 6667 : p.to_i }
        irc_tls = parse_csv(env_optional('IRC_TLS')).map { |t| ['1', 'true', 'yes'].include?(t.downcase) }
        irc_channels = parse_csv(env_optional('IRC_CHANNELS'))
        irc_nicks = parse_csv(env_optional('IRC_NICKS'))
        
        default_port = (env_optional('IRC_PORT') || '6667').to_i
        default_tls = ['1', 'true', 'yes'].include?((env_optional('IRC_TLS') || 'false').downcase)
        default_nick = env_optional('IRC_NICK') || 'UpLove'
        
        irc_servers.each_with_index do |server, i|
          port = irc_ports[i] || default_port
          tls = irc_tls[i] || default_tls
          channel = irc_channels[i] || raise("IRC_CHANNELS missing entry for server #{i + 1}")
          nick = irc_nicks[i] || default_nick
          
          networks << IRCNetworkConfig.new(
            server: server,
            port: port,
            tls: tls,
            channel: channel,
            nick: nick
          )
        end
      else
        # Single network format (backward compatible)
        networks << IRCNetworkConfig.new(
          server: env_required('IRC_SERVER'),
          port: (env_optional('IRC_PORT') || '6667').to_i,
          tls: ['1', 'true', 'yes'].include?((env_optional('IRC_TLS') || 'false').downcase),
          channel: env_required('IRC_CHANNEL'),
          nick: env_required('IRC_NICK')
        )
      end
      
      networks
    end

    def validate_config
      errors = []
      
      errors << 'DISCORD_TOKEN is required' if @discord_token.nil? || @discord_token == 'replace-me'
      errors << 'DISCORD_CHANNEL_ID is required' if @discord_channel_id.nil?
      errors << 'At least one IRC network must be configured' if @irc_networks.empty?
      
      @irc_networks.each_with_index do |network, i|
        errors << "IRC network #{i + 1}: server is required" if network.server.nil? || network.server.empty?
        errors << "IRC network #{i + 1}: channel is required" if network.channel.nil? || network.channel.empty?
        errors << "IRC network #{i + 1}: nick is required" if network.nick.nil? || network.nick.empty?
        unless (1..65_535).include?(network.port)
          errors << "IRC network #{i + 1}: port must be between 1 and 65535 (got #{network.port})"
        end
      end
      
      unless (1..65_535).include?(@api_port)
        errors << "API_PORT must be between 1 and 65535 (got #{@api_port})"
      end
      
      raise "Configuration validation failed:\n#{errors.map { |e| "  - #{e}" }.join("\n")}" if errors.any?
    end

    def env_required(key)
      value = ENV[key]
      raise "Missing required environment variable: #{key}" if value.nil? || value.empty?
      value
    end

    def env_optional(key)
      ENV[key]
    end

    def parse_csv(value)
      return [] if value.nil? || value.empty?
      value.split(',').map(&:strip).reject(&:empty?)
    end
  end
end

