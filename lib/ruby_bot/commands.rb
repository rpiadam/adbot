# frozen_string_literal: true

require 'discordrb'

module RubyBot
  # Discord slash commands
  module Commands
    # Register all slash commands with the bot
    def self.register_commands(bot, coordinator)
      # Register /relaystatus command
      bot.register_application_command(:relaystatus, 'Show Discord ↔ IRC bridge status') do |cmd|
        # No options needed for this command
      end

      bot.application_command(:relaystatus) do |event|
        handle_relay_status(event, coordinator)
      end

      # Register /relayping command
      bot.register_application_command(:relayping, 'Measure the relay\'s Discord latency') do |cmd|
        # No options needed
      end

      bot.application_command(:relayping) do |event|
        handle_relay_ping(event, bot)
      end
    end

    module_function

    # Handle /relaystatus command
    def handle_relay_status(event, coordinator)
      begin
        channel = coordinator.instance_variable_get(:@discord_channel)
        webhook_configured = coordinator.settings.discord_webhook_url ? true : false

        parts = [
          '**Relay Status**',
          channel ? "- Discord channel: ##{channel.name} (#{channel.id})" : '- Discord channel: Not connected',
          "- Webhook configured: #{webhook_configured ? 'yes' : 'no'}",
          '',
          '**IRC Networks:**'
        ]

        irc_bots = coordinator.instance_variable_get(:@irc_bots)
        irc_networks = coordinator.settings.irc_networks

        if irc_bots&.any?
          irc_bots.each_with_index do |bot, i|
            network = irc_networks[i]
            status = bot&.connected? ? '✅ connected' : '❌ disconnected'
            parts << "#{i + 1}. #{network.server}:#{network.port} → #{network.channel} (#{status})"
          end
        else
          parts << 'No IRC networks configured'
        end

        event.respond(content: parts.join("\n"), ephemeral: false)
      rescue StandardError => e
        event.respond(content: "Error getting relay status: #{e.message}", ephemeral: true)
      end
    end

    # Handle /relayping command
    def handle_relay_ping(event, bot)
      begin
        before = Time.now
        latency_ms = (bot.latency * 1000).round(0)
        event.respond(content: "Relay pong! #{latency_ms} ms", ephemeral: false)
      rescue StandardError => e
        event.respond(content: "Error: #{e.message}", ephemeral: true)
      end
    end
  end
end

