# frozen_string_literal: true

require 'discordrb'
require 'cinch'
require 'logger'
require_relative 'config'
require_relative 'storage'

module RubyBot
  # Coordinates Discord and IRC relay
  class RelayCoordinator
    attr_reader :settings, :storage, :discord_bot, :irc_bots

    def initialize(settings)
      @settings = settings
      @storage = Storage.new
      @logger = Logger.new($stdout)
      
      @discord_bot = nil
      @irc_bots = []
      @discord_channel = nil
      @discord_webhook = nil
      
      @start_time = Time.now
      @error_count = 0
      @message_count = 0
      @discord_reconnect_count = 0
      @irc_reconnect_count = 0
    end

    def start_discord
      intents = Discordrb::INTENTS[:default] |
                Discordrb::INTENTS[:server_messages] |
                Discordrb::INTENTS[:server_members] |
                Discordrb::INTENTS[:server_voice_states]

      @discord_bot = Discordrb::Bot.new(
        token: @settings.discord_token,
        intents: intents,
        ignore_bots: true
      )
      
      setup_discord_events
      @discord_bot.run(true) # Run in async mode
    end

    def start_irc
      @settings.irc_networks.each do |network|
        bot = create_irc_bot(network)
        @irc_bots << bot
        
        Thread.new do
          begin
            bot.start
          rescue StandardError => e
            @logger.error("IRC bot error for #{network.server}:#{network.port}: #{e}")
            @error_count += 1
            sleep 5
            retry
          end
        end
      end
    end

    def send_to_irc(message)
      sent = false
      @irc_bots.each_with_index do |bot, i|
        next unless bot.connected?
        
        begin
          network = @settings.irc_networks[i]
          channel = bot.Channel(network.channel)
          channel.send(message)
          sent = true
        rescue StandardError => e
          network = @settings.irc_networks[i]
          @logger.error("Failed to send to IRC #{network.server}:#{network.port}: #{e}")
          @error_count += 1
        end
      end
      
      @logger.warn("No IRC clients connected, dropping message: #{message}") unless sent
      @error_count += 1 unless sent
    end

    def send_to_discord(message, username: nil)
      return unless @discord_channel
      
      begin
        if @discord_webhook
          # Use webhook if available
          @discord_webhook.execute do |builder|
            builder.content = message
            builder.username = username if username
          end
        else
          # Fallback to regular message
          formatted = username ? "**<#{username}>** #{message}" : message
          @discord_channel.send(formatted)
        end
      rescue StandardError => e
        @logger.error("Failed to send to Discord: #{e}")
        @error_count += 1
      end
    end

    def announce_football_event(summary)
      send_to_discord(summary)
      send_to_irc(summary)
    end

    def get_uptime
      Time.now - @start_time
    end

    def get_health_stats
      uptime_seconds = get_uptime
      discord_ready = @discord_bot&.connected? || false
      irc_connected = @irc_bots.any?(&:connected?)
      
      {
        uptime_seconds: uptime_seconds,
        uptime_hours: (uptime_seconds / 3600).round(2),
        uptime_days: (uptime_seconds / 86_400).round(2),
        error_count: @error_count,
        discord_connected: discord_ready,
        irc_connected: irc_connected,
        message_count: @message_count,
        discord_reconnect_count: @discord_reconnect_count,
        irc_reconnect_count: @irc_reconnect_count
      }
    end

    def shutdown
      @logger.info('Shutting down relay coordinator...')
      @discord_bot&.stop
      @irc_bots.each(&:quit)
    end

    private

    def setup_discord_events
      @discord_bot.ready do |event|
        @logger.info("Discord bot connected as #{event.bot.profile.username}")
        
        channel = @discord_bot.channel(@settings.discord_channel_id)
        if channel
          @discord_channel = channel
          channel.send('🔗 IRC relay is online.')
          ensure_webhook
        else
          @logger.warn("Discord channel #{@settings.discord_channel_id} not found")
        end
      end
      
      @discord_bot.message do |event|
        handle_discord_message(event)
      end
    end

    def handle_discord_message(event)
      return if event.author.bot
      return unless event.channel.id == @settings.discord_channel_id
      
      @message_count += 1
      content = event.message.content
      
      if event.message.attachments.any?
        attachment_urls = event.message.attachments.map(&:url).join(' ')
        content += " [attachments] #{attachment_urls}"
      end
      
      return if content.strip.empty?
      
      prefix = "<#{event.author.display_name}>"
      send_to_irc("#{prefix} #{content}")
    end

    def create_irc_bot(network)
      coordinator = self
      
      bot = Cinch::Bot.new do
        configure do |c|
          c.server = network.server
          c.port = network.port
          c.ssl.use = network.tls
          c.nick = network.nick
          c.channels = [network.channel]
        end
        
        # Store network config
        @network_config = network
        
        on :message do |m|
          next if m.user.nick == bot.nick
          channel_name = network.channel.start_with?('#') ? network.channel[1..-1] : network.channel
          next unless m.channel.name.casecmp(channel_name).zero?
          
          # Forward to Discord
          coordinator.handle_irc_message(m.user.nick, m.message, network.server)
        end
        
        on :connect do
          coordinator.instance_variable_get(:@logger).info("Connected to IRC #{network.server}:#{network.port} as #{bot.nick}")
        end
      end
      
      bot
    end

    def handle_irc_message(author, content, network_name = nil)
      @message_count += 1
      
      # Determine username
      has_multiple = @settings.irc_networks.length > 1
      username = if has_multiple && network_name
                   "#{author} [#{network_name}]"
                 else
                   author
                 end
      
      send_to_discord(content, username: username)
    end

    def ensure_webhook
      return unless @discord_channel
      
      if @settings.discord_webhook_url
        begin
          @discord_webhook = Discordrb::Webhooks::Client.new(url: @settings.discord_webhook_url)
        rescue StandardError => e
          @logger.warn("Failed to create webhook from URL: #{e}")
        end
        return
      end
      
      # Try to find or create webhook
      begin
        webhooks = @discord_channel.webhooks
        existing = webhooks.find { |w| w.name == 'UpLove IRC Relay' }
        
        if existing
          @discord_webhook = existing
        else
          @discord_webhook = @discord_channel.create_webhook('UpLove IRC Relay')
        end
      rescue StandardError => e
        @logger.warn("Could not setup webhook: #{e}")
      end
    end
  end
end

